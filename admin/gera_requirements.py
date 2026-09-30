"""Gera admin/requirements*.txt com versoes fixadas e hashes reais (PRD 5.10).

Baixa cada dependencia (com as transitivas), calcula o SHA-256 dos arquivos
baixados e escreve os dois arquivos no formato que `pip install
--require-hashes` aceita.
"""
import hashlib
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(r"C:\Users\Usuario\Desktop\vitrinePI_site")
TMP = Path(r"C:\Users\Usuario\AppData\Local\Temp\claude\req")

RUNTIME = ["pywebview==5.4", "pymupdf==1.28.2", "pillow==12.3.0"]
DEV = ["pyinstaller==6.16.0", "pytest==9.1.1"]

CABECALHO = """\
# ============================================================
# {titulo}
#
# Instalar SEMPRE com verificacao de hash:
#     pip install --require-hashes -r {arquivo}
#
# Sem --require-hashes, uma dependencia comprometida no PyPI entraria no
# executavel que a equipe da UFC Inova roda (modelo de ameacas T9).
#
# GERADO para {plataforma}, Python {pyver}. Wheels com codigo compilado
# (pymupdf, pillow) sao especificos de versao do Python e de plataforma:
# trocar qualquer um dos dois exige regerar este arquivo.
#
# Para regerar:
#     python admin/gera_requirements.py
# ============================================================
"""


def baixa(pacotes, destino):
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "download", "--dest", str(destino), *pacotes],
        check=True,
        capture_output=True,
    )
    return sorted(destino.iterdir())


def nome_e_versao(arquivo: Path) -> tuple[str, str]:
    nome = arquivo.name
    if nome.endswith(".whl"):
        partes = nome.split("-")
        return partes[0].replace("_", "-"), partes[1]
    m = re.match(r"^(.+?)-([0-9][^-]*)\.tar\.gz$", nome)
    if m:
        return m.group(1).replace("_", "-"), m.group(2)
    raise SystemExit(f"nao sei ler o nome: {nome}")


def escreve(pacotes, destino_txt, titulo, pasta):
    arquivos = baixa(pacotes, pasta)
    linhas = [
        CABECALHO.format(
            titulo=titulo,
            arquivo=f"admin/{destino_txt.name}",
            plataforma=platform.machine() + " / " + platform.system(),
            pyver=".".join(map(str, sys.version_info[:2])),
        )
    ]
    for f in arquivos:
        pacote, versao = nome_e_versao(f)
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        linhas.append(f"{pacote}=={versao} \\\n    --hash=sha256:{h}")
    destino_txt.write_text("\n".join(linhas) + "\n", encoding="utf-8", newline="\n")
    print(f"{destino_txt.name}: {len(arquivos)} pacote(s)")
    for f in arquivos:
        print("   ", f.name)


escreve(
    RUNTIME,
    RAIZ / "admin" / "requirements.txt",
    "Dependencias de execucao do Painel da Vitrine",
    TMP / "runtime",
)
print()
escreve(
    DEV,
    RAIZ / "admin" / "requirements-dev.txt",
    "Dependencias so de desenvolvimento (testes e empacotamento)",
    TMP / "dev",
)
