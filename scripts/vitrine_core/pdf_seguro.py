# -*- coding: utf-8 -*-
"""Validacao e higienizacao de PDF (PRD 5.4).

Um PDF nao e um documento: e um formato executavel. Pode trazer JavaScript,
acoes de abertura, arquivos anexados, formularios e metadados com nome de
autor e caminho de pasta de quem o gerou. As fichas do acervo, por exemplo,
carregam `author`, `creator` e IDs internos do Canva.

Por isso o `ficha.pdf` publicado nunca e copia byte a byte do original
(achado A4 do PRD): e uma versao higienizada. O original fica intacto no
acervo.

`valida()` roda **antes** de qualquer outra coisa, na ordem da secao 5.4: o
arquivo nao chega a uma biblioteca de parsing antes de passar pelos testes
baratos de tamanho e assinatura.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "TAMANHO_MAX",
    "PAGINAS_MAX",
    "LADO_MAX_PT",
    "SEGUNDOS_MAX",
    "TOKENS_PERIGOSOS",
    "PdfInvalido",
    "InfoPdf",
    "valida_tamanho",
    "valida_assinatura",
    "valida",
    "valida_dados",
    "higieniza",
    "higieniza_dados",
    "tokens_perigosos",
]

TAMANHO_MAX = 25 * 1024 * 1024
PAGINAS_MAX = 5
LADO_MAX_PT = 5000
SEGUNDOS_MAX = 15

ASSINATURA = b"%PDF-"

# O que nao pode sobreviver a higienizacao. Usado pelos testes de seguranca
# (PRD 12.2) e na conferencia do pacote de publicacao.
TOKENS_PERIGOSOS = (
    b"/JavaScript",
    b"/JS",
    b"/OpenAction",
    b"/Launch",
    b"/EmbeddedFile",
    b"/RichMedia",
)

# Parametros de scrub() conferidos na assinatura do PyMuPDF instalado
# (1.28.2). Os tres desligados sao deliberados:
#   hidden_text=False    mexer no texto invisivel alteraria o conteudo
#   redactions=False     aplicar tarjas reescreveria a pagina
#   remove_links=False   os links da ficha continuam funcionando
_SCRUB = dict(
    attached_files=True,
    clean_pages=True,
    embedded_files=True,
    hidden_text=False,
    javascript=True,
    metadata=True,
    redactions=False,
    remove_links=False,
    reset_fields=True,
    reset_responses=True,
    thumbnails=True,
    xml_metadata=True,
)

# no_new_id=True e o que torna a saida deterministica: sem ele o MuPDF sorteia
# um /ID novo a cada gravacao, os 60 ficha.pdf seriam reescritos em todo build
# e o `git status` nunca ficaria limpo.
_SAVE = dict(garbage=4, deflate=True, clean=True, no_new_id=True)


class PdfInvalido(Exception):
    """PDF recusado. A mensagem ja esta escrita para quem nao e tecnico."""


@dataclass
class InfoPdf:
    paginas: int
    largura_pt: float
    altura_pt: float
    avisos: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Passos baratos -- rodam antes de abrir o arquivo
# --------------------------------------------------------------------------

def valida_tamanho(n_bytes: int) -> None:
    """Passo 1. Recebe o tamanho, nao o conteudo.

    Assim o painel confere o limite a partir do `Content-Length` do arquivo
    ou do comprimento do base64, **antes** de decodificar 25 MB de texto na
    memoria.
    """
    if n_bytes <= 0:
        raise PdfInvalido("O arquivo está vazio.")
    if n_bytes > TAMANHO_MAX:
        mb = n_bytes / 1024 / 1024
        raise PdfInvalido(
            f"A ficha tem {mb:.1f} MB e o limite é "
            f"{TAMANHO_MAX // 1024 // 1024} MB. Tente salvar o PDF com uma "
            "qualidade menor."
        )


def valida_assinatura(inicio: bytes) -> None:
    """Passo 2. Os primeiros bytes precisam ser `%PDF-`.

    A extensao do arquivo e ignorada de proposito: um `.pdf` que na verdade e
    um PNG (ou um arquivo poliglota, valido como duas coisas ao mesmo tempo)
    nao passa daqui.
    """
    if not inicio.startswith(ASSINATURA):
        raise PdfInvalido(
            "Este arquivo não é um PDF. Confira se escolheu a ficha técnica "
            "certa — o nome terminar em .pdf não basta."
        )


# --------------------------------------------------------------------------
# Validacao completa
# --------------------------------------------------------------------------

def _valida_aberto(abre) -> InfoPdf:
    """Passos 3 a 6, com o documento ja aberto por `abre()`."""
    import pymupdf

    try:
        doc = abre()
    except PdfInvalido:
        raise
    except Exception as e:  # pymupdf levanta tipos variados em arquivo corrompido
        raise PdfInvalido(
            "Não conseguimos ler esta ficha. Confira se o arquivo abre "
            "normalmente no seu leitor de PDF."
        ) from e

    try:
        # Passo 4: protegido por senha.
        if doc.needs_pass or doc.is_encrypted:
            raise PdfInvalido(
                "Este PDF está protegido por senha. Salve uma versão sem "
                "senha e tente de novo."
            )

        # Passo 5: numero de paginas.
        n = len(doc)
        if n < 1:
            raise PdfInvalido("Este PDF não tem nenhuma página.")
        if n > PAGINAS_MAX:
            raise PdfInvalido(
                f"Este PDF tem {n} páginas. A ficha técnica deveria ter no "
                f"máximo {PAGINAS_MAX} — confira se escolheu o arquivo certo."
            )

        avisos: list[str] = []
        if n > 1:
            avisos.append(f"o PDF tem {n} paginas; usando a primeira.")

        # Passo 6: dimensoes da pagina 1.
        r = doc[0].rect
        if max(r.width, r.height) > LADO_MAX_PT:
            raise PdfInvalido(
                f"A página deste PDF mede {r.width:.0f}×{r.height:.0f} pontos, "
                "muito maior que uma folha comum. Confira o arquivo."
            )
        if r.width <= 0 or r.height <= 0:
            raise PdfInvalido("A primeira página deste PDF não tem tamanho válido.")

        return InfoPdf(
            paginas=n, largura_pt=r.width, altura_pt=r.height, avisos=avisos
        )
    finally:
        doc.close()


def _com_limite_de_tempo(fn, segundos: int):
    """Roda `fn()` e desiste depois de `segundos`.

    Limitacao conhecida: uma thread em Python nao pode ser interrompida, e o
    parsing do PyMuPDF acontece em C. Se um PDF realmente travar o parser, a
    thread (daemon) continua rodando ate o processo terminar -- o que se ganha
    e a interface nao ficar parada e a pessoa receber uma mensagem. Matar de
    verdade exigiria um subprocesso por arquivo, que custaria mais do que
    resolve num build de 60 fichas confiaveis.
    """
    caixa: dict[str, object] = {}

    def alvo():
        try:
            caixa["ok"] = fn()
        except BaseException as e:  # noqa: BLE001 - repassado na thread principal
            caixa["erro"] = e

    t = threading.Thread(target=alvo, daemon=True)
    t.start()
    t.join(segundos)
    if t.is_alive():
        raise PdfInvalido(
            f"A leitura desta ficha passou de {segundos} segundos e foi "
            "interrompida. O arquivo pode estar corrompido."
        )
    if "erro" in caixa:
        raise caixa["erro"]  # type: ignore[misc]
    return caixa["ok"]


def valida(caminho: Path, *, segundos: int | None = None) -> InfoPdf:
    """Valida um PDF em disco, na ordem da secao 5.4.

    `segundos` liga o limite de tempo; o build nao usa (o acervo e confiavel
    e sao 60 arquivos), o painel usa em todo arquivo recebido.
    """
    import pymupdf

    caminho = Path(caminho)
    try:
        valida_tamanho(caminho.stat().st_size)
    except OSError as e:
        raise PdfInvalido("Não conseguimos abrir este arquivo.") from e

    with caminho.open("rb") as f:
        valida_assinatura(f.read(len(ASSINATURA)))

    def trabalho() -> InfoPdf:
        return _valida_aberto(lambda: pymupdf.open(caminho))

    if segundos:
        return _com_limite_de_tempo(trabalho, segundos)
    return trabalho()


def valida_dados(dados: bytes, *, segundos: int | None = None) -> InfoPdf:
    """Mesma validacao a partir dos bytes -- o caminho do painel.

    O painel recebe o arquivo por arrastar/colar e ja conferiu o limite de
    tamanho antes de decodificar o base64; `valida_tamanho` roda aqui de novo
    porque esta funcao nao pode confiar em quem a chamou.
    """
    import pymupdf

    valida_tamanho(len(dados))
    valida_assinatura(dados[: len(ASSINATURA)])

    def trabalho() -> InfoPdf:
        return _valida_aberto(lambda: pymupdf.open(stream=dados, filetype="pdf"))

    if segundos:
        return _com_limite_de_tempo(trabalho, segundos)
    return trabalho()


# --------------------------------------------------------------------------
# Higienizacao
# --------------------------------------------------------------------------

# Chaves de acao que precisam sair do catalogo e das paginas.
#
# Duas descobertas na versao instalada (PyMuPDF 1.28.2) motivam este bloco:
#
# 1. `scrub(javascript=True)` NAO remove um /OpenAction com acao de
#    JavaScript no catalogo -- o vetor mais comum de JS em PDF, justamente o
#    que a secao 5.4 manda barrar.
# 2. `xref_set_key(..., "null")` neutraliza a acao mas MANTEM a chave: o
#    arquivo sai com `/OpenAction null`. E inofensivo, mas deixa o token
#    visivel para quem auditar o PDF com um grep -- e a garantia da secao
#    5.4 e justamente que ele nao esteja la.
#
# Por isso o dicionario e reescrito sem as chaves, com `update_object`.
_CHAVES_DE_ACAO = ("OpenAction", "AA")

# Arvores de nomes do catalogo (PDF 32000-1, tabela 31). `xref_get_keys` nao
# aceita caminho, entao a lista e enumerada: cada uma e consultada por
# `Names/<arvore>` para saber se existe.
_ARVORES_DE_NOMES = (
    "Dests",
    "AP",
    "JavaScript",
    "Pages",
    "Templates",
    "IDS",
    "URLS",
    "EmbeddedFiles",
    "AlternatePresentations",
    "Renditions",
)
# JavaScript e EmbeddedFiles saem; o resto e navegacao legitima.
_NOMES_PERIGOSOS = ("JavaScript", "EmbeddedFiles", "Renditions")


def _sem_chaves(doc, xref: int, remover: tuple[str, ...]) -> bool:
    """Reescreve o objeto `xref` sem as chaves de `remover`.

    Remonta o dicionario a partir das chaves que ficam, em vez de editar o
    texto do objeto com expressao regular: os valores podem ser dicionarios
    aninhados, e casar chaves por regex erraria no primeiro `>>` interno.

    Devolve True se mexeu em algo.
    """
    presentes = [k for k in doc.xref_get_keys(xref) if k in remover]
    if not presentes:
        return False

    partes = []
    for chave in doc.xref_get_keys(xref):
        if chave in remover:
            continue
        _tipo, valor = doc.xref_get_key(xref, chave)
        partes.append(f"/{chave} {valor}")
    doc.update_object(xref, "<<" + " ".join(partes) + ">>")
    return True


def _remove_acoes(doc) -> None:
    cat = doc.pdf_catalog()
    _sem_chaves(doc, cat, _CHAVES_DE_ACAO)

    # /Names << /JavaScript ... >>: a arvore de nomes com scripts de
    # documento. O /Names pode trazer outras arvores legitimas (Dests), entao
    # so o galho do JavaScript sai; se o /Names ficar vazio, ele sai inteiro.
    if "Names" in doc.xref_get_keys(cat):
        manter = []
        perigosa = False
        for arvore in _ARVORES_DE_NOMES:
            tipo, valor = doc.xref_get_key(cat, f"Names/{arvore}")
            if tipo == "null":
                continue
            if arvore in _NOMES_PERIGOSOS:
                perigosa = True
            else:
                manter.append(f"/{arvore} {valor}")
        if perigosa:
            if manter:
                doc.xref_set_key(cat, "Names", "<<" + " ".join(manter) + ">>")
            else:
                _sem_chaves(doc, cat, ("Names",))

    # acoes automaticas por pagina (ao abrir, ao fechar, ao sair)
    for pagina in doc:
        _sem_chaves(doc, pagina.xref, ("AA",))


def _higieniza_doc(doc) -> bytes:
    doc.scrub(**_SCRUB)
    _remove_acoes(doc)
    saida = doc.tobytes(**_SAVE)

    # Cinto e suspensorio: se algo perigoso sobreviveu, e melhor o build
    # falhar e a vitrine anterior continuar de pe do que publicar um PDF que
    # afirmamos ter higienizado.
    sobrou = tokens_perigosos(saida)
    if sobrou:
        raise PdfInvalido(
            "Não conseguimos limpar este PDF com segurança "
            f"(sobrou: {', '.join(sobrou)}). Gere uma versão simples do "
            "arquivo, sem formulário nem anexos, e tente de novo."
        )
    return saida


def higieniza(origem: Path) -> bytes:
    """Devolve a versao publicavel do PDF em disco. Nao toca no original.

    Resultado deterministico: higienizar o mesmo arquivo duas vezes da os
    mesmos bytes, o que mantem o build idempotente.
    """
    import pymupdf

    doc = pymupdf.open(origem)
    try:
        return _higieniza_doc(doc)
    finally:
        doc.close()


def higieniza_dados(dados: bytes) -> bytes:
    """Versao publicavel a partir dos bytes."""
    import pymupdf

    doc = pymupdf.open(stream=dados, filetype="pdf")
    try:
        return _higieniza_doc(doc)
    finally:
        doc.close()


# Um nome em PDF termina num delimitador -- espaco, /, <, >, [, ], (, ), {, }
# ou %. Sem esse limite, `/EmbeddedFile` casaria dentro de `/EmbeddedFiles`,
# que e a chave (vazia, depois da limpeza) da arvore de nomes: um falso
# positivo que faria o build recusar um PDF ja limpo.
_FIM_DE_NOME = rb"(?![A-Za-z0-9])"


def tokens_perigosos(dados: bytes) -> list[str]:
    """Quais tokens de TOKENS_PERIGOSOS aparecem nos bytes.

    Busca literal, sem parsear. Tem dois limites conhecidos, e os dois estao
    do lado seguro para o uso que se faz dela: um `/JavaScript` escondido
    dentro de um stream comprimido nao seria visto (por isso a remocao real
    acontece em `_remove_acoes`, nao aqui), e um token que aparecesse por
    coincidencia em dados binarios daria falso positivo. Serve como
    conferencia final e para os testes de seguranca.
    """
    achados = []
    for t in TOKENS_PERIGOSOS:
        if re.search(re.escape(t) + _FIM_DE_NOME, dados):
            achados.append(t.decode("ascii"))
    return achados
