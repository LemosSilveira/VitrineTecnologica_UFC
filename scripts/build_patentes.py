#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline de dados da Vitrine de Patentes UFC (linha de comando).

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

A logica em si vive em `scripts/vitrine_core/`, que o painel local tambem
importa. Este arquivo e so a casca de linha de comando: argumentos, o que
sai no terminal e o codigo de saida.

Dependencias: pip install pymupdf pillow
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import pymupdf  # noqa: F401
except ImportError:  # pragma: no cover
    sys.exit("PyMuPDF nao instalado. Rode: pip install pymupdf pillow")

try:
    from PIL import Image  # noqa: F401
except ImportError:  # pragma: no cover
    sys.exit("Pillow nao instalado. Rode: pip install pymupdf pillow")

from vitrine_core.acervo import ErroDeConfiguracao
from vitrine_core.build import mb, roda_build


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera os dados da Vitrine de Patentes UFC.")
    ap.add_argument("--src", required=True, help="pasta de origem com as subpastas das patentes")
    ap.add_argument("--out", default=".", help="raiz do site (padrao: diretorio atual)")
    ap.add_argument(
        "--categorias",
        default=None,
        help="caminho de categorias.json (padrao: dados/categorias.json do repositorio)",
    )
    args = ap.parse_args()

    src = Path(args.src).expanduser()
    out = Path(args.out).expanduser().resolve()
    cats = Path(args.categorias).expanduser() if args.categorias else None
    if not src.is_dir():
        print(f"ERRO: pasta de origem nao encontrada: {src}", file=sys.stderr)
        return 2

    def comecou(n: int) -> None:
        print(f"Processando {n} pastas de `{src}`...")

    def processou(p: dict) -> None:
        print(f"  [{p['id']:2d}] {p['categoria']:24s} {p['titulo'][:58]}")

    try:
        res = roda_build(src, out, cats, ao_processar=processou, ao_comecar=comecou)
    except ErroDeConfiguracao as e:
        print(f"ERRO de configuracao: {e}", file=sys.stderr)
        return 2

    print()
    print(f"  patentes .......... {len(res.patentes)}")
    print(f"  categorias ........ {len(res.categorias)}")
    print(f"  erros ............. {len(res.erros)}")
    print(f"  avisos ............ {len(res.avisos)}")
    print(f"  ignorados ......... {len(res.ignorados)}")
    print(f"  peso origem ....... {mb(res.bytes_origem)}")
    print(f"  peso saida ........ {mb(res.bytes_saida)}")
    print(f"  soma capa-400 ..... {mb(res.capas_400)}")
    print(f"  patentes.js ....... {'atualizado' if res.js_mudou else 'sem mudanca'}")

    if res.erros:
        print("\nERROS:", file=sys.stderr)
        for e in res.erros:
            print("  - " + e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
