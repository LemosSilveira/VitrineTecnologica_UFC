#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline de dados da Vitrine de Patentes UFC.

Le a pasta de origem com as 60 subpastas de patentes (1 PDF + 1 imagem cada),
extrai o conteudo das fichas tecnicas, otimiza as imagens e gera:

  js/data/patentes.js     window.PATENTES / window.CATEGORIAS
  assets/patentes/<slug>/ capa-400.webp, capa-800.webp,
                          ficha-600.webp, ficha-1620.webp, ficha.pdf
  scripts/build_report.md relatorio do build

Uso:
    python scripts/build_patentes.py --src "<pasta de origem>" --out .

O script SO LE a pasta de origem: nunca renomeia, move ou apaga os originais.
E idempotente -- arquivos de saida so sao reescritos quando o conteudo muda,
entao rodar duas vezes nao altera nenhum byte nem mtime.

Dependencias: pip install pymupdf pillow
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover
    sys.exit("PyMuPDF nao instalado. Rode: pip install pymupdf pillow")

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow nao instalado. Rode: pip install pymupdf pillow")


# --------------------------------------------------------------------------
# Constantes de dominio
# --------------------------------------------------------------------------

IMG_EXTS = {".png", ".jpg", ".jpeg"}

# Mapa de normalizacao de categorias (PRD 2.4). Chave = como aparece no
# arquivo (comparada sem acento/caixa); valor = nome exibido no site.
CATEGORIA_MAP = {
    "alimentos": "Alimentos",
    "agropecuaria": "Agropecuária",
    "tic": "TIC",
    "engenharias": "Engenharias",
    "biotecnologia": "Biotecnologia",
    "ciencias da saude": "Ciências da Saúde",
    "industria": "Indústria",
    "quimico": "Química",
    "quimicos": "Química",
    "cosmetico": "Cosméticos",
    "cosmeticos": "Cosméticos",
    "energia e meio ambiente": "Energia e Meio Ambiente",
}

TIPOS = {
    "10": {"sigla": "PI", "nome": "Patente de Invenção"},
    "20": {"sigla": "MU", "nome": "Modelo de Utilidade"},
}

# Cabecalhos das secoes da ficha, na ordem em que aparecem no template.
SECOES = [
    ("oQueE", "O que é?"),
    ("problema", "Problema que resolve"),
    ("exemploDeUso", "Exemplo de uso"),
    ("diferenciais", "Diferenciais competitivos"),
    ("beneficio", "Benefício principal"),
    ("_trl", "Nível de maturidade"),
]

# Nome da pasta: "19. BR 10 2022 019303 7" (com "_" final em algumas).
PASTA_RE = re.compile(
    r"^(?P<id>\d+)\s*\.\s*(?P<pais>BR)\s*(?P<esp>\d{2})\s*(?P<ano>\d{4})\s*"
    r"(?P<seq>\d{6})[\s\-]*(?P<dv>\d)\s*_?\s*$",
    re.IGNORECASE,
)

# Nome do arquivo: prefixo numerico opcional, categoria, numero BR, titulo.
# O traco entre categoria e "BR" e opcional (a patente 48 nao tem).
ARQUIVO_RE = re.compile(
    r"^(?:\d+\s*[.\-]\s*)?\s*(?P<cat>.+?)\s*-?\s*"
    r"BR\s*\d{2}\s*\d{4}\s*\d{6}[\s\-]*\d\s*-?\s*(?P<titulo>.*)$",
    re.IGNORECASE,
)

TRL_RE = re.compile(r"TRL\s*(\d)(?:\s*[–—\-]\s*(\d))?", re.IGNORECASE)

RESUMO_MAX = 160
SLUG_MAX = 80

WEBP_CAPA_Q = 82
WEBP_FICHA_LG_Q = 85
WEBP_FICHA_SM_Q = 80
CAPA_LARGURAS = (400, 800)
FICHA_ZOOM = 2.0  # 810x1012.5pt -> 1620x2025 px
FICHA_SM_LARGURA = 600


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

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


def write_if_changed(path: Path, data: bytes) -> bool:
    """Escreve so se o conteudo mudou. Garante idempotencia (mtime estavel)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def js_string(s: str) -> str:
    """Literal JS seguro, com escape de aspas, barras, quebras e U+2028/9."""
    out = (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
        .replace("</", "<\\/")  # nao fecha um <script> por acidente
    )
    return f'"{out}"'


# --------------------------------------------------------------------------
# Extracao do PDF
# --------------------------------------------------------------------------

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
    s = s.replace("­", "")  # hifen condicional
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
        if ln.startswith(("✅", "✔", "☑", "▪", "•", "-")):
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
    return corte.rstrip(" ,;:.-") + "…"


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
        texto = f"TRL {lo}–{hi}"
    if estimado:
        texto += " (estimado)"
    return {"min": lo, "max": hi, "estimado": estimado, "texto": texto}


# --------------------------------------------------------------------------
# Imagens
# --------------------------------------------------------------------------

def webp_bytes(img: Image.Image, qualidade: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=qualidade, method=6)
    return buf.getvalue()


def gera_capas(origem: Path, destino: Path) -> tuple[dict[str, str], list[int], int]:
    """Gera capa-400/800.webp. Nao amplia imagens menores que o alvo."""
    with Image.open(origem) as im:
        im = im.convert("RGB")
        larg, alt = im.size
        saidas: dict[str, str] = {}
        bytes_saida = 0
        for alvo in CAPA_LARGURAS:
            if larg <= alvo:
                novo = im.copy()  # sem upscale
            else:
                h = max(1, round(alt * alvo / larg))
                novo = im.resize((alvo, h), Image.LANCZOS)
            nome = f"capa-{alvo}.webp"
            write_if_changed(destino / nome, webp_bytes(novo, WEBP_CAPA_Q))
            bytes_saida += (destino / nome).stat().st_size
            saidas[f"capa{alvo}"] = nome
            if alvo == CAPA_LARGURAS[-1]:
                dims = list(novo.size)
            novo.close()
    return saidas, dims, bytes_saida


def gera_ficha(pdf_path: Path, destino: Path) -> tuple[dict[str, str], int]:
    """Renderiza a pagina 1 do PDF em 2x -> ficha-1620.webp e ficha-600.webp."""
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(FICHA_ZOOM, FICHA_ZOOM), alpha=False)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()

    bytes_saida = 0
    saidas: dict[str, str] = {}

    nome_lg = f"ficha-{pix.width}.webp"
    write_if_changed(destino / nome_lg, webp_bytes(im, WEBP_FICHA_LG_Q))
    bytes_saida += (destino / nome_lg).stat().st_size
    saidas["ficha1620"] = nome_lg

    h = max(1, round(im.height * FICHA_SM_LARGURA / im.width))
    pequeno = im.resize((FICHA_SM_LARGURA, h), Image.LANCZOS)
    nome_sm = f"ficha-{FICHA_SM_LARGURA}.webp"
    write_if_changed(destino / nome_sm, webp_bytes(pequeno, WEBP_FICHA_SM_Q))
    bytes_saida += (destino / nome_sm).stat().st_size
    saidas["ficha600"] = nome_sm

    pequeno.close()
    im.close()
    return saidas, bytes_saida


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------

@dataclass
class Resultado:
    patentes: list[dict] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    ignorados: list[str] = field(default_factory=list)
    bytes_origem: int = 0
    bytes_saida: int = 0


# --------------------------------------------------------------------------
# Processamento de uma pasta
# --------------------------------------------------------------------------

def processa(pasta: Path, out_root: Path, res: Resultado) -> dict | None:
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
    pdfs = sorted(f for f in pasta.iterdir() if f.is_file() and f.suffix.lower() == ".pdf")
    imgs = sorted(f for f in pasta.iterdir() if f.is_file() and f.suffix.lower() in IMG_EXTS)
    outros = sorted(
        f for f in pasta.iterdir()
        if f.is_file() and f.suffix.lower() != ".pdf" and f.suffix.lower() not in IMG_EXTS
    )
    for f in outros:
        res.ignorados.append(f"[{pid}] ignorado: `{f.name}`")
    for f in pdfs[1:] + imgs[1:]:
        res.ignorados.append(f"[{pid}] extra ignorado: `{f.name}`")

    if not pdfs:
        res.erros.append(f"[{pid}] sem PDF -- patente fora da vitrine.")
        return None
    if not imgs:
        res.erros.append(f"[{pid}] sem imagem de capa -- patente fora da vitrine.")
        return None

    pdf_src, img_src = pdfs[0], imgs[0]
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

    categoria = CATEGORIA_MAP.get(chave(categoria_bruta))
    if categoria is None:
        res.erros.append(
            f"[{pid}] categoria fora do mapa: `{categoria_bruta or '(vazia)'}` "
            f"(arquivo: `{pdf_src.name}`). Adicione ao CATEGORIA_MAP."
        )
        return None

    # ---- conteudo do PDF ----
    doc = pymupdf.open(pdf_src)
    if len(doc) != 1:
        res.avisos.append(f"[{pid}] o PDF tem {len(doc)} paginas; usando a primeira.")
    page = doc[0]
    titulo_pdf = titulo_do_pdf(page)
    texto = page.get_text("text")
    doc.close()

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
        res.avisos.append(f"[{pid}] titulo estava em MAIUSCULAS; convertido para caixa de frase.")

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
# Serializacao
# --------------------------------------------------------------------------

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
# main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Gera os dados da Vitrine de Patentes UFC.")
    ap.add_argument("--src", required=True, help="pasta de origem com as subpastas das patentes")
    ap.add_argument("--out", default=".", help="raiz do site (padrao: diretorio atual)")
    args = ap.parse_args()

    src = Path(args.src).expanduser()
    out = Path(args.out).expanduser().resolve()
    if not src.is_dir():
        print(f"ERRO: pasta de origem nao encontrada: {src}", file=sys.stderr)
        return 2

    res = Resultado()
    pastas = sorted(
        (d for d in src.iterdir() if d.is_dir()),
        key=lambda p: int(m.group(1)) if (m := re.match(r"^(\d+)", p.name)) else 10**6,
    )
    print(f"Processando {len(pastas)} pastas de `{src}`...")
    for d in pastas:
        p = processa(d, out, res)
        if p:
            res.patentes.append(p)
            print(f"  [{p['id']:2d}] {p['categoria']:24s} {p['titulo'][:58]}")

    res.patentes.sort(key=lambda p: p["id"])

    cont = Counter(p["categoria"] for p in res.patentes)
    categorias = [
        {"nome": n, "total": cont[n]}
        for n in sorted(cont, key=lambda s: sem_acento(s).lower())
    ]

    # ---- saidas ----
    js = serializa(res.patentes, categorias)
    mudou_js = write_if_changed(out / "js" / "data" / "patentes.js", js.encode("utf-8"))

    capas_400 = sum(
        (out / p["imagens"]["capa400"]).stat().st_size
        for p in res.patentes
        if (out / p["imagens"]["capa400"]).exists()
    )
    rel = relatorio(res, categorias, src, capas_400)
    write_if_changed(out / "scripts" / "build_report.md", rel.encode("utf-8"))

    print()
    print(f"  patentes .......... {len(res.patentes)}")
    print(f"  categorias ........ {len(categorias)}")
    print(f"  erros ............. {len(res.erros)}")
    print(f"  avisos ............ {len(res.avisos)}")
    print(f"  ignorados ......... {len(res.ignorados)}")
    print(f"  peso origem ....... {mb(res.bytes_origem)}")
    print(f"  peso saida ........ {mb(res.bytes_saida)}")
    print(f"  soma capa-400 ..... {mb(capas_400)}")
    print(f"  patentes.js ....... {'atualizado' if mudou_js else 'sem mudanca'}")

    if res.erros:
        print("\nERROS:", file=sys.stderr)
        for e in res.erros:
            print("  - " + e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
