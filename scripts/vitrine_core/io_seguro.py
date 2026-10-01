# -*- coding: utf-8 -*-
"""Escrita em disco e confinamento de caminho.

Duas responsabilidades:

1. **Escrever sem corromper.** Toda gravacao passa por um arquivo temporario
   na mesma pasta, `fsync` e `os.replace`. Uma queda de energia no meio da
   escrita deixa o arquivo anterior intacto, nunca um `patentes.js` pela
   metade (PRD 5.8).

2. **Nao escrever fora do lugar.** `dentro_de()` e obrigatorio em toda
   operacao feita a pedido da interface do painel (PRD 5.7), que nunca
   trabalha com caminhos e nao pode ser fonte de um `..\\..\\Windows`.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

__all__ = ["escreve_atomico", "write_if_changed", "dentro_de"]


def escreve_atomico(path: Path, data: bytes) -> None:
    """Grava `data` em `path` sem deixar estado intermediario visivel.

    O temporario nasce na mesma pasta do destino de proposito: `os.replace`
    so e atomico dentro do mesmo volume.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        # a falha nao pode deixar lixo ao lado do arquivo bom
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_if_changed(path: Path, data: bytes) -> bool:
    """Escreve so se o conteudo mudou. Devolve True se escreveu.

    E o que torna o build idempotente: rodar duas vezes nao altera nenhum
    byte nem nenhum mtime, entao o `git status` continua limpo e o painel
    consegue dizer se ha alteracao pendente de publicacao.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return False
    escreve_atomico(path, data)
    return True


def dentro_de(raiz: Path | str, caminho: Path | str) -> bool:
    """True se `caminho` estiver dentro de `raiz` depois de resolvido.

    Resolve os dois lados antes de comparar, para que `..`, links simbolicos
    e caminhos relativos nao escapem. A propria raiz conta como dentro.
    """
    try:
        r = Path(raiz).resolve()
        c = Path(caminho).resolve()
    except (OSError, ValueError):
        return False
    return c == r or r in c.parents
