# -*- coding: utf-8 -*-
"""Geracao das imagens publicadas.

Tudo que vai ao ar e **reencodado** em WebP a partir dos pixels decodificados.
Isso nao e so compressao: reencodar elimina EXIF (inclusive GPS), perfis de
cor e qualquer conteudo poliglota escondido depois do fim da imagem -- uma
imagem que tambem e um ZIP valido nao sobrevive ao round-trip (PRD 5.5).
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from .io_seguro import write_if_changed

__all__ = [
    "WEBP_CAPA_Q",
    "WEBP_FICHA_LG_Q",
    "WEBP_FICHA_SM_Q",
    "CAPA_LARGURAS",
    "FICHA_ZOOM",
    "FICHA_SM_LARGURA",
    "webp_bytes",
    "gera_capas",
    "gera_ficha",
]

WEBP_CAPA_Q = 82
WEBP_FICHA_LG_Q = 85
WEBP_FICHA_SM_Q = 80
CAPA_LARGURAS = (400, 800)
FICHA_ZOOM = 2.0  # 810x1012.5pt -> 1620x2025 px
FICHA_SM_LARGURA = 600


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
    import pymupdf

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
