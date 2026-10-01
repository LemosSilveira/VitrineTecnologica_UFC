# -*- coding: utf-8 -*-
"""Preenchimento automatico do formulario do painel (PRD 6.2).

Inclui o **teste de ouro**: `ler_ficha` rodado nas 60 fichas reais tem de
devolver exatamente o titulo, as secoes, o TRL, o numero e a area que estao
no `js/data/patentes.js` gerado. E o que garante que a pessoa que arrasta o
PDF no painel ve os mesmos campos que o build extrairia.

O teste de ouro e pulado quando o acervo nao esta na maquina (outro
computador, CI), porque ele depende das 60 fichas originais.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf
import pytest
from PIL import Image  # noqa: F401  (garante que o ambiente tem Pillow)

from vitrine_core.acervo import carrega_categorias, lista_pastas
from vitrine_core.extracao import (
    NAO_ENCONTRADO,
    NOME_ARQUIVO,
    PDF,
    ler_ficha,
    ler_texto,
)

RAIZ = Path(__file__).resolve().parents[2]
ACERVO = Path(
    r"C:\Users\Usuario\Documents\50 Patentes Observatório-20260924T152758Z-1-001"
    r"\50 Patentes Observatório"
)

TEXTO_FICHA = """O que é?
Ingrediente obtido pela desidratação de camarão por spray-dryer.
Problema que resolve
Falta de ingredientes práticos com vida útil longa.
Exemplo de uso
Molhos, temperos e sopas desidratadas.
Diferenciais competitivos
- Alto teor proteico
- Preservação do sabor natural
Benefício principal
Agrega sabor natural de camarão.
Nível de maturidade
TRL 5-6
"""


# --------------------------------------------------------------------------
# ler_texto: o caminho de quem colou o texto sem ter o arquivo
# --------------------------------------------------------------------------

class TestLerTexto:
    def test_extrai_as_secoes(self):
        f = ler_texto(TEXTO_FICHA)
        assert f["secoes"]["oQueE"]["valor"].startswith("Ingrediente obtido")
        assert f["secoes"]["problema"]["valor"].startswith("Falta de")
        assert f["secoes"]["diferenciais"]["valor"] == [
            "Alto teor proteico",
            "Preservação do sabor natural",
        ]
        assert f["secoes"]["beneficio"]["valor"].startswith("Agrega sabor")

    def test_extrai_o_trl(self):
        trl = ler_texto(TEXTO_FICHA)["trl"]["valor"]
        assert (trl["min"], trl["max"]) == (5, 6)

    def test_marca_a_origem_como_pdf(self):
        f = ler_texto(TEXTO_FICHA)
        assert f["secoes"]["oQueE"]["origem"] == PDF
        assert f["trl"]["origem"] == PDF

    def test_acha_o_numero_no_texto(self):
        f = ler_texto("Pedido BR 10 2014 030019 8 depositado em 2014.\n" + TEXTO_FICHA)
        assert f["numero"]["valor"] == "BR 10 2014 030019-8"
        assert f["numero"]["origem"] == PDF

    def test_sem_arquivo_nao_ha_como_deduzir_a_area(self):
        """A area sai do nome do arquivo; texto colado nao tem nome."""
        f = ler_texto(TEXTO_FICHA)
        assert f["categoria"]["valor"] is None
        assert f["categoria"]["origem"] == NAO_ENCONTRADO
        assert f["titulo"]["origem"] == NAO_ENCONTRADO

    def test_texto_vazio_nao_quebra(self):
        f = ler_texto("")
        assert f["numero"]["origem"] == NAO_ENCONTRADO
        assert f["secoes"]["oQueE"]["valor"] is None
        assert f["secoes"]["oQueE"]["origem"] == NAO_ENCONTRADO

    def test_none_nao_quebra(self):
        assert ler_texto(None)["trl"]["valor"] is None

    def test_campo_vazio_vira_nao_encontrado(self):
        """A interface precisa distinguir "achei e esta vazio" de "nao achei"
        para sinalizar o campo com a borda tracejada (PRD 7.4)."""
        f = ler_texto("O que é?\nAlgo.\n")
        assert f["secoes"]["problema"]["origem"] == NAO_ENCONTRADO
        assert f["secoes"]["diferenciais"]["origem"] == NAO_ENCONTRADO


# --------------------------------------------------------------------------
# ler_ficha: o caminho de quem arrastou o PDF
# --------------------------------------------------------------------------

@pytest.fixture
def ficha(tmp_path):
    """Gera um PDF de ficha com titulo em fonte grande e nome no padrao."""

    def _ficha(
        nome="1. Alimentos - BR 10 2014 030019 8 - Camarão em Pó Natural.pdf",
        titulo="Camarão em Pó Natural",
        corpo=TEXTO_FICHA,
    ):
        alvo = tmp_path / nome
        doc = pymupdf.open()
        pagina = doc.new_page(width=810, height=1012.5)
        pagina.insert_textbox(
            pymupdf.Rect(40, 40, 770, 200), titulo, fontsize=28, fontname="helv"
        )
        pagina.insert_textbox(
            pymupdf.Rect(40, 220, 770, 980), corpo, fontsize=11, fontname="helv"
        )
        doc.save(alvo)
        doc.close()
        return alvo

    return _ficha


class TestLerFicha:
    def test_titulo_vem_do_pdf(self, ficha):
        f = ler_ficha(ficha())
        assert f["titulo"]["valor"] == "Camarão em Pó Natural"
        assert f["titulo"]["origem"] == PDF

    def test_numero_cai_para_o_nome_do_arquivo(self, ficha):
        """Nas 60 fichas reais o numero do pedido NAO aparece no texto do PDF,
        so no nome do arquivo -- entao este e o caminho normal, nao a excecao."""
        f = ler_ficha(ficha())
        assert f["numero"]["valor"] == "BR 10 2014 030019-8"
        assert f["numero"]["origem"] == NOME_ARQUIVO

    def test_numero_no_texto_tem_prioridade(self, ficha):
        alvo = ficha(corpo="Pedido BR 20 2020 111111 2.\n" + TEXTO_FICHA)
        f = ler_ficha(alvo)
        assert f["numero"]["valor"] == "BR 20 2020 111111-2"
        assert f["numero"]["origem"] == PDF

    def test_area_sai_do_nome_do_arquivo_pelo_mapa(self, ficha):
        f = ler_ficha(ficha(), carrega_categorias())
        assert f["categoria"]["valor"] == "Alimentos"
        assert f["categoria"]["origem"] == NOME_ARQUIVO

    def test_area_fora_do_mapa_fica_vazia(self, ficha):
        alvo = ficha(nome="1. Astrologia - BR 10 2014 030019 8 - Titulo.pdf")
        f = ler_ficha(alvo, carrega_categorias())
        assert f["categoria"]["valor"] is None
        assert f["categoria"]["origem"] == NAO_ENCONTRADO

    def test_sem_mapa_nao_deduz_a_area(self, ficha):
        assert ler_ficha(ficha())["categoria"]["valor"] is None

    def test_secoes_e_trl(self, ficha):
        f = ler_ficha(ficha(), carrega_categorias())
        assert f["secoes"]["oQueE"]["valor"].startswith("Ingrediente obtido")
        assert (f["trl"]["valor"]["min"], f["trl"]["valor"]["max"]) == (5, 6)

    def test_conta_as_paginas(self, ficha):
        assert ler_ficha(ficha())["paginas"] == 1

    def test_titulo_em_maiusculas_vira_caixa_de_frase(self, ficha):
        """Mesmo tratamento do build (o caso da patente 52)."""
        alvo = ficha(titulo="TITULO TODO EM MAIUSCULAS")
        assert ler_ficha(alvo)["titulo"]["valor"] == "Titulo todo em maiusculas"

    def test_titulo_truncado_no_pdf_cai_para_o_nome_do_arquivo(self, ficha):
        """O caso da patente 4: o design cortou o titulo no PDF, e o nome do
        arquivo tem a versao completa."""
        alvo = ficha(
            nome="4. Alimentos - BR 10 2016 021263 4 - Molho Agridoce com Hortaliças Não Convencionais.pdf",
            titulo="Molho Agridoce com Hortaliças",
        )
        f = ler_ficha(alvo)
        assert f["titulo"]["valor"] == "Molho Agridoce com Hortaliças Não Convencionais"
        assert f["titulo"]["origem"] == NOME_ARQUIVO

    def test_nome_de_arquivo_fora_do_padrao_nao_quebra(self, ficha):
        f = ler_ficha(ficha(nome="rascunho final (2).pdf"), carrega_categorias())
        assert f["titulo"]["valor"] == "Camarão em Pó Natural"  # veio do PDF
        assert f["numero"]["origem"] == NAO_ENCONTRADO
        assert f["categoria"]["valor"] is None

    def test_todo_campo_tem_valor_e_origem(self, ficha):
        f = ler_ficha(ficha(), carrega_categorias())
        for chave in ("numero", "categoria", "titulo", "trl"):
            assert set(f[chave]) == {"valor", "origem"}, chave
        for chave in ("oQueE", "problema", "exemploDeUso", "diferenciais", "beneficio"):
            assert set(f["secoes"][chave]) == {"valor", "origem"}, chave


# --------------------------------------------------------------------------
# Teste de ouro: as 60 fichas reais
# --------------------------------------------------------------------------

def carrega_patentes_js() -> dict[int, dict]:
    """Le o `patentes.js` gerado como dados, para comparar com ler_ficha."""
    js = (RAIZ / "js" / "data" / "patentes.js").read_text(encoding="utf-8")
    inicio = js.index("window.PATENTES = ") + len("window.PATENTES = ")
    corpo = js[inicio : js.index("\n];", inicio) + 2]
    corpo = re.sub(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):", r'\1"\2":', corpo, flags=re.M)
    corpo = re.sub(r",(\s*[\]}])", r"\1", corpo)  # JSON nao aceita virgula sobrando
    return {p["id"]: p for p in json.loads(corpo)}


@pytest.mark.skipif(not ACERVO.is_dir(), reason="o acervo original nao esta nesta maquina")
class TestDeOuro:
    """`ler_ficha` tem de reproduzir o que o build extraiu das 60 fichas."""

    @pytest.fixture(scope="class")
    @staticmethod
    def dados():
        cats = carrega_categorias()
        esperado = carrega_patentes_js()
        lidas = {}
        for pasta in lista_pastas(ACERVO):
            pid = int(re.match(r"^(\d+)", pasta.name).group(1))
            pdfs = sorted(pasta.glob("*.pdf"))
            if pdfs:
                lidas[pid] = ler_ficha(pdfs[0], cats)
        return lidas, esperado

    def test_le_as_60(self, dados):
        lidas, esperado = dados
        assert len(lidas) == 60
        assert set(lidas) == set(esperado)

    def test_titulos_batem(self, dados):
        lidas, esperado = dados
        erradas = {
            pid: (f["titulo"]["valor"], esperado[pid]["titulo"])
            for pid, f in lidas.items()
            if f["titulo"]["valor"] != esperado[pid]["titulo"]
        }
        assert erradas == {}

    def test_numeros_batem(self, dados):
        lidas, esperado = dados
        erradas = {
            pid: (f["numero"]["valor"], esperado[pid]["numero"])
            for pid, f in lidas.items()
            if f["numero"]["valor"] != esperado[pid]["numero"]
        }
        assert erradas == {}

    def test_areas_batem(self, dados):
        lidas, esperado = dados
        erradas = {
            pid: (f["categoria"]["valor"], esperado[pid]["categoria"])
            for pid, f in lidas.items()
            if f["categoria"]["valor"] != esperado[pid]["categoria"]
        }
        assert erradas == {}

    @pytest.mark.parametrize(
        "secao", ["oQueE", "problema", "exemploDeUso", "diferenciais", "beneficio"]
    )
    def test_secoes_batem(self, dados, secao):
        lidas, esperado = dados
        erradas = {
            pid: (f["secoes"][secao]["valor"], esperado[pid]["secoes"][secao])
            for pid, f in lidas.items()
            if f["secoes"][secao]["valor"] != esperado[pid]["secoes"][secao]
        }
        assert erradas == {}

    def test_trl_bate(self, dados):
        lidas, esperado = dados
        erradas = {
            pid: (f["trl"]["valor"], esperado[pid]["trl"])
            for pid, f in lidas.items()
            if f["trl"]["valor"] != esperado[pid]["trl"]
        }
        assert erradas == {}

    def test_a_origem_de_cada_campo_e_a_esperada(self, dados):
        """Documenta o que foi medido no acervo real: o numero e a area vem
        SEMPRE do nome do arquivo (o texto do PDF nao traz o numero), e o
        titulo vem do PDF em 59 das 60 -- a excecao e a patente 4."""
        lidas, _esperado = dados
        origens = {}
        for campo in ("numero", "categoria", "titulo"):
            origens[campo] = {}
            for f in lidas.values():
                o = f[campo]["origem"]
                origens[campo][o] = origens[campo].get(o, 0) + 1

        assert origens["numero"] == {NOME_ARQUIVO: 60}
        assert origens["categoria"] == {NOME_ARQUIVO: 60}
        assert origens["titulo"] == {PDF: 59, NOME_ARQUIVO: 1}
