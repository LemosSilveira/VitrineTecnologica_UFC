# -*- coding: utf-8 -*-
"""O build completo: acervo -> patentes.js + assets + relatorio.

`roda_build()` e o unico ponto de entrada. A CLI
(`scripts/build_patentes.py`) e o painel chamam esta mesma funcao, para que
nao existam dois caminhos de codigo capazes de divergir.

O progresso sai por um callback em vez de `print`, porque o painel mostra as
mesmas etapas numa janela, nao num terminal.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .acervo import TIPOS, arquivos_da_pasta, carrega_categorias, lista_pastas
from .extracao import (
    faz_resumo,
    le_pagina1,
    limpa_diferenciais,
    limpa_paragrafo,
    parse_trl,
    secoes_do_pdf,
)
from .imagens import gera_capas, gera_ficha
from .io_seguro import write_if_changed
from .nomes import (
    ARQUIVO_RE,
    PASTA_RE,
    SLUG_MAX,
    chave,
    normaliza_espacos,
    sem_acento,
    slugify,
    so_letras,
)

__all__ = ["Resultado", "roda_build", "processa", "serializa", "relatorio", "js_string"]


@dataclass
class Resultado:
    patentes: list[dict] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    ignorados: list[str] = field(default_factory=list)
    bytes_origem: int = 0
    bytes_saida: int = 0
    categorias: list[dict] = field(default_factory=list)
    capas_400: int = 0
    js_mudou: bool = False


# --------------------------------------------------------------------------
# Serializacao
# --------------------------------------------------------------------------

def js_string(s: str) -> str:
    """Literal JS seguro, com escape de aspas, barras, quebras e U+2028/9.

    U+2028 e U+2029 sao quebras de linha para o parser de JavaScript, mesmo
    dentro de uma string: sem escapar, um desses caracteres vindo de uma
    ficha quebraria o `patentes.js` inteiro. O `</` vira `<\\/` para que um
    texto com "</script>" nao feche a tag que carrega o arquivo.
    """
    out = (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
        .replace("</", "<\\/")
    )
    return f'"{out}"'


def serializa(patentes: list[dict], categorias: list[dict]) -> str:
    def val(v, ind: int) -> str:
        pad = "  " * ind
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str):
            return js_string(v)
        if isinstance(v, list):
            if not v:
                return "[]"
            if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
                return "[" + ", ".join(str(x) for x in v) + "]"
            itens = ",\n".join(f"{pad}  {val(x, ind + 1)}" for x in v)
            return "[\n" + itens + f"\n{pad}]"
        if isinstance(v, dict):
            if not v:
                return "{}"
            itens = ",\n".join(f"{pad}  {k}: {val(x, ind + 1)}" for k, x in v.items())
            return "{\n" + itens + f"\n{pad}}}"
        raise TypeError(type(v))

    linhas = [
        "/* ARQUIVO GERADO por scripts/build_patentes.py -- nao editar a mao.",
        " * Para atualizar: python scripts/build_patentes.py --src \"<origem>\" --out .",
        " * Carregado como script classico (sem modulos) para funcionar via file://.",
        " */",
        "window.PATENTES = [",
    ]
    for p in patentes:
        linhas.append("  " + val(p, 1) + ",")
    linhas.append("];")
    linhas.append("")
    linhas.append("window.CATEGORIAS = [")
    for c in categorias:
        linhas.append(f"  {{ nome: {js_string(c['nome'])}, total: {c['total']} }},")
    linhas.append("];")
    linhas.append("")
    return "\n".join(linhas)


# --------------------------------------------------------------------------
# Processamento de uma pasta
# --------------------------------------------------------------------------

def processa(
    pasta: Path,
    out_root: Path,
    res: Resultado,
    categoria_map: dict[str, str],
) -> dict | None:
    nome = normaliza_espacos(pasta.name)
    m = PASTA_RE.match(nome)
    if not m:
        res.erros.append(f"`{pasta.name}`: nome de pasta fora do padrao esperado.")
        return None

    pid = int(m.group("id"))
    esp, ano, seq, dv = m.group("esp"), m.group("ano"), m.group("seq"), m.group("dv")
    numero = f"BR {esp} {ano} {seq}-{dv}"

    tipo = TIPOS.get(esp)
    if tipo is None:
        res.erros.append(f"[{pid}] especie INPI desconhecida: BR {esp}.")
        return None

    # ---- arquivos ----
    arqs = arquivos_da_pasta(pasta)
    for f in arqs.outros:
        res.ignorados.append(f"[{pid}] ignorado: `{f.name}`")
    for f in arqs.pdfs[1:] + arqs.imagens[1:]:
        res.ignorados.append(f"[{pid}] extra ignorado: `{f.name}`")

    if not arqs.pdfs:
        res.erros.append(f"[{pid}] sem PDF -- patente fora da vitrine.")
        return None
    if not arqs.imagens:
        res.erros.append(f"[{pid}] sem imagem de capa -- patente fora da vitrine.")
        return None

    pdf_src, img_src = arqs.pdfs[0], arqs.imagens[0]
    res.bytes_origem += pdf_src.stat().st_size + img_src.stat().st_size

    # ---- categoria e titulo pelo nome do arquivo ----
    categoria_bruta = ""
    titulo_arquivo = ""
    mm = ARQUIVO_RE.match(normaliza_espacos(pdf_src.stem))
    if mm:
        categoria_bruta = mm.group("cat").strip(" -")
        titulo_arquivo = mm.group("titulo").strip()
    if not categoria_bruta:  # ultima tentativa: nome da imagem
        mi = ARQUIVO_RE.match(normaliza_espacos(img_src.stem))
        if mi:
            categoria_bruta = mi.group("cat").strip(" -")

    # "...Analisepdf.pdf" -> tira o "pdf" sobrando; "...albumina_" -> tira o "_"
    titulo_arquivo = re.sub(r"pdf$", "", titulo_arquivo).strip()
    titulo_arquivo = titulo_arquivo.strip("_").strip()

    categoria = categoria_map.get(chave(categoria_bruta))
    if categoria is None:
        res.erros.append(
            f"[{pid}] categoria fora do mapa: `{categoria_bruta or '(vazia)'}` "
            f"(arquivo: `{pdf_src.name}`). Adicione em dados/categorias.json."
        )
        return None

    # ---- conteudo do PDF ----
    titulo_pdf, texto, n_paginas = le_pagina1(pdf_src)
    if n_paginas != 1:
        res.avisos.append(f"[{pid}] o PDF tem {n_paginas} paginas; usando a primeira.")

    bruto, avisos_sec = secoes_do_pdf(texto)
    for a in avisos_sec:
        res.avisos.append(f"[{pid}] {a}")

    # Titulo canonico: o do PDF (caixa correta -- corrige o MAIUSCULAS da 52).
    # Excecao: quando o nome do arquivo CONTEM o titulo do PDF, o PDF foi
    # truncado no design (caso da 4) e o nome do arquivo e mais completo.
    titulo = titulo_pdf or titulo_arquivo
    if titulo_pdf and titulo_arquivo:
        a, b = so_letras(titulo_pdf), so_letras(titulo_arquivo)
        if a != b and a in b:
            titulo = titulo_arquivo
            res.avisos.append(
                f"[{pid}] titulo do PDF truncado (`{titulo_pdf}`); "
                f"usando o do arquivo (`{titulo_arquivo}`)."
            )
    if not titulo:
        res.erros.append(f"[{pid}] sem titulo no PDF nem no nome do arquivo.")
        return None
    if titulo.isupper():
        titulo = titulo.capitalize()
        res.avisos.append(
            f"[{pid}] titulo estava em MAIUSCULAS; convertido para caixa de frase."
        )

    secoes = {
        "oQueE": limpa_paragrafo(bruto["oQueE"]) if bruto.get("oQueE") else None,
        "problema": limpa_paragrafo(bruto["problema"]) if bruto.get("problema") else None,
        "exemploDeUso": limpa_paragrafo(bruto["exemploDeUso"]) if bruto.get("exemploDeUso") else None,
        "diferenciais": limpa_diferenciais(bruto["diferenciais"]) if bruto.get("diferenciais") else None,
        "beneficio": limpa_paragrafo(bruto["beneficio"]) if bruto.get("beneficio") else None,
    }
    if not secoes["diferenciais"]:
        secoes["diferenciais"] = None

    trl = parse_trl(bruto.get("_trl", "") or "")
    if trl is None:
        res.avisos.append(f"[{pid}] TRL nao encontrado.")

    resumo = faz_resumo(secoes["oQueE"]) if secoes["oQueE"] else faz_resumo(titulo)

    # ---- saida ----
    slug = f"{pid}-{slugify(titulo, SLUG_MAX - len(str(pid)) - 1)}"
    destino = out_root / "assets" / "patentes" / slug
    destino.mkdir(parents=True, exist_ok=True)

    capas, dims, b1 = gera_capas(img_src, destino)
    fichas, b2 = gera_ficha(pdf_src, destino)
    write_if_changed(destino / "ficha.pdf", pdf_src.read_bytes())
    b3 = (destino / "ficha.pdf").stat().st_size
    res.bytes_saida += b1 + b2 + b3

    base = f"assets/patentes/{slug}"
    return {
        "id": pid,
        "slug": slug,
        "numero": numero,
        "ano": int(ano),
        "tipo": tipo,
        "categoria": categoria,
        "titulo": titulo,
        "resumo": resumo,
        "secoes": secoes,
        "trl": trl,
        "imagens": {
            "capa400": f"{base}/{capas['capa400']}",
            "capa800": f"{base}/{capas['capa800']}",
            "ficha600": f"{base}/{fichas['ficha600']}",
            "ficha1620": f"{base}/{fichas['ficha1620']}",
            "dimensoesCapa": dims,
        },
        "pdf": f"{base}/ficha.pdf",
    }


# --------------------------------------------------------------------------
# Relatorio
# --------------------------------------------------------------------------

def mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def relatorio(res: Resultado, categorias: list[dict], src: Path, capas_400: int) -> str:
    tipos = Counter(p["tipo"]["sigla"] for p in res.patentes)
    anos = Counter(p["ano"] for p in res.patentes)
    L: list[str] = []
    A = L.append

    A("# Relatorio de build -- Vitrine de Patentes UFC")
    A("")
    A("> Gerado por `scripts/build_patentes.py`. Nao editar a mao.")
    A("")
    A(f"- **Pasta de origem:** `{src}`")
    A(f"- **Patentes processadas:** {len(res.patentes)}")
    A(f"- **Erros:** {len(res.erros)}")
    A(f"- **Avisos:** {len(res.avisos)}")
    A(f"- **Arquivos ignorados:** {len(res.ignorados)}")
    A("")
    A("## Peso")
    A("")
    A("| | Antes | Depois |")
    A("|---|---|---|")
    A(f"| PDFs + imagens de origem | {mb(res.bytes_origem)} | {mb(res.bytes_saida)} |")
    A("")
    A(f"- Soma das `capa-400.webp`: **{mb(capas_400)}** (meta do PRD: < 4 MB) "
      f"{'OK' if capas_400 < 4 * 1024 * 1024 else 'ACIMA DA META'}")
    A("")
    A("## Por categoria")
    A("")
    A("| Area tecnologica | Patentes |")
    A("|---|---|")
    for c in categorias:
        A(f"| {c['nome']} | {c['total']} |")
    A(f"| **Total** | **{len(res.patentes)}** |")
    A("")
    A("## Por tipo de protecao")
    A("")
    A("| Tipo | Sigla | Patentes |")
    A("|---|---|---|")
    A(f"| Patente de Invencao | PI | {tipos.get('PI', 0)} |")
    A(f"| Modelo de Utilidade | MU | {tipos.get('MU', 0)} |")
    A("")
    A("## Por ano de deposito")
    A("")
    A("| Ano | Patentes |")
    A("|---|---|")
    for ano in sorted(anos):
        A(f"| {ano} | {anos[ano]} |")
    A("")

    A("## Erros")
    A("")
    if res.erros:
        for e in res.erros:
            A(f"- {e}")
    else:
        A("Nenhum.")
    A("")

    A("## Avisos")
    A("")
    if res.avisos:
        for a in res.avisos:
            A(f"- {a}")
    else:
        A("Nenhum.")
    A("")

    A("## Arquivos ignorados")
    A("")
    if res.ignorados:
        for i in res.ignorados:
            A(f"- {i}")
    else:
        A("Nenhum.")
    A("")

    A("## Inventario")
    A("")
    A("| ID | Numero | Tipo | Categoria | TRL | Titulo |")
    A("|---|---|---|---|---|---|")
    for p in res.patentes:
        trl = p["trl"]["texto"] if p["trl"] else "--"
        A(f"| {p['id']} | `{p['numero']}` | {p['tipo']['sigla']} | {p['categoria']} "
          f"| {trl} | {p['titulo']} |")
    A("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# Build completo
# --------------------------------------------------------------------------

def roda_build(
    src: Path,
    out: Path,
    categorias_json: Path | None = None,
    ao_processar: Callable[[dict], None] | None = None,
    ao_comecar: Callable[[int], None] | None = None,
) -> Resultado:
    """Le o acervo em `src` e escreve a vitrine em `out`.

    `ao_comecar(n_pastas)` e `ao_processar(patente)` existem para que a CLI
    imprima no terminal e o painel mostre as mesmas etapas numa janela, sem
    que este modulo precise saber qual dos dois esta chamando.
    """
    categoria_map = carrega_categorias(categorias_json)

    res = Resultado()
    pastas = lista_pastas(src)
    if ao_comecar:
        ao_comecar(len(pastas))

    for d in pastas:
        p = processa(d, out, res, categoria_map)
        if p:
            res.patentes.append(p)
            if ao_processar:
                ao_processar(p)

    res.patentes.sort(key=lambda p: p["id"])

    cont = Counter(p["categoria"] for p in res.patentes)
    res.categorias = [
        {"nome": n, "total": cont[n]}
        for n in sorted(cont, key=lambda s: sem_acento(s).lower())
    ]

    js = serializa(res.patentes, res.categorias)
    res.js_mudou = write_if_changed(out / "js" / "data" / "patentes.js", js.encode("utf-8"))

    res.capas_400 = sum(
        (out / p["imagens"]["capa400"]).stat().st_size
        for p in res.patentes
        if (out / p["imagens"]["capa400"]).exists()
    )
    rel = relatorio(res, res.categorias, src, res.capas_400)
    write_if_changed(out / "scripts" / "build_report.md", rel.encode("utf-8"))

    return res
