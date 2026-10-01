# -*- coding: utf-8 -*-
"""Normalizacao de texto, slugs e os padroes de nome do acervo.

As pastas do acervo sao a fonte da verdade e nunca sao renomeadas pelo
build, entao os dois regex abaixo precisam tolerar as inconsistencias que
ja existem nas 60 pastas originais -- e so elas. Cada tolerancia esta
comentada com o caso que a justifica.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

__all__ = [
    "SLUG_MAX",
    "PASTA_RE",
    "ARQUIVO_RE",
    "sem_acento",
    "chave",
    "so_letras",
    "slugify",
    "normaliza_espacos",
    "limpa_texto",
    "NUMERO_RE",
    "normaliza_numero",
    "TITULO_MAX_NO_NOME",
    "CAMINHO_MAX",
    "RESERVADOS_WINDOWS",
    "NomeInvalido",
    "nome_seguro",
    "numero_para_pasta",
    "nome_pasta_patente",
    "nome_arquivo_patente",
]

SLUG_MAX = 80

# Nome da pasta: "19. BR 10 2022 019303 7" (algumas terminam com "_").
PASTA_RE = re.compile(
    r"^(?P<id>\d+)\s*\.\s*(?P<pais>BR)\s*(?P<esp>\d{2})\s*(?P<ano>\d{4})\s*"
    r"(?P<seq>\d{6})[\s\-]*(?P<dv>\d)\s*_?\s*$",
    re.IGNORECASE,
)

# Numero do pedido no INPI, solto no meio de um texto: "BR 10 2025 012345 6"
# ou "BR102025012345-6". So 10 (invencao) e 20 (modelo de utilidade) existem.
NUMERO_RE = re.compile(
    r"BR\s*(?P<esp>10|20)\s*(?P<ano>\d{4})\s*(?P<seq>\d{6})[\s\-]*(?P<dv>\d)",
    re.IGNORECASE,
)

# Nome do arquivo: prefixo numerico opcional, categoria, numero BR, titulo.
# O traco entre a categoria e o "BR" e opcional (a patente 48 nao tem).
ARQUIVO_RE = re.compile(
    r"^(?:\d+\s*[.\-]\s*)?\s*(?P<cat>.+?)\s*-?\s*"
    r"BR\s*\d{2}\s*\d{4}\s*\d{6}[\s\-]*\d\s*-?\s*(?P<titulo>.*)$",
    re.IGNORECASE,
)


def sem_acento(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def chave(s: str) -> str:
    """Normaliza para comparacao: sem acento, minusculo, espacos colapsados."""
    return re.sub(r"\s+", " ", sem_acento(s).lower()).strip()


def so_letras(s: str) -> str:
    """Reduz a [a-z0-9] para comparar titulos ignorando pontuacao e caixa."""
    return re.sub(r"[^a-z0-9]+", "", sem_acento(s).lower())


def slugify(s: str, limite: int = SLUG_MAX) -> str:
    s = sem_acento(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > limite:
        s = s[:limite].rstrip("-")
        # nao corta no meio de uma palavra quando da para evitar
        if "-" in s:
            s = s.rsplit("-", 1)[0]
    return s


def normaliza_espacos(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# Caracteres de controle (menos os espacos em branco, que normaliza_espacos
# resolve) e os de direcao bidirecional. Os bidi entram na lista porque
# U+202E inverte visualmente o resto da linha: um titulo pode ser escrito
# para *parecer* outra coisa na vitrine (PRD 5.7).
#
# A classe e montada a partir dos pontos de codigo em vez de escrita com os
# caracteres literais: sao todos invisiveis, e no fonte ninguem conseguiria
# revisar a lista nem notar se um deles virasse um espaco comum.
FAIXAS_INVISIVEIS = (
    (0x00, 0x08),  # controle C0 -- \t (09), \n (0A) e \r (0D) ficam de fora
    (0x0B, 0x0C),  # de proposito: normaliza_espacos os colapsa em espaco
    (0x0E, 0x1F),
    (0x7F, 0x9F),  # DEL e controle C1
    (0x200B, 0x200F),  # zero-width e marcas de direcao (LRM/RLM)
    (0x202A, 0x202E),  # embedding e override bidi
    (0x2060, 0x2064),  # word joiner e invisiveis matematicos
    (0x2066, 0x2069),  # isolates bidi
    (0xFEFF, 0xFEFF),  # BOM no meio do texto
)

_INVISIVEIS_RE = re.compile(
    "["
    + "".join(
        re.escape(chr(a)) if a == b else f"{re.escape(chr(a))}-{re.escape(chr(b))}"
        for a, b in FAIXAS_INVISIVEIS
    )
    + "]"
)


def normaliza_numero(s: str) -> str | None:
    """Acha o primeiro numero de pedido em `s` e devolve na forma canonica.

    `BR 10 2025 012345-6` -- com espacos entre os grupos e hifen antes do
    digito verificador, que e como o site mostra e como a busca indexa.
    Devolve None se nao houver numero nenhum.
    """
    m = NUMERO_RE.search(s or "")
    if not m:
        return None
    return (
        f"BR {m.group('esp')} {m.group('ano')} {m.group('seq')}-{m.group('dv')}"
    )


def limpa_texto(s: object) -> str:
    """Normaliza texto recebido de fora para guardar e publicar.

    NFC (para que "á" tenha uma unica representacao e a busca do site o
    encontre), sem caracteres invisiveis ou de direcao, espacos colapsados e
    sem sobra nas pontas. Recebe `object` de proposito: quem chama pode estar
    passando o que veio de um JSON, e um numero ou `None` nao deve explodir
    aqui -- vira texto e a validacao de tipo acontece em quem sabe o campo.
    """
    if s is None:
        return ""
    texto = unicodedata.normalize("NFC", str(s))
    return normaliza_espacos(_INVISIVEIS_RE.sub("", texto))


# --------------------------------------------------------------------------
# Nomes de arquivo e de pasta gerados pelo painel (PRD 5.7)
# --------------------------------------------------------------------------

# O titulo completo fica no patente.json; no NOME do arquivo ele e cortado,
# porque o caminho no Windows tem limite e a pasta do acervo pode estar
# alguns niveis abaixo de Documents.
TITULO_MAX_NO_NOME = 80
CAMINHO_MAX = 240

# Nomes que o Windows reserva para dispositivos. Um arquivo "CON.pdf" nao
# pode ser criado, e a mensagem de erro do sistema nao explica por que.
RESERVADOS_WINDOWS = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

# Conjunto deliberadamente estreito: letras (com acento), digitos, espaco e
# a pontuacao que aparece nos titulos reais. Tudo fora disso vira espaco --
# inclusive `/`, `\`, `:` e `..`, que e o que impede um titulo de escapar da
# pasta de destino.
_FORA_DO_PERMITIDO = re.compile(r"[^A-Za-z0-9À-ÿ .,()_\-]+")


class NomeInvalido(Exception):
    """Nao foi possivel gerar um nome de arquivo utilizavel."""


def nome_seguro(texto: object, limite: int = TITULO_MAX_NO_NOME) -> str:
    """Transforma texto livre num pedaco de nome de arquivo seguro.

    Nao e escape: e uma lista de permissoes. O que nao esta nela vira espaco
    e os espacos colapsam, entao `..\\..\\Windows` sai como `Windows` e nao
    como um caminho. Tambem tira ponto e espaco do fim, que o Windows
    silenciosamente remove ao criar o arquivo (e o nome gravado deixaria de
    bater com o esperado).
    """
    limpo = _FORA_DO_PERMITIDO.sub(" ", limpa_texto(texto))
    limpo = normaliza_espacos(limpo)
    if len(limpo) > limite:
        limpo = limpo[:limite].rstrip()
        # nao cortar no meio de uma palavra quando da para evitar
        if " " in limpo:
            limpo = limpo.rsplit(" ", 1)[0]
    limpo = limpo.rstrip(". ").lstrip(". ")
    # "con.pdf" seria recusado pelo Windows; "con_" nao
    if limpo.upper() in RESERVADOS_WINDOWS:
        limpo += "_"
    return limpo


def numero_para_pasta(numero: str) -> str:
    """`BR 10 2025 012345-6` -> `BR 10 2025 012345 6`.

    As pastas do acervo usam espaco antes do digito verificador, nao hifen.
    O formato com hifen e o canonico dos dados e do site.
    """
    m = NUMERO_RE.search(numero or "")
    if not m:
        raise NomeInvalido(f"numero de pedido invalido: {numero!r}")
    return f"BR {m.group('esp')} {m.group('ano')} {m.group('seq')} {m.group('dv')}"


def nome_pasta_patente(pid: int, numero: str) -> str:
    """`61. BR 10 2025 012345 6` -- o padrao que PASTA_RE reconhece."""
    return f"{int(pid)}. {numero_para_pasta(numero)}"


def nome_arquivo_patente(
    pid: int,
    categoria: str,
    numero: str,
    titulo: str,
    extensao: str,
    pasta: Path | str | None = None,
) -> str:
    """`61. Engenharias - BR 10 2025 012345 6 - Titulo curto.pdf`.

    Mesmo padrao que ARQUIVO_RE ja reconhece, para que o build continue
    extraindo a area e o titulo do nome como faz com as 60 pastas atuais.

    Se `pasta` for dada, o titulo e encurtado ate o caminho absoluto caber em
    CAMINHO_MAX. Um caminho longo demais falharia na hora de gravar, com um
    erro do sistema que nao diz qual foi o problema.
    """
    ext = extensao if extensao.startswith(".") else f".{extensao}"
    if _FORA_DO_PERMITIDO.sub("", ext.lstrip(".")) != ext.lstrip("."):
        raise NomeInvalido(f"extensao invalida: {extensao!r}")

    prefixo = f"{int(pid)}. {nome_seguro(categoria, 40)} - {numero_para_pasta(numero)} - "

    limite = TITULO_MAX_NO_NOME
    while True:
        nome = prefixo + nome_seguro(titulo, limite) + ext
        nome = nome.rstrip(". ") if not nome.endswith(ext) else nome
        if pasta is None:
            break
        if len(str(Path(pasta) / nome)) <= CAMINHO_MAX:
            break
        limite -= 10
        if limite < 10:
            # sem titulo nenhum o nome ainda serve: o build tira o titulo do
            # texto do PDF, e o completo esta no patente.json
            nome = prefixo.rstrip(" -") + ext
            if len(str(Path(pasta) / nome)) > CAMINHO_MAX:
                raise NomeInvalido(
                    "o caminho da pasta do acervo e longo demais para gravar "
                    "os arquivos desta patente. Mova o acervo para uma pasta "
                    "mais perto da raiz do disco."
                )
            break
    return nome
