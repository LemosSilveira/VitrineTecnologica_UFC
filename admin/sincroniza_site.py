#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Copia os arquivos do site para `admin/ui/site/`.

O painel **reutiliza** o CSS e o JS da vitrine em vez de ter uma copia
propria: e assim que a previa mostra o card com o mesmo codigo que vai ao ar,
e que os botoes, chips e cores sao os mesmos sem ninguem precisar manter dois
conjuntos (PRD 7.1).

Copiar em vez de referenciar `../../css/` e necessario porque o servidor
estatico interno do pywebview serve **somente** `admin/ui/` (PRD 5.6). Um
caminho que subisse para fora dessa pasta nao seria servido -- e nao deveria
ser: e o que impede a janela de alcancar o resto do repositorio.

`admin/ui/site/` e gerado e fica fora do git. Rode este script:

* ao desenvolver, depois de mexer em qualquer CSS ou JS do site;
* no empacotamento, antes do PyInstaller (o exe leva a copia dentro).

    python admin/sincroniza_site.py
    python admin/sincroniza_site.py --conferir   # so avisa se divergiu

O modo `--conferir` e usado por um teste: se a copia divergir do original, a
previa do painel deixa de mostrar o que a vitrine mostra, e o erro apareceria
so quando alguem comparasse as duas telas a olho.
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "admin" / "ui" / "site"

# O que o painel precisa do site, e por que.
ARQUIVOS = [
    # tokens: cores, tipografia, espacamento, raio, sombra, movimento
    "css/tokens.css",
    # base: reset, @font-face, tipografia, .mosaico, .eyebrow
    "css/base.css",
    # components: .botao, .badge, .chip, .segmentado, .busca, .card, .previa,
    # .trl, .logo-ufcinova, lightbox
    "css/components.css",
    # pages: .ficha-secao e .patente-topo, usados na aba "Pagina" da previa
    "css/pages.css",
    # ui.js: UI.esc, UI.icone, UI.normaliza, UI.montaMosaico
    "js/ui.js",
    # render.js: o card, o TRL e as secoes -- o coracao da previa
    "js/render.js",
]

PASTAS = [
    # as fontes sao locais e o @font-face do base.css as busca em ../assets
    "assets/fonts",
]

# Do assets/img, so o logo (mascara CSS do .logo-ufcinova) e o favicon.
IMAGENS = [
    "assets/img/logo-ufcinova.svg",
    "assets/img/favicon.svg",
]


def _itens() -> list[str]:
    itens = list(ARQUIVOS) + list(IMAGENS)
    for pasta in PASTAS:
        base = RAIZ / pasta
        if base.is_dir():
            itens += [p.relative_to(RAIZ).as_posix() for p in sorted(base.iterdir()) if p.is_file()]
    return itens


def copia() -> list[str]:
    """Copia tudo. Devolve a lista de caminhos relativos copiados."""
    if DESTINO.exists():
        shutil.rmtree(DESTINO)

    copiados = []
    for rel in _itens():
        origem = RAIZ / rel
        if not origem.is_file():
            raise SystemExit(f"ERRO: nao encontrei {rel} para copiar.")
        alvo = DESTINO / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, alvo)
        copiados.append(rel)
    return copiados


def confere() -> list[str]:
    """Devolve a lista de divergencias entre o site e a copia."""
    problemas = []
    for rel in _itens():
        origem = RAIZ / rel
        alvo = DESTINO / rel
        if not alvo.is_file():
            problemas.append(f"ausente na copia: {rel}")
        elif not filecmp.cmp(origem, alvo, shallow=False):
            problemas.append(f"diferente do original: {rel}")

    # arquivo a mais na copia tambem e divergencia: seria codigo servido na
    # janela do painel que ninguem mantem
    if DESTINO.is_dir():
        esperados = {(DESTINO / rel).resolve() for rel in _itens()}
        for p in DESTINO.rglob("*"):
            if p.is_file() and p.resolve() not in esperados:
                problemas.append(f"sobrando na copia: {p.relative_to(DESTINO).as_posix()}")
    return problemas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--conferir",
        action="store_true",
        help="nao copia; sai com codigo != 0 se a copia divergir do site",
    )
    args = ap.parse_args()

    if args.conferir:
        problemas = confere()
        if problemas:
            print(f"{len(problemas)} divergencia(s) entre o site e admin/ui/site:\n")
            for p in problemas:
                print("  " + p)
            print("\nRode: python admin/sincroniza_site.py")
            return 1
        print(f"OK: {len(_itens())} arquivos iguais aos do site.")
        return 0

    copiados = copia()
    print(f"{len(copiados)} arquivos copiados para admin/ui/site/")
    for rel in copiados:
        print("  " + rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
