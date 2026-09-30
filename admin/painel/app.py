# -*- coding: utf-8 -*-
"""Inicializacao do painel: instancia unica e preparo do ambiente.

A janela (pywebview / WebView2) entra aqui na Fase 7. O que ja existe e o que
precisa valer **antes** de qualquer escrita: garantir que so ha um painel
mexendo no acervo.

Por que instancia unica importa: dois paineis abertos gravariam no mesmo
`patente.json` e rodariam o build ao mesmo tempo, e a segunda gravacao
sobrescreveria a primeira sem ninguem perceber. A trava e local -- um
computador por vez, como a v1 do PRD define. Acervo em pasta de rede
compartilhada entre maquinas precisaria de trava entre computadores, o que
fica para depois (PRD P4).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .config import caminho_trava

__all__ = ["TravaOcupada", "Trava", "prepara_ambiente"]

# O byte disputado. Todas as instancias travam este mesmo byte; e o que faz a
# segunda receber conflito em vez de travar outra regiao sem perceber.
_BYTE_DA_TRAVA = 0


class TravaOcupada(Exception):
    """Ja ha um painel aberto neste computador."""


class Trava:
    """Trava de instancia unica, por bloqueio de arquivo.

    Usa `msvcrt.locking` no Windows e `fcntl.flock` fora dele. O bloqueio e
    do sistema operacional, nao um "arquivo existe?": um painel que travou e
    foi encerrado pelo Gerenciador de Tarefas deixaria o arquivo para tras, e
    a checagem por existencia impediria o proximo de abrir para sempre.
    """

    def __init__(self, caminho: Path | None = None):
        self.caminho = Path(caminho) if caminho else caminho_trava()
        self._f = None

    def adquire(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)

        # Modo binario e posicionamento explicito, nao texto com "a+":
        # `msvcrt.locking` trava o byte na POSICAO ATUAL do arquivo, e em modo
        # append a posicao e o fim. Duas instancias travariam bytes diferentes,
        # nenhuma veria conflito, e a segunda so falharia depois -- ao escrever.
        self._f = open(self.caminho, "a+b")
        self._f.seek(_BYTE_DA_TRAVA)
        try:
            self._bloqueia(self._f)
        except OSError as e:
            self._f.close()
            self._f = None
            raise TravaOcupada(
                "O painel já está aberto neste computador. Procure a janela na "
                "barra de tarefas."
            ) from e

        # O PID vai DEPOIS do byte travado, para nao escrever na regiao
        # bloqueada. Serve so para diagnostico: quem manda e a trava.
        self._f.seek(_BYTE_DA_TRAVA + 1)
        self._f.truncate()
        self._f.write(f"{os.getpid()}\n".encode("ascii"))
        self._f.flush()

    def libera(self) -> None:
        if self._f is None:
            return
        try:
            self._desbloqueia(self._f)
        except OSError:  # pragma: no cover - o fechamento ja libera
            pass
        self._f.close()
        self._f = None

    def __enter__(self):
        self.adquire()
        return self

    def __exit__(self, *exc):
        self.libera()
        return False

    # -- especifico de plataforma -----------------------------------------

    @staticmethod
    def _bloqueia(f) -> None:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:  # pragma: no cover - o painel e Windows
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _desbloqueia(f) -> None:
        if os.name == "nt":
            import msvcrt

            f.seek(_BYTE_DA_TRAVA)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:  # pragma: no cover
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def prepara_ambiente() -> None:
    """Coloca `scripts/` no sys.path, como a CLI faz.

    O pacote `vitrine_core` nao e instalado com pip: ele mora em `scripts/` e e
    importado tanto pela linha de comando quanto pelo painel.
    """
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
