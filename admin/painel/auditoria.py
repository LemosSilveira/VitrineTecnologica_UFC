# -*- coding: utf-8 -*-
"""Historico de acoes, em JSON Lines (PRD 5.8).

Uma linha por acao, so acrescentada, nunca reescrita. E o que responde "quem
mexeu nisto e quando" -- a unica pergunta que um painel sem login consegue
responder, porque a fronteira de seguranca e a conta do Windows (T10).

O que NAO vai para o log: o conteudo dos campos e caminhos pessoais alem do
necessario. O log diz *que* o titulo mudou, nao para o que ele mudou -- para
isso existe o backup.
"""
from __future__ import annotations

import getpass
import json
import os
import socket
from datetime import datetime
from pathlib import Path

from .config import caminho_auditoria

__all__ = ["registra", "le", "conta", "quem", "onde"]

# Tamanho maximo de uma linha. Um campo gigante (um `resumo` montado a partir
# de dados errados, por exemplo) nao pode inflar o log sem limite.
_LINHA_MAX = 4096


def _inteiro(valor: object, padrao: int) -> int:
    """Converte para int sem levantar. Texto, None e lista caem no padrao."""
    if isinstance(valor, bool) or valor is None:
        return padrao
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def quem() -> str:
    """Usuario do Windows. Sem login proprio, e a identidade disponivel."""
    try:
        return getpass.getuser()
    except Exception:  # pragma: no cover - getuser() falha sem HOME nem USER
        return "?"


def onde() -> str:
    try:
        return socket.gethostname()
    except Exception:  # pragma: no cover
        return "?"


def registra(
    acao: str,
    *,
    resultado: str = "ok",
    caminho: Path | None = None,
    **campos,
) -> dict:
    """Acrescenta uma linha ao log e devolve o registro gravado.

    Nunca levanta excecao: falhar ao escrever o historico nao pode impedir a
    acao que ja aconteceu, nem derrubar o painel. Um log que nao gravou e um
    problema; uma patente perdida por causa dele seria maior.
    """
    registro = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "usuario": quem(),
        "maquina": onde(),
        "acao": str(acao),
        **{k: v for k, v in campos.items() if v is not None},
        "resultado": resultado,
    }

    alvo = caminho or caminho_auditoria()
    try:
        linha = json.dumps(registro, ensure_ascii=False)
        if len(linha) > _LINHA_MAX:
            registro = {
                "ts": registro["ts"],
                "usuario": registro["usuario"],
                "maquina": registro["maquina"],
                "acao": registro["acao"],
                "resumo": "(registro grande demais, campos omitidos)",
                "resultado": resultado,
            }
            linha = json.dumps(registro, ensure_ascii=False)

        alvo.parent.mkdir(parents=True, exist_ok=True)
        # "a" + uma unica chamada de write: o append em modo texto e atomico o
        # bastante para linhas curtas, e nao ha releitura para corromper.
        with alvo.open("a", encoding="utf-8", newline="\n") as f:
            f.write(linha + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass
    return registro


def le(pagina: int = 1, por_pagina: int = 50, caminho: Path | None = None) -> dict:
    """Uma pagina do historico, da acao mais recente para a mais antiga.

    Linha corrompida nao derruba a leitura: ela entra na lista marcada, para
    que a tela Historico mostre que algo se perdeu em vez de ficar vazia.
    """
    alvo = caminho or caminho_auditoria()
    if not alvo.is_file():
        return {"linhas": [], "pagina": 1, "paginas": 0, "total": 0}

    try:
        cru = alvo.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"linhas": [], "pagina": 1, "paginas": 0, "total": 0}

    brutas = [ln for ln in cru if ln.strip()]
    brutas.reverse()

    # A pagina vem da interface: qualquer coisa pode chegar aqui, e um
    # ValueError derrubaria a tela Historico inteira.
    por_pagina = max(1, min(_inteiro(por_pagina, 50), 200))
    total = len(brutas)
    paginas = max(1, -(-total // por_pagina))
    pagina = max(1, min(_inteiro(pagina, 1), paginas))
    inicio = (pagina - 1) * por_pagina

    linhas = []
    for ln in brutas[inicio : inicio + por_pagina]:
        try:
            item = json.loads(ln)
            if not isinstance(item, dict):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            item = {"acao": "(linha ilegivel no historico)", "resultado": "erro"}
        linhas.append(item)

    return {"linhas": linhas, "pagina": pagina, "paginas": paginas, "total": total}


def conta(caminho: Path | None = None) -> int:
    alvo = caminho or caminho_auditoria()
    if not alvo.is_file():
        return 0
    try:
        return sum(
            1
            for ln in alvo.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip()
        )
    except OSError:
        return 0
