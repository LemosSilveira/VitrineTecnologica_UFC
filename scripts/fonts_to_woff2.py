#!/usr/bin/env python3
"""Converte as fontes da identidade (OTF) para woff2.

Uso:
    python scripts/fonts_to_woff2.py

As fontes de origem ficam fora do repositorio (pastas locais do usuario).
Ajuste SOURCES se os caminhos mudarem. O script apenas le os OTF originais;
nunca os modifica.

Dependencias: pip install fonttools brotli
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("fonttools nao instalado. Rode: pip install fonttools brotli")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "fonts"

METROPOLIS_DIR = Path(r"C:\Users\Usuario\Documents\metropolis")
UFCINOVA_OTF = Path(
    r"C:\Users\Usuario\Desktop\Interface_UFC_AI\UFC_AI\public\fonts\UFCInova-Bold.otf"
)

# (arquivo de origem, nome de saida) -- somente os 5 pesos da Metropolis
# previstos no PRD, mais o unico peso da UFCInova.
SOURCES: list[tuple[Path, str]] = [
    (METROPOLIS_DIR / "Metropolis-Regular.otf", "Metropolis-Regular.woff2"),
    (METROPOLIS_DIR / "Metropolis-Medium.otf", "Metropolis-Medium.woff2"),
    (METROPOLIS_DIR / "Metropolis-SemiBold.otf", "Metropolis-SemiBold.woff2"),
    (METROPOLIS_DIR / "Metropolis-Bold.otf", "Metropolis-Bold.woff2"),
    (METROPOLIS_DIR / "Metropolis-RegularItalic.otf", "Metropolis-RegularItalic.woff2"),
    (UFCINOVA_OTF, "UFCInova-Bold.woff2"),
]

# Um OTF real da Metropolis tem dezenas de KB. Os arquivos "._Nome.otf" do
# macOS tem ~212 bytes e nao sao fontes -- barramos isso explicitamente.
MIN_FONT_BYTES = 2048


def convert(src: Path, out_name: str) -> tuple[str, int, int]:
    if not src.exists():
        raise FileNotFoundError(f"fonte nao encontrada: {src}")
    size_in = src.stat().st_size
    if size_in < MIN_FONT_BYTES:
        raise ValueError(
            f"{src.name} tem apenas {size_in} bytes -- provavelmente um stub "
            "de metadados do macOS (._*), nao uma fonte real."
        )

    font = TTFont(str(src))
    font.flavor = "woff2"
    dest = OUT_DIR / out_name
    font.save(str(dest))
    font.close()
    return out_name, size_in, dest.stat().st_size


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total_in = total_out = 0
    failures: list[str] = []

    for src, out_name in SOURCES:
        try:
            name, size_in, size_out = convert(src, out_name)
        except Exception as exc:  # noqa: BLE001 - queremos relatar e seguir
            failures.append(f"  ERRO  {out_name}: {exc}")
            continue
        total_in += size_in
        total_out += size_out
        pct = 100 * (1 - size_out / size_in)
        print(f"  OK    {name:34s} {size_in:>7,} -> {size_out:>7,} B  (-{pct:.0f}%)")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1

    print(f"\n{len(SOURCES)} fontes convertidas: {total_in:,} -> {total_out:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
