# -*- coding: utf-8 -*-
"""Backup antes de cada alteracao, e restauracao (PRD 5.8).

A lixeira cobre a exclusao; o backup cobre o resto -- editar, ocultar,
restaurar, acrescentar uma area. Toda acao que escreve guarda antes uma copia
do que vai mudar: a pasta da patente afetada no acervo e o `patentes.js` do
site.

Retencao: os 50 backups mais recentes, **mas nunca o ultimo de cada
patente**. Sem essa excecao, 50 edicoes seguidas numa patente apagariam o
unico backup de todas as outras.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import pasta_backups
from .auditoria import quem

__all__ = ["MAX_BACKUPS", "Backup", "ErroDeBackup", "cria", "lista", "restaura"]

MAX_BACKUPS = 50

_META = "backup.json"


class ErroDeBackup(Exception):
    """Falha ao criar ou restaurar um backup."""


@dataclass
class Backup:
    id: str
    acao: str
    patente_id: int | None
    quando: str
    usuario: str
    pasta: Path

    def descricao(self) -> str:
        alvo = f"patente {self.patente_id}" if self.patente_id else "a vitrine"
        return f"{self.acao} em {alvo}"


def _agora_id(acao: str, patente_id: int | None) -> str:
    quando = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    sufixo = f"_{patente_id}" if patente_id is not None else ""
    return f"{quando}_{acao}{sufixo}"


def cria(
    acao: str,
    *,
    patente_id: int | None = None,
    pasta_patente: Path | None = None,
    patentes_js: Path | None = None,
    raiz: Path | None = None,
) -> Backup:
    """Guarda uma copia do estado atual antes de alterar.

    `pasta_patente` e copiada inteira (PDF, capa e patente.json originais);
    `patentes_js` e copiado como arquivo. Os dois sao opcionais porque nem
    toda acao mexe nos dois -- acrescentar uma area tecnologica, por exemplo,
    nao toca em nenhuma patente.
    """
    base = raiz or pasta_backups()
    destino = base / _agora_id(acao, patente_id)

    # duas acoes no mesmo segundo nao podem escrever uma sobre a outra
    n = 2
    while destino.exists():
        destino = base / f"{_agora_id(acao, patente_id)}-{n}"
        n += 1

    try:
        destino.mkdir(parents=True)
        if pasta_patente is not None and Path(pasta_patente).is_dir():
            shutil.copytree(pasta_patente, destino / "acervo" / Path(pasta_patente).name)
        if patentes_js is not None and Path(patentes_js).is_file():
            alvo = destino / "site" / "js" / "data"
            alvo.mkdir(parents=True, exist_ok=True)
            shutil.copy2(patentes_js, alvo / "patentes.js")

        meta = {
            "versao": 1,
            "acao": acao,
            "patenteId": patente_id,
            "quando": datetime.now().astimezone().isoformat(timespec="seconds"),
            "usuario": quem(),
        }
        (destino / _META).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as e:
        shutil.rmtree(destino, ignore_errors=True)
        raise ErroDeBackup(
            "Nao conseguimos guardar a copia de seguranca, e por isso nada foi "
            "alterado. Confira se ha espaco em disco."
        ) from e

    _remove_antigos(base)
    return _le(destino)


def _le(pasta: Path) -> Backup:
    dados = {}
    arq = pasta / _META
    if arq.is_file():
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            dados = {}
    return Backup(
        id=pasta.name,
        acao=str(dados.get("acao", "?")),
        patente_id=dados.get("patenteId"),
        quando=str(dados.get("quando", "")),
        usuario=str(dados.get("usuario", "?")),
        pasta=pasta,
    )


def lista(raiz: Path | None = None) -> list[Backup]:
    """Backups do mais recente para o mais antigo.

    A ordem vem do nome da pasta, que comeca com a data em formato ordenavel
    -- nao do mtime, que muda ao copiar a pasta de backup para outro lugar.
    """
    base = raiz or pasta_backups()
    if not base.is_dir():
        return []
    return [
        _le(p) for p in sorted((d for d in base.iterdir() if d.is_dir()), reverse=True)
    ]


def _remove_antigos(raiz: Path) -> list[str]:
    """Mantem MAX_BACKUPS, preservando o mais recente de cada patente."""
    todos = lista(raiz)
    if len(todos) <= MAX_BACKUPS:
        return []

    protegidos: set[str] = set()
    vistos: set[int | None] = set()
    for b in todos:  # do mais recente para o mais antigo
        if b.patente_id not in vistos:
            vistos.add(b.patente_id)
            protegidos.add(b.id)

    removidos = []
    for b in reversed(todos):  # apaga primeiro os mais antigos
        if len(todos) - len(removidos) <= MAX_BACKUPS:
            break
        if b.id in protegidos:
            continue
        shutil.rmtree(b.pasta, ignore_errors=True)
        removidos.append(b.id)
    return removidos


def restaura(
    id_backup: str,
    *,
    acervo: Path,
    site: Path,
    raiz: Path | None = None,
) -> Backup:
    """Devolve o acervo e o patentes.js ao estado guardado no backup.

    Quem chama precisa criar um backup do estado ATUAL antes (a `Api` faz
    isso): sem ele, restaurar por engano nao teria volta.
    """
    base = raiz or pasta_backups()
    # o id vem da interface: nao pode ser usado como caminho sem conferir
    if not id_backup or "/" in id_backup or "\\" in id_backup or ".." in id_backup:
        raise ErroDeBackup("Este ponto do historico nao existe.")

    pasta = base / id_backup
    if not pasta.is_dir():
        raise ErroDeBackup("Este ponto do historico nao existe mais.")

    b = _le(pasta)
    try:
        guardado = pasta / "acervo"
        if guardado.is_dir():
            for origem in guardado.iterdir():
                if not origem.is_dir():
                    continue
                destino = Path(acervo) / origem.name
                if destino.exists():
                    shutil.rmtree(destino)
                shutil.copytree(origem, destino)

        js = pasta / "site" / "js" / "data" / "patentes.js"
        if js.is_file():
            alvo = Path(site) / "js" / "data" / "patentes.js"
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(js, alvo)
    except OSError as e:
        raise ErroDeBackup(
            "A restauracao falhou no meio. Confira a pasta do acervo antes de "
            "tentar de novo."
        ) from e
    return b
