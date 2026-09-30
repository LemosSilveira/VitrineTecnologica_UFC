# -*- coding: utf-8 -*-
"""Leitura do conteudo das fichas tecnicas em PDF.

As 60 fichas seguem o mesmo template da UFC Inova: um titulo grande e cinco
secoes com cabecalhos fixos. O que varia sao as quebras de linha, os
marcadores dos diferenciais e o fato de o texto sair do PDF na ordem do
fluxo, nao na ordem visual -- dai a reconstrucao por posicao em
`titulo_do_pdf`.

Os caracteres nao-ASCII que entram na saida (travessao do TRL, reticencias
do resumo, hifen condicional) ficam em constantes nomeadas no topo, com o
ponto de codigo no comentario. A saida do build e comparada byte a byte, e
um hifen condicional -- que e invisivel -- trocado por engano num editor
nao apareceria em nenhuma revisao de codigo.
"""
from __future__ import annotations

import re

from .nomes import (
    ARQUIVO_RE,
    chave,
    normaliza_espacos,
    normaliza_numero,
    so_letras,
)

__all__ = [
    "SECOES",
    "TRL_RE",
    "RESUMO_MAX",
    "PDF",
    "NOME_ARQUIVO",
    "NAO_ENCONTRADO",
    "le_pagina1",
    "titulo_do_pdf",
    "secoes_do_pdf",
    "limpa_paragrafo",
    "limpa_diferenciais",
    "faz_resumo",
    "parse_trl",
    "ler_ficha",
    "ler_texto",
]

# Cabecalhos das secoes da ficha, na ordem em que aparecem no template.
SECOES = [
    ("oQueE", "O que é?"),
    ("problema", "Problema que resolve"),
    ("exemploDeUso", "Exemplo de uso"),
    ("diferenciais", "Diferenciais competitivos"),
    ("beneficio", "Benefício principal"),
    ("_trl", "Nível de maturidade"),
]

# – travessao curto, — travessao longo: as fichas usam os dois.
TRL_RE = re.compile(r"TRL\s*(\d)(?:\s*[–—\-]\s*(\d))?", re.IGNORECASE)

RESUMO_MAX = 160

_HIFEN_CONDICIONAL = "­"  # soft hyphen — invisivel, o PDF insere nas quebras
_RETICENCIAS = "…"  # … no fim do resumo cortado
_TRAVESSAO = "–"  # – entre o min e o max do TRL
_MARCADORES = ("✅", "✔", "☑", "▪", "•", "-")


def le_pagina1(pdf_path) -> tuple[str, str, int]:
    """Abre o PDF uma vez e devolve (titulo, texto da pagina 1, n de paginas).

    Concentrar a abertura aqui evita abrir o mesmo arquivo duas vezes por
    patente e deixa um unico ponto para a validacao de PDF da Fase 2.
    """
    import pymupdf

    doc = pymupdf.open(pdf_path)
    try:
        n = len(doc)
        page = doc[0]
        return titulo_do_pdf(page), page.get_text("text"), n
    finally:
        doc.close()


def titulo_do_pdf(page) -> str:
    """Titulo = o maior corpo de texto da pagina.

    Verificado nas 60 fichas: o titulo e sempre o maior tamanho de fonte e
    nunca colide com um cabecalho de secao. Mais robusto que a ordem do
    fluxo de texto, em que o titulo sai por ultimo (depois do TRL).
    """
    data = page.get_text("dict")

    maior = 0.0
    for blk in data["blocks"]:
        if blk.get("type") != 0:
            continue
        for line in blk["lines"]:
            for sp in line["spans"]:
                if sp["text"].strip():
                    maior = max(maior, round(sp["size"], 1))
    if not maior:
        return ""

    linhas: list[tuple[float, float, str]] = []
    for blk in data["blocks"]:
        if blk.get("type") != 0:
            continue
        for line in blk["lines"]:
            spans = [sp for sp in line["spans"] if round(sp["size"], 1) == maior]
            if not any(sp["text"].strip() for sp in spans):
                continue
            # Spans da mesma linha sao contiguos: juntar SEM separador.
            # E o que reconstroi "(τf" quando o tau vem de outra fonte.
            txt = "".join(sp["text"] for sp in spans)
            linhas.append((round(line["bbox"][1], 1), round(line["bbox"][0], 1), txt))

    linhas.sort(key=lambda t: (t[0], t[1]))

    out = ""
    for _, _, txt in linhas:
        t = txt.strip()
        if not t:
            continue
        if not out:
            out = t
        elif out.endswith("-"):
            out += t  # palavra hifenizada quebrada na linha: "micro-" + "ondas"
        else:
            out += " " + t
    return normaliza_espacos(out)


def secoes_do_pdf(texto: str) -> tuple[dict, list[str]]:
    """Fatia o texto da pagina pelos cabecalhos conhecidos."""
    avisos: list[str] = []
    achados: list[tuple[int, int, str, str]] = []

    for campo, cabecalho in SECOES:
        m = re.search(re.escape(cabecalho), texto)
        if m:
            achados.append((m.start(), m.end(), campo, cabecalho))
        else:
            avisos.append(f"secao nao encontrada: {cabecalho}")

    achados.sort()
    bruto: dict[str, str] = {}
    for i, (_ini, fim, campo, _cab) in enumerate(achados):
        prox = achados[i + 1][0] if i + 1 < len(achados) else len(texto)
        bruto[campo] = texto[fim:prox].strip()

    return bruto, avisos


def limpa_paragrafo(s: str) -> str:
    """Junta as quebras de linha do PDF num paragrafo continuo."""
    s = s.replace(_HIFEN_CONDICIONAL, "")
    linhas = [ln.strip() for ln in s.splitlines()]
    linhas = [ln for ln in linhas if ln]
    out = ""
    for ln in linhas:
        if not out:
            out = ln
        elif out.endswith("-"):
            out += ln
        else:
            out += " " + ln
    return normaliza_espacos(out)


def limpa_diferenciais(s: str) -> list[str]:
    """Um item por marcador. Remove o emoji e a pontuacao final solta."""
    itens: list[str] = []
    atual = ""
    for ln in s.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith(_MARCADORES):
            if atual:
                itens.append(atual)
            atual = re.sub(r"^[✅✔☑▪•\-]\s*", "", ln)
        elif atual:
            atual += " " + ln
        else:
            atual = ln
    if atual:
        itens.append(atual)

    limpos: list[str] = []
    for it in itens:
        it = normaliza_espacos(it).rstrip(";").strip()
        if it:
            limpos.append(it)
    return limpos


def faz_resumo(texto: str, limite: int = RESUMO_MAX) -> str:
    texto = normaliza_espacos(texto)
    if len(texto) <= limite:
        return texto
    corte = texto[:limite]
    if " " in corte:
        corte = corte.rsplit(" ", 1)[0]
    return corte.rstrip(" ,;:.-") + _RETICENCIAS


def parse_trl(trecho: str) -> dict | None:
    m = TRL_RE.search(trecho)
    if not m:
        return None
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    if hi < lo:
        lo, hi = hi, lo
    estimado = "estimad" in chave(trecho)
    if lo == hi:
        texto = f"TRL {lo}"
    else:
        texto = f"TRL {lo}{_TRAVESSAO}{hi}"
    if estimado:
        texto += " (estimado)"
    return {"min": lo, "max": hi, "estimado": estimado, "texto": texto}


# --------------------------------------------------------------------------
# Preenchimento automatico do formulario do painel (PRD 6.2)
# --------------------------------------------------------------------------

PDF = "pdf"
NOME_ARQUIVO = "nome_arquivo"
NAO_ENCONTRADO = "nao_encontrado"


def _campo(valor, origem: str) -> dict:
    """Um campo do formulario com a procedencia do que foi preenchido.

    A interface mostra "✦ do PDF" ou "✦ do nome do arquivo" ao lado do campo,
    e sinaliza o que nao achou para a pessoa preencher a mao. Sem a origem, a
    equipe nao teria como saber o que conferir (PRD 7.4).
    """
    vazio = valor is None or valor == "" or valor == []
    return {"valor": valor, "origem": NAO_ENCONTRADO if vazio else origem}


def _secoes_com_origem(bruto: dict, origem: str) -> dict:
    return {
        "oQueE": _campo(limpa_paragrafo(bruto.get("oQueE") or "") or None, origem),
        "problema": _campo(limpa_paragrafo(bruto.get("problema") or "") or None, origem),
        "exemploDeUso": _campo(
            limpa_paragrafo(bruto.get("exemploDeUso") or "") or None, origem
        ),
        "diferenciais": _campo(
            limpa_diferenciais(bruto.get("diferenciais") or "") or None, origem
        ),
        "beneficio": _campo(limpa_paragrafo(bruto.get("beneficio") or "") or None, origem),
    }


def ler_texto(texto: str) -> dict:
    """Extrai os campos da ficha de um texto colado.

    Alternativa para quem tem o conteudo mas nao o arquivo -- copiou da tela
    do leitor de PDF, por exemplo. Sem o arquivo nao ha nome de arquivo, e
    portanto nao ha como deduzir a area tecnologica.
    """
    texto = texto or ""
    bruto, _ = secoes_do_pdf(texto)
    trl = parse_trl(bruto.get("_trl", "") or "")
    return {
        "numero": _campo(normaliza_numero(texto), PDF),
        "categoria": _campo(None, NAO_ENCONTRADO),
        "titulo": _campo(None, NAO_ENCONTRADO),
        "secoes": _secoes_com_origem(bruto, PDF),
        "trl": _campo(trl, PDF),
    }


def ler_ficha(caminho_pdf, categorias: dict[str, str] | None = None) -> dict:
    """Extrai os campos da ficha de um PDF, com a origem de cada um.

    Reaproveita a mesma extracao do build, mais duas deducoes que o build
    tirava do nome da pasta e que aqui nao existem ainda:

    - **numero** do pedido, procurado no texto do PDF e, se nao achar, no
      nome do arquivo;
    - **area tecnologica**, pelo nome do arquivo e pelo mapa de categorias.

    Quem chama precisa ter validado o PDF antes (`pdf_seguro.valida`).
    """
    from pathlib import Path

    caminho = Path(caminho_pdf)
    nome = normaliza_espacos(caminho.stem)

    titulo_pdf, texto, n_paginas = le_pagina1(caminho)
    bruto, _ = secoes_do_pdf(texto)

    # ---- numero: PDF primeiro, nome do arquivo como reserva ----
    numero, origem_numero = normaliza_numero(texto), PDF
    if not numero:
        numero, origem_numero = normaliza_numero(nome), NOME_ARQUIVO

    # ---- categoria e titulo pelo nome do arquivo ----
    categoria = None
    titulo_arquivo = ""
    m = ARQUIVO_RE.match(nome)
    if m:
        bruta = m.group("cat").strip(" -")
        titulo_arquivo = re.sub(r"pdf$", "", m.group("titulo").strip()).strip()
        titulo_arquivo = titulo_arquivo.strip("_").strip()
        if categorias:
            categoria = categorias.get(chave(bruta))

    # ---- titulo: mesma regra do build ----
    titulo, origem_titulo = titulo_pdf, PDF
    if not titulo:
        titulo, origem_titulo = titulo_arquivo, NOME_ARQUIVO
    elif titulo_arquivo:
        a, b = so_letras(titulo_pdf), so_letras(titulo_arquivo)
        if a != b and a in b:
            # PDF truncado no design: o nome do arquivo e mais completo
            titulo, origem_titulo = titulo_arquivo, NOME_ARQUIVO
    if titulo and titulo.isupper():
        titulo = titulo.capitalize()

    return {
        "numero": _campo(numero, origem_numero),
        "categoria": _campo(categoria, NOME_ARQUIVO),
        "titulo": _campo(titulo or None, origem_titulo),
        "secoes": _secoes_com_origem(bruto, PDF),
        "trl": _campo(parse_trl(bruto.get("_trl", "") or ""), PDF),
        "paginas": n_paginas,
    }
