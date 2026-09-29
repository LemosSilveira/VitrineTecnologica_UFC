# -*- coding: utf-8 -*-
"""Leitura do acervo -- as pastas originais das fichas.

O acervo e a **fonte da verdade** e e somente leitura para o build: nada
aqui renomeia, move ou apaga um original. Quem escreve no acervo e so o
painel.

Tambem vive aqui o carregamento de `dados/categorias.json`. O mapa de areas
tecnologicas era uma constante no codigo do build (achado A5 do PRD): com
ele em arquivo, o painel consegue acrescentar uma area sem que ninguem
precise editar Python.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "IMG_EXTS",
    "TIPOS",
    "ErroDeConfiguracao",
    "ArquivosDaPasta",
    "lista_pastas",
    "arquivos_da_pasta",
    "caminho_categorias_padrao",
    "carrega_categorias",
]

IMG_EXTS = {".png", ".jpg", ".jpeg"}

# Especie no numero do INPI: BR 10 = invencao, BR 20 = modelo de utilidade.
TIPOS = {
    "10": {"sigla": "PI", "nome": "Patente de Invenção"},
    "20": {"sigla": "MU", "nome": "Modelo de Utilidade"},
}

_PREFIXO_NUMERICO = re.compile(r"^(\d+)")


class ErroDeConfiguracao(Exception):
    """Configuracao do projeto invalida (categorias.json ausente ou torto)."""


@dataclass
class ArquivosDaPasta:
    """O que ha dentro de uma pasta de patente, ja classificado."""

    pdfs: list[Path]
    imagens: list[Path]
    outros: list[Path]


def lista_pastas(src: Path) -> list[Path]:
    """Subpastas do acervo, em ordem de ID.

    Pastas sem prefixo numerico vao para o fim, onde o build as reporta como
    erro de nome -- em vez de quebrarem a ordenacao.
    """

    def ordem(p: Path) -> int:
        m = _PREFIXO_NUMERICO.match(p.name)
        return int(m.group(1)) if m else 10**6

    return sorted((d for d in src.iterdir() if d.is_dir()), key=ordem)


def arquivos_da_pasta(pasta: Path) -> ArquivosDaPasta:
    """Separa PDFs, imagens e o resto.

    Ordem estavel: o build precisa escolher sempre o mesmo arquivo quando a
    pasta tem mais de um PDF ou mais de uma imagem, senao a saida mudaria
    entre execucoes.
    """
    pdfs: list[Path] = []
    imagens: list[Path] = []
    outros: list[Path] = []
    for f in sorted(pasta.iterdir()):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext == ".pdf":
            pdfs.append(f)
        elif ext in IMG_EXTS:
            imagens.append(f)
        else:
            outros.append(f)
    return ArquivosDaPasta(pdfs=pdfs, imagens=imagens, outros=outros)


def caminho_categorias_padrao() -> Path:
    """`dados/categorias.json` na raiz do repositorio.

    Derivado da posicao deste arquivo (`scripts/vitrine_core/acervo.py`), e
    nao do diretorio atual, para que o build funcione de qualquer pasta.
    """
    return Path(__file__).resolve().parents[2] / "dados" / "categorias.json"


def carrega_categorias(caminho: Path | None = None) -> dict[str, str]:
    """Le o mapa de areas tecnologicas.

    Devolve {chave normalizada: nome exibido}. Erra alto e claro em vez de
    seguir com um mapa vazio, porque um mapa vazio faria o build reprovar as
    60 patentes de uma vez com uma mensagem que nao explicaria a causa.
    """
    caminho = caminho or caminho_categorias_padrao()
    if not caminho.is_file():
        raise ErroDeConfiguracao(
            f"nao encontrei o mapa de areas em `{caminho}`. "
            "Ele acompanha o repositorio; restaure-o do git."
        )

    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ErroDeConfiguracao(f"`{caminho}` nao e um JSON valido: {e}") from e

    if not isinstance(dados, dict):
        raise ErroDeConfiguracao(f"`{caminho}`: o conteudo deveria ser um objeto JSON.")
    if dados.get("versao") != 1:
        raise ErroDeConfiguracao(
            f"`{caminho}`: versao {dados.get('versao')!r} desconhecida (esperada: 1)."
        )

    mapa = dados.get("mapa")
    if not isinstance(mapa, dict) or not mapa:
        raise ErroDeConfiguracao(
            f"`{caminho}`: o campo `mapa` deveria ser um objeto nao vazio."
        )
    for k, v in mapa.items():
        if not isinstance(k, str) or not isinstance(v, str) or not k or not v:
            raise ErroDeConfiguracao(
                f"`{caminho}`: a entrada {k!r} -> {v!r} deveria ser texto para texto."
            )

    return mapa
