#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline de dados da Vitrine de Patentes UFC.

Le uma ou mais pastas de origem (uma subpasta por patente, com 1 PDF + 1
imagem cada), extrai o conteudo das fichas tecnicas, otimiza as imagens e
gera:

  js/data/patentes.js       window.PATENTES / window.CATEGORIAS
  assets/patentes/<slug>/   capa-400.webp, capa-800.webp,
                            ficha-600.webp, ficha-1620.webp, ficha.pdf
  dados/ids_patentes.json   registro permanente numero INPI -> ID
  scripts/build_report.md  relatorio do build

Uso:
    python scripts/build_patentes.py --src "<pasta 1>" --src "<pasta 2>" --out .

O script SO LE as pastas de origem: nunca renomeia, move ou apaga os
originais. E idempotente -- arquivos de saida so sao reescritos quando o
conteudo muda, entao rodar duas vezes nao altera nenhum byte nem mtime.

So grava patentes.js, o registro de IDs e o relatorio normal quando o build
termina sem erros. Com erro, grava so scripts/build_report_FALHOU.md.

Dependencias: pip install pymupdf pillow
"""
from __future__ import annotations

import argparse
import io
import json
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

# Nome da pasta: "19. BR 10 2022 019303 7" (com "_" final em algumas) ou,
# em lotes novos, sem o prefixo de ID: "BR 10 2015 029772 6".
PASTA_RE = re.compile(
    r"^(?:(?P<id>\d+)\s*\.\s*)?(?P<pais>BR)\s*(?P<esp>\d{2})\s*(?P<ano>\d{4})\s*"
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

# Numero BR com o digito verificador grafado como letra "O" em vez de zero
# (PRD P2). So casa o digito verificador, nunca outras letras da string.
NUMERO_BR_RE = re.compile(
    r"(?P<pre>BR\s*\d{2}\s*\d{4}\s*\d{6}[\s\-]*)(?P<dv>[0-9Oo])",
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

ID_REGISTRO_VERSAO = 1
ID_REGISTRO_OBS = (
    "ID permanente de cada patente (numero INPI normalizado -> id). "
    "Nunca reutilizar nem renumerar."
)


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


def normaliza_numero_bruto(s: str) -> str:
    """Troca a letra O/o pelo digito 0 quando ocupa o digito verificador
    de um numero BR (PRD P2). Nao toca em nenhum outro O/o da string."""

    def repl(m: re.Match) -> str:
        dv = m.group("dv")
        dv0 = "0" if dv.upper() == "O" else dv
        return m.group("pre") + dv0

    return NUMERO_BR_RE.sub(repl, s)


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
# Registro de IDs e lista de exclusao
# --------------------------------------------------------------------------

def carrega_registro(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    dados = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): int(v) for k, v in dados.get("ids", {}).items()}


def grava_registro(path: Path, registro: dict[str, int]) -> bool:
    ids_ordenados = dict(sorted(registro.items(), key=lambda kv: kv[1]))
    dados = {
        "versao": ID_REGISTRO_VERSAO,
        "observacao": ID_REGISTRO_OBS,
        "ids": ids_ordenados,
    }
    texto = json.dumps(dados, ensure_ascii=False, indent=2) + "\n"
    return write_if_changed(path, texto.encode("utf-8"))


def carrega_excluir(path: Path) -> set[str]:
    if not path.exists():
        return set()
    dados = json.loads(path.read_text(encoding="utf-8"))
    return {str(n) for n in dados.get("numeros", [])}


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


def escolhe_titulo(titulo_pdf: str, titulo_arquivo: str, pid: int, res: "Resultado") -> str:
    """Decide entre o titulo do PDF e o do nome do arquivo (PRD 3.4)."""
    titulo = titulo_pdf or titulo_arquivo

    # Titulo do PDF truncado (so tem o INICIO do titulo do arquivo): usa o
    # do arquivo, que e mais completo (caso da patente 4).
    if titulo_pdf and titulo_arquivo:
        a, b = so_letras(titulo_pdf), so_letras(titulo_arquivo)
        if a != b and a in b:
            titulo = titulo_arquivo
            res.avisos.append(
                f"[{pid}] titulo do PDF truncado (`{titulo_pdf}`); "
                f"usando o do arquivo (`{titulo_arquivo}`)."
            )

    # Titulo do PDF com uma palavra quebrada no meio por layout do Canva:
    # mesmo texto do arquivo se ignorarmos so os espacos (diferenca de caixa
    # continua valendo, por isso o do arquivo em MAIUSCULAS nao entra aqui).
    if (
        titulo_pdf
        and titulo_arquivo
        and titulo != titulo_arquivo
        and titulo.replace(" ", "") == titulo_arquivo.replace(" ", "")
    ):
        titulo = titulo_arquivo
        res.avisos.append(
            f"[{pid}] titulo do PDF com palavra partida; usando o do arquivo."
        )

    if titulo.isupper():
        titulo = titulo.capitalize()
        res.avisos.append(
            f"[{pid}] titulo estava em MAIUSCULAS; convertido para caixa de frase."
        )
    return titulo


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
    excluidos: list[str] = field(default_factory=list)
    contagem_origem: Counter = field(default_factory=Counter)
    bytes_origem: int = 0
    bytes_saida: int = 0


@dataclass
class EntradaPasta:
    pasta: Path
    src_root: Path
    numero: str
    esp: str
    ano: str
    seq: str
    dv: str
    prefixo_id: int | None
    corrigido_o: bool


# --------------------------------------------------------------------------
# Reconhecimento das pastas e atribuicao de IDs
# --------------------------------------------------------------------------

def monta_entrada(pasta: Path, src_root: Path, res: Resultado) -> EntradaPasta | None:
    nome = normaliza_espacos(pasta.name)
    nome_norm = normaliza_numero_bruto(nome)
    m = PASTA_RE.match(nome_norm)
    if not m:
        res.erros.append(f"`{pasta.name}`: nome de pasta fora do padrao esperado.")
        return None

    prefixo_id = int(m.group("id")) if m.group("id") else None
    esp, ano, seq, dv = m.group("esp"), m.group("ano"), m.group("seq"), m.group("dv")
    numero = f"BR {esp} {ano} {seq}-{dv}"
    return EntradaPasta(pasta, src_root, numero, esp, ano, seq, dv, prefixo_id, nome != nome_norm)


def filtra_duplicados(entradas: list[EntradaPasta], res: Resultado) -> list[EntradaPasta]:
    """Mesmo numero BR em duas pastas diferentes e erro (PRD 3.1)."""
    vistos: dict[str, Path] = {}
    unicos: list[EntradaPasta] = []
    for e in entradas:
        if e.numero in vistos:
            res.erros.append(
                f"numero duplicado em `{vistos[e.numero]}` e `{e.pasta}`."
            )
            continue
        vistos[e.numero] = e.pasta
        unicos.append(e)
    return unicos


def atribui_ids(
    entradas: list[EntradaPasta], registro_inicial: dict[str, int], res: Resultado
) -> dict[str, int]:
    """Resolve o ID de cada entrada contra o registro permanente (PRD 3.2)."""
    registro = dict(registro_inicial)

    for e in entradas:
        if e.prefixo_id is None:
            continue
        existente = registro.get(e.numero)
        if existente is not None and existente != e.prefixo_id:
            res.erros.append(
                f"[{e.prefixo_id}] numero {e.numero} ja esta registrado com id "
                f"{existente} (pasta `{e.pasta.name}`)."
            )
        else:
            registro[e.numero] = e.prefixo_id

    novas = sorted({e.numero for e in entradas if e.prefixo_id is None} - registro.keys())
    proximo = max(registro.values(), default=0) + 1
    for numero in novas:
        registro[numero] = proximo
        proximo += 1

    return registro


# --------------------------------------------------------------------------
# Processamento dos arquivos de uma pasta
# --------------------------------------------------------------------------

def arquivos_da_pasta(pasta: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """So PDF e imagem contam como fonte (PRD 1); o resto e ignorado."""
    pdfs = sorted(f for f in pasta.iterdir() if f.is_file() and f.suffix.lower() == ".pdf")
    imgs = sorted(f for f in pasta.iterdir() if f.is_file() and f.suffix.lower() in IMG_EXTS)
    outros = sorted(
        f for f in pasta.iterdir()
        if f.is_file() and f.suffix.lower() != ".pdf" and f.suffix.lower() not in IMG_EXTS
    )
    return pdfs, imgs, outros


def processa_arquivos(e: EntradaPasta, pid: int, out_root: Path, res: Resultado) -> dict | None:
    pasta = e.pasta
    tipo = TIPOS.get(e.esp)
    if tipo is None:
        res.erros.append(f"[{pid}] especie INPI desconhecida: BR {e.esp}.")
        return None

    pdfs, imgs, outros = arquivos_da_pasta(pasta)
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
    stem_norm = normaliza_numero_bruto(normaliza_espacos(pdf_src.stem))
    mm = ARQUIVO_RE.match(stem_norm)
    if mm:
        categoria_bruta = mm.group("cat").strip(" -")
        titulo_arquivo = mm.group("titulo").strip()
    if not categoria_bruta:  # ultima tentativa: nome da imagem
        img_stem_norm = normaliza_numero_bruto(normaliza_espacos(img_src.stem))
        mi = ARQUIVO_RE.match(img_stem_norm)
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

    titulo = escolhe_titulo(titulo_pdf, titulo_arquivo, pid, res)
    if not titulo:
        res.erros.append(f"[{pid}] sem titulo no PDF nem no nome do arquivo.")
        return None

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
        "numero": e.numero,
        "ano": int(e.ano),
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


def relatorio(
    res: Resultado,
    categorias: list[dict],
    srcs: list[Path],
    capas_400: int,
    atribuidos_neste_build: dict[str, int],
) -> str:
    tipos = Counter(p["tipo"]["sigla"] for p in res.patentes)
    anos = Counter(p["ano"] for p in res.patentes)
    L: list[str] = []
    A = L.append

    A("# Relatorio de build -- Vitrine de Patentes UFC")
    A("")
    A("> Gerado por `scripts/build_patentes.py`. Nao editar a mao.")
    A("")
    A(f"- **Patentes processadas:** {len(res.patentes)}")
    A(f"- **Erros:** {len(res.erros)}")
    A(f"- **Avisos:** {len(res.avisos)}")
    A(f"- **Arquivos ignorados:** {len(res.ignorados)}")
    A(f"- **Excluidos por decisao:** {len(res.excluidos)}")
    A("")
    A("## Pastas de origem")
    A("")
    A("| Pasta | Patentes |")
    A("|---|---|")
    for src in srcs:
        A(f"| `{src}` | {res.contagem_origem.get(str(src), 0)} |")
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

    A("## IDs atribuidos neste build")
    A("")
    if atribuidos_neste_build:
        A("| Numero | ID |")
        A("|---|---|")
        for numero, idd in sorted(atribuidos_neste_build.items(), key=lambda kv: kv[1]):
            A(f"| `{numero}` | {idd} |")
    else:
        A("Nenhum (nenhum numero novo neste build).")
    A("")

    A("## Fichas com texto identico")
    A("")
    grupos: dict[str, list[dict]] = {}
    for p in res.patentes:
        chave_secoes = json.dumps(p["secoes"], sort_keys=True, ensure_ascii=False)
        grupos.setdefault(chave_secoes, []).append(p)
    teve_grupo = False
    for membros in grupos.values():
        if len(membros) > 1:
            teve_grupo = True
            ids = ", ".join(str(m["id"]) for m in membros)
            A(f"- IDs {ids} tem as mesmas secoes (oQueE/problema/exemploDeUso/diferenciais/beneficio):")
            for m in membros:
                A(f"  - [{m['id']}] {m['titulo']}")
    if not teve_grupo:
        A("Nenhuma.")
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

    A("## Excluidos por decisao")
    A("")
    if res.excluidos:
        for x in res.excluidos:
            A(f"- {x}")
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
    # Console do Windows roda em cp1252 por padrao: acentos e o "tau" do
    # titulo da patente 12 quebrariam o print sem isso (os arquivos de
    # saida ja usam utf-8 explicito via write_if_changed).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="Gera os dados da Vitrine de Patentes UFC.")
    ap.add_argument(
        "--src",
        required=True,
        action="append",
        help="pasta de origem com as subpastas das patentes (pode repetir)",
    )
    ap.add_argument("--out", default=".", help="raiz do site (padrao: diretorio atual)")
    args = ap.parse_args()

    srcs = [Path(s).expanduser() for s in args.src]
    out = Path(args.out).expanduser().resolve()
    for s in srcs:
        if not s.is_dir():
            print(f"ERRO: pasta de origem nao encontrada: {s}", file=sys.stderr)
            return 2

    res = Resultado()

    pastas: list[tuple[Path, Path]] = []
    for src in srcs:
        dirs = sorted(
            (d for d in src.iterdir() if d.is_dir()),
            key=lambda p: int(m.group(1)) if (m := re.match(r"^(\d+)", p.name)) else 10**6,
        )
        pastas.extend((d, src) for d in dirs)
    print(f"Processando {len(pastas)} pastas de {len(srcs)} origem(ns)...")

    entradas_brutas = [monta_entrada(pasta, src_root, res) for pasta, src_root in pastas]
    entradas = filtra_duplicados([e for e in entradas_brutas if e is not None], res)

    dados_dir = out / "dados"
    ids_path = dados_dir / "ids_patentes.json"
    excluir_path = dados_dir / "excluir.json"

    registro_inicial = carrega_registro(ids_path)
    registro = atribui_ids(entradas, registro_inicial, res)
    excluidos = carrega_excluir(excluir_path)

    for e in entradas:
        pid = registro.get(e.numero)
        if pid is None:
            continue
        if e.corrigido_o:
            res.avisos.append(f"[{pid}] digito com letra O corrigido para 0.")
        if e.numero in excluidos:
            res.excluidos.append(
                f"[{pid}] excluido por decisao: numero {e.numero} (pasta `{e.pasta.name}`)."
            )
            continue
        p = processa_arquivos(e, pid, out, res)
        if p:
            res.patentes.append(p)
            res.contagem_origem[str(e.src_root)] += 1
            print(f"  [{p['id']:2d}] {p['categoria']:24s} {p['titulo'][:58]}")

    res.patentes.sort(key=lambda p: p["id"])

    cont = Counter(p["categoria"] for p in res.patentes)
    categorias = [
        {"nome": n, "total": cont[n]}
        for n in sorted(cont, key=lambda s: sem_acento(s).lower())
    ]

    atribuidos_neste_build = {
        numero: idd for numero, idd in registro.items() if numero not in registro_inicial
    }

    capas_400 = sum(
        (out / p["imagens"]["capa400"]).stat().st_size
        for p in res.patentes
        if (out / p["imagens"]["capa400"]).exists()
    )
    rel = relatorio(res, categorias, srcs, capas_400, atribuidos_neste_build)

    sem_erros = not res.erros
    mudou_js = False
    if sem_erros:
        js = serializa(res.patentes, categorias)
        mudou_js = write_if_changed(out / "js" / "data" / "patentes.js", js.encode("utf-8"))
        grava_registro(ids_path, registro)
        write_if_changed(out / "scripts" / "build_report.md", rel.encode("utf-8"))
    else:
        write_if_changed(out / "scripts" / "build_report_FALHOU.md", rel.encode("utf-8"))

    print()
    print(f"  patentes .......... {len(res.patentes)}")
    print(f"  categorias ........ {len(categorias)}")
    print(f"  erros ............. {len(res.erros)}")
    print(f"  avisos ............ {len(res.avisos)}")
    print(f"  ignorados ......... {len(res.ignorados)}")
    print(f"  excluidos ......... {len(res.excluidos)}")
    print(f"  peso origem ....... {mb(res.bytes_origem)}")
    print(f"  peso saida ........ {mb(res.bytes_saida)}")
    print(f"  soma capa-400 ..... {mb(capas_400)}")
    print(f"  patentes.js ....... {'atualizado' if mudou_js else 'sem mudanca'}")

    if res.erros:
        print("\nERROS:", file=sys.stderr)
        for e in res.erros:
            print("  - " + e, file=sys.stderr)
        print(
            f"\npatentes.js e o registro de IDs NAO foram gravados. "
            f"Relatorio: {out / 'scripts' / 'build_report_FALHOU.md'}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
