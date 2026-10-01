# -*- coding: utf-8 -*-
"""Fixtures compartilhadas pelos testes Python.

Coloca `scripts/` e `admin/` no sys.path (os dois pacotes nao sao instalados
com pip: a CLI e o painel ajustam o caminho do mesmo jeito) e monta um
ambiente completo de mentira -- site, acervo, %APPDATA% e %LOCALAPPDATA% --
para que nenhum teste toque a vitrine de verdade nem a configuracao da
maquina de quem esta rodando.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "admin"))

import pymupdf  # noqa: E402
from PIL import Image  # noqa: E402

# Mesmo template de secoes das fichas reais. Os diferenciais usam "-" porque a
# Helvetica embutida no PyMuPDF nao tem o emoji das fichas de verdade.
CORPO_FICHA = """O que é?
{oQueE}
Problema que resolve
Um problema real que esta tecnologia resolve no dia a dia.
Exemplo de uso
Uso em laboratorio e na industria de alimentos.
Diferenciais competitivos
- Primeiro diferencial
- Segundo diferencial
Benefício principal
O beneficio principal desta tecnologia para quem a licencia.
Nível de maturidade
TRL 5-6
"""


def escreve_pdf(caminho: Path, titulo: str, o_que_e: str | None = None) -> Path:
    """Ficha em PDF com o titulo em fonte grande, como as reais."""
    doc = pymupdf.open()
    pagina = doc.new_page(width=810, height=1012.5)
    pagina.insert_textbox(
        pymupdf.Rect(40, 40, 770, 200), titulo, fontsize=28, fontname="helv"
    )
    corpo = CORPO_FICHA.format(
        oQueE=o_que_e or f"Descricao do que a tecnologia {titulo!r} faz e para que serve."
    )
    pagina.insert_textbox(
        pymupdf.Rect(40, 220, 770, 980), corpo, fontsize=11, fontname="helv"
    )
    caminho.parent.mkdir(parents=True, exist_ok=True)
    doc.save(caminho)
    doc.close()
    return caminho


def escreve_imagem(caminho: Path, largura: int = 900, altura: int | None = None) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (largura, altura or largura), (92, 6, 157)).save(caminho)
    return caminho


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """Site vazio + acervo vazio + %APPDATA%/%LOCALAPPDATA% temporarios.

    Devolve um objeto com `.site`, `.acervo`, `.appdata`, `.local` e o helper
    `.add_patente(...)`. As variaveis de ambiente sao trocadas para que
    config.pasta_dados() e config.pasta_local() apontem para o tmp_path: sem
    isso os testes escreveriam no historico e nos backups reais da maquina.
    """
    site = tmp_path / "site"
    acervo = tmp_path / "acervo"
    appdata = tmp_path / "appdata"
    local = tmp_path / "local"
    for p in (site, acervo, appdata, local):
        p.mkdir(parents=True)

    # as tres marcas que identificam a pasta da vitrine
    (site / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (site / "js" / "data").mkdir(parents=True)
    (site / "js" / "data" / "patentes.js").write_text(
        "window.PATENTES = [\n];\n\nwindow.CATEGORIAS = [\n];\n", encoding="utf-8"
    )
    (site / "scripts").mkdir(exist_ok=True)
    (site / "scripts" / "build_patentes.py").write_text("# CLI", encoding="utf-8")

    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    class Ambiente:
        def __init__(self):
            self.site = site
            self.acervo = acervo
            self.appdata = appdata
            self.local = local

        def add_patente(
            self,
            pid: int,
            *,
            categoria: str = "Alimentos",
            titulo: str | None = None,
            numero: str | None = None,
            com_pdf: bool = True,
            com_capa: bool = True,
            patente_json: dict | None = None,
        ) -> Path:
            titulo = titulo or f"Tecnologia numero {pid} para testes automatizados"
            numero = numero or f"BR 10 2025 {pid:06d} 1"
            pasta = self.acervo / f"{pid}. {numero}"
            pasta.mkdir(parents=True, exist_ok=True)
            base = f"{pid}. {categoria} - {numero} - {titulo}"
            if com_pdf:
                escreve_pdf(pasta / f"{base}.pdf", titulo)
            if com_capa:
                escreve_imagem(pasta / f"{base}.png")
            if patente_json is not None:
                (pasta / "patente.json").write_text(
                    json.dumps(patente_json, ensure_ascii=False), encoding="utf-8"
                )
            return pasta

    return Ambiente()


@pytest.fixture
def dialogos_falsos():
    """Substitui o seletor nativo do Windows.

    A `Api` recebe os dialogos por injecao justamente para isto: sem ele, os
    metodos `escolher_*` so poderiam ser testados com uma janela aberta.
    """

    class Dialogos:
        def __init__(self):
            self.pasta = None
            self.arquivo = None
            self.chamadas = []

        def escolher_pasta(self, titulo):
            self.chamadas.append(("pasta", titulo))
            return self.pasta

        def escolher_arquivo(self, titulo, filtros):
            self.chamadas.append(("arquivo", titulo, filtros))
            return self.arquivo

    return Dialogos()


@pytest.fixture
def api(ambiente, dialogos_falsos):
    """Api ja configurada com o site e o acervo de mentira."""
    from painel import config
    from painel.api import Api

    ambiente.add_patente(1)
    cfg = config.Config(pastaSite=str(ambiente.site), pastaAcervo=str(ambiente.acervo))
    config.salva(cfg)

    inst = Api(dialogos=dialogos_falsos)
    inst._ambiente = ambiente  # atalho para os testes
    return inst
