# -*- coding: utf-8 -*-
"""Normalizacao de texto, slugs e os padroes de nome do acervo.

As pastas do acervo sao a fonte da verdade e nunca sao renomeadas pelo
build, entao os dois regex abaixo precisam tolerar as inconsistencias que
ja existem nas 60 pastas originais -- e so elas. Cada tolerancia esta
comentada com o caso que a justifica.
"""
from __future__ import annotations

import re
import unicodedata

__all__ = [
    "SLUG_MAX",
    "PASTA_RE",
    "ARQUIVO_RE",
    "sem_acento",
    "chave",
    "so_letras",
    "slugify",
    "normaliza_espacos",
]

SLUG_MAX = 80

# Nome da pasta: "19. BR 10 2022 019303 7" (algumas terminam com "_").
PASTA_RE = re.compile(
    r"^(?P<id>\d+)\s*\.\s*(?P<pais>BR)\s*(?P<esp>\d{2})\s*(?P<ano>\d{4})\s*"
    r"(?P<seq>\d{6})[\s\-]*(?P<dv>\d)\s*_?\s*$",
    re.IGNORECASE,
)

# Nome do arquivo: prefixo numerico opcional, categoria, numero BR, titulo.
# O traco entre a categoria e o "BR" e opcional (a patente 48 nao tem).
ARQUIVO_RE = re.compile(
    r"^(?:\d+\s*[.\-]\s*)?\s*(?P<cat>.+?)\s*-?\s*"
    r"BR\s*\d{2}\s*\d{4}\s*\d{6}[\s\-]*\d\s*-?\s*(?P<titulo>.*)$",
    re.IGNORECASE,
)


def sem_acento(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def chave(s: str) -> str:
    """Normaliza para comparacao: sem acento, minusculo, espacos colapsados."""
    return re.sub(r"\s+", " ", sem_acento(s).lower()).strip()


def so_letras(s: str) -> str:
    """Reduz a [a-z0-9] para comparar titulos ignorando pontuacao e caixa."""
    return re.sub(r"[^a-z0-9]+", "", sem_acento(s).lower())


def slugify(s: str, limite: int = SLUG_MAX) -> str:
    s = sem_acento(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > limite:
        s = s[:limite].rstrip("-")
        # nao corta no meio de uma palavra quando da para evitar
        if "-" in s:
            s = s.rsplit("-", 1)[0]
    return s


def normaliza_espacos(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()
