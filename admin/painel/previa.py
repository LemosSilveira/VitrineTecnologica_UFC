# -*- coding: utf-8 -*-
"""Monta o objeto da previa no mesmo formato de `PATENTES[i]`.

A previa do painel usa o `js/render.js` do site, entao ela precisa receber
exatamente a mesma forma de dado que o `patentes.js` entrega. Assim o que a
equipe ve antes de salvar e o que vai ao ar -- nao uma aproximacao.

As imagens saem como `data:` URL, geradas em memoria: nada e escrito na pasta
do site antes de a pessoa confirmar.
"""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from PIL import Image  # noqa: E402

from vitrine_core.extracao import RESUMO_MAX, faz_resumo, parse_trl  # noqa: E402
from vitrine_core.imagens import (  # noqa: E402
    FICHA_SM_LARGURA,
    Recorte,
    WEBP_CAPA_Q,
    WEBP_FICHA_SM_Q,
    webp_bytes,
)
from vitrine_core.nomes import slugify  # noqa: E402

__all__ = ["monta", "capa_data_url", "ficha_data_url"]

# Larguras menores que as publicadas: a previa e vista num painel de 340px e
# num card de 296px, e uma data: URL grande deixa a atualizacao lenta a cada
# tecla digitada.
CAPA_PREVIA = 800
FICHA_PREVIA = FICHA_SM_LARGURA


def _data_url(dados: bytes, tipo: str = "image/webp") -> str:
    return f"data:{tipo};base64," + base64.b64encode(dados).decode("ascii")


def capa_data_url(caminho: Path, recorte: Recorte | None = None) -> tuple[str, list[int]]:
    """Capa como data: URL em WebP, e as dimensoes resultantes."""
    with Image.open(caminho) as im:
        im.load()
        if recorte is not None:
            recorte.valida(*im.size)
            im = im.crop(
                (recorte.x, recorte.y, recorte.x + recorte.lado, recorte.y + recorte.lado)
            )
        rgb = im.convert("RGB")
        larg, alt = rgb.size
        if larg > CAPA_PREVIA:
            alt = max(1, round(alt * CAPA_PREVIA / larg))
            rgb = rgb.resize((CAPA_PREVIA, alt), Image.LANCZOS)
        dados = webp_bytes(rgb, WEBP_CAPA_Q)
        dims = list(rgb.size)
        rgb.close()
    return _data_url(dados), dims


def ficha_data_url(caminho_pdf: Path) -> str:
    """Pagina 1 do PDF como data: URL, no tamanho da previa do hover."""
    import pymupdf

    doc = pymupdf.open(caminho_pdf)
    try:
        pagina = doc[0]
        # zoom calculado para sair ja na largura da previa, em vez de
        # renderizar em 2x e reduzir depois
        zoom = FICHA_PREVIA / pagina.rect.width
        pix = pagina.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()
    try:
        return _data_url(webp_bytes(im, WEBP_FICHA_SM_Q))
    finally:
        im.close()


def monta(
    *,
    campos: dict,
    patente_id: int,
    capa: Path | None = None,
    pdf: Path | None = None,
    recorte: Recorte | None = None,
) -> dict:
    """Objeto no formato de PATENTES[i], pronto para o js/render.js.

    Campos que o build calcula -- `resumo`, `trl.texto` e o `slug` -- sao
    calculados aqui com as MESMAS funcoes, e nao aproximados: e justamente o
    resumo cortado em 160 caracteres que a equipe precisa ver antes de salvar.
    """
    titulo = campos.get("titulo") or ""
    secoes = dict(campos.get("secoes") or {})
    for chave in ("oQueE", "problema", "exemploDeUso", "diferenciais", "beneficio"):
        secoes.setdefault(chave, None)

    trl = campos.get("trl")
    if trl:
        trl = parse_trl(
            f"TRL {trl['min']}-{trl['max']}" + (" estimado" if trl.get("estimado") else "")
        )

    resumo = faz_resumo(secoes["oQueE"], RESUMO_MAX) if secoes["oQueE"] else faz_resumo(titulo)

    capa_url, dims = ("", [800, 800])
    if capa is not None and Path(capa).is_file():
        capa_url, dims = capa_data_url(Path(capa), recorte)

    ficha_url = None
    if pdf is not None and Path(pdf).is_file():
        ficha_url = ficha_data_url(Path(pdf))

    numero = campos.get("numero") or ""
    return {
        "id": patente_id,
        "slug": f"{patente_id}-{slugify(titulo)}" if titulo else str(patente_id),
        "numero": numero,
        "ano": campos.get("ano") or 0,
        "tipo": campos.get("tipo") or {"sigla": "PI", "nome": "Patente de Invenção"},
        "categoria": campos.get("categoria") or "",
        "titulo": titulo,
        "resumo": resumo,
        "secoes": secoes,
        "trl": trl,
        "imagens": {
            "capa400": capa_url,
            "capa800": capa_url,
            # sem PDF, os dois ficam nulos e o site cai para a capa (PRD 6.4)
            "ficha600": ficha_url,
            "ficha1620": ficha_url,
            "dimensoesCapa": dims,
        },
        "pdf": "#" if ficha_url else None,
    }
