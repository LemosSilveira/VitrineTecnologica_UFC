# -*- coding: utf-8 -*-
"""Nucleo da Vitrine de Patentes UFC.

Toda a logica que le o acervo e gera a vitrine mora aqui. A CLI
(`scripts/build_patentes.py`) e o painel local importam este pacote em vez
de duplicar o pipeline -- foi para isso que ele foi extraido do script de
linha de comando (achado A6 do PRD).

    from vitrine_core.build import roda_build
    res = roda_build(Path("<acervo>"), Path("."))

Modulos:
    nomes       normalizacao de texto, slug e os regex de pasta/arquivo
    io_seguro   escrita atomica, write_if_changed, confinamento de caminho
    extracao    leitura das fichas em PDF (titulo, secoes, TRL)
    imagens     capas e render da ficha em WebP
    acervo      leitura das pastas originais e de dados/categorias.json
    build       o pipeline completo e o relatorio

Dependencias: pymupdf, pillow.
"""
from __future__ import annotations

__all__ = ["VERSAO"]

VERSAO = "1.0.0"
