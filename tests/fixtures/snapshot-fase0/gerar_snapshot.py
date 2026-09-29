"""Gera o snapshot de referencia da Fase 0.

Serve de linha de base para a refatoracao das Fases 1 e 2: depois de mexer no
build, `verificar_snapshot.py` compara a saida atual com o que foi congelado
aqui e acusa qualquer divergencia byte a byte.

Uso:
    python tests/fixtures/snapshot-fase0/gerar_snapshot.py

Grava, ao lado deste arquivo:
    patentes.js        copia de js/data/patentes.js
    build_report.md    copia de scripts/build_report.md
    assets-sha256.txt  SHA-256 de todos os arquivos de assets/patentes/**
    MANIFEST.md        resumo legivel (data, contagens, hash dos dois .js/.md)
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]  # tests/fixtures/snapshot-fase0 -> raiz do repositorio

ARQUIVOS = {
    "patentes.js": RAIZ / "js" / "data" / "patentes.js",
    "build_report.md": RAIZ / "scripts" / "build_report.md",
}
ASSETS = RAIZ / "assets" / "patentes"


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def linhas_assets() -> list[str]:
    """Uma linha `<sha256>  <caminho relativo>` por arquivo, em ordem estavel.

    O caminho usa `/` sempre, para que o arquivo saia igual no Windows e no
    Linux e possa ser comparado com `git diff`.
    """
    arquivos = sorted(
        (p for p in ASSETS.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(RAIZ).as_posix(),
    )
    return [f"{sha256(p)}  {p.relative_to(RAIZ).as_posix()}" for p in arquivos]


def main() -> int:
    for destino, origem in ARQUIVOS.items():
        if not origem.exists():
            print(f"ERRO: nao encontrei {origem}")
            return 1
        shutil.copy2(origem, AQUI / destino)

    linhas = linhas_assets()
    (AQUI / "assets-sha256.txt").write_text(
        "\n".join(linhas) + "\n", encoding="utf-8", newline="\n"
    )

    agora = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    manifesto = [
        "# Snapshot de referencia — Fase 0",
        "",
        f"Gerado em {agora} por `gerar_snapshot.py`.",
        "",
        "Linha de base da vitrine **antes** da refatoracao do build",
        "(PRD secao 14, Fase 0). As Fases 1 e 2 so passam se",
        "`verificar_snapshot.py` nao acusar diferenca.",
        "",
        "| Item | Valor |",
        "|---|---|",
        f"| `js/data/patentes.js` | `{sha256(AQUI / 'patentes.js')}` |",
        f"| `scripts/build_report.md` | `{sha256(AQUI / 'build_report.md')}` |",
        f"| Arquivos em `assets/patentes/**` | {len(linhas)} |",
        f"| Pastas de patente | {sum(1 for p in ASSETS.iterdir() if p.is_dir())} |",
        "",
        "> A Fase 2 troca a copia byte a byte do PDF por uma versao",
        "> higienizada (PRD 5.4). Os hashes de `ficha.pdf` mudam **uma vez**;",
        "> `verificar_snapshot.py --ignorar-pdf` compara todo o resto.",
        "",
    ]
    (AQUI / "MANIFEST.md").write_text(
        "\n".join(manifesto), encoding="utf-8", newline="\n"
    )

    print(f"Snapshot gravado em {AQUI}")
    print(f"  {len(linhas)} arquivos de assets/patentes/**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
