"""Compara a vitrine atual com o snapshot de referencia da Fase 0.

Porta de saida das Fases 1 e 2 (PRD 6.1 e 12.1): a refatoracao do build so
esta aprovada se a saida continuar identica byte a byte.

Uso:
    python tests/fixtures/snapshot-fase0/verificar_snapshot.py
    python tests/fixtures/snapshot-fase0/verificar_snapshot.py --ignorar-pdf

`--ignorar-pdf` existe para a Fase 2: a higienizacao do PDF (PRD 5.4) muda os
bytes de `ficha.pdf` uma unica vez, de proposito. Todo o resto continua tendo
de bater.

Codigo de saida: 0 se tudo bate, 1 se ha qualquer diferenca.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]

ARQUIVOS = {
    "patentes.js": RAIZ / "js" / "data" / "patentes.js",
    "build_report.md": RAIZ / "scripts" / "build_report.md",
}


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def esperado() -> dict[str, str]:
    """Le assets-sha256.txt como {caminho relativo: sha256}."""
    txt = (AQUI / "assets-sha256.txt").read_text(encoding="utf-8")
    mapa = {}
    for linha in txt.splitlines():
        if not linha.strip():
            continue
        h, _, caminho = linha.partition("  ")
        mapa[caminho] = h
    return mapa


def atual() -> dict[str, str]:
    base = RAIZ / "assets" / "patentes"
    return {
        p.relative_to(RAIZ).as_posix(): sha256(p)
        for p in base.rglob("*")
        if p.is_file()
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--ignorar-pdf",
        action="store_true",
        help="ignora ficha.pdf (esperado na Fase 2, higienizacao do PDF)",
    )
    args = ap.parse_args()

    problemas: list[str] = []

    for nome, caminho in ARQUIVOS.items():
        ref = AQUI / nome
        if not caminho.exists():
            problemas.append(f"AUSENTE  {caminho.relative_to(RAIZ).as_posix()}")
            continue
        if sha256(caminho) != sha256(ref):
            problemas.append(f"DIFERE   {caminho.relative_to(RAIZ).as_posix()}")

    esp, atu = esperado(), atual()

    def pular(caminho: str) -> bool:
        return args.ignorar_pdf and caminho.endswith("/ficha.pdf")

    for caminho, h in sorted(esp.items()):
        if pular(caminho):
            continue
        if caminho not in atu:
            problemas.append(f"AUSENTE  {caminho}")
        elif atu[caminho] != h:
            problemas.append(f"DIFERE   {caminho}")

    for caminho in sorted(set(atu) - set(esp)):
        if not pular(caminho):
            problemas.append(f"NOVO     {caminho}")

    if problemas:
        print(f"{len(problemas)} divergencia(s) em relacao ao snapshot da Fase 0:\n")
        for p in problemas[:60]:
            print("  " + p)
        if len(problemas) > 60:
            print(f"  ... e mais {len(problemas) - 60}")
        return 1

    alvo = len(esp) - sum(1 for c in esp if pular(c))
    print(f"OK: patentes.js, build_report.md e {alvo} arquivos de assets batem.")
    if args.ignorar_pdf:
        print("(ficha.pdf ignorado a pedido: --ignorar-pdf)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
