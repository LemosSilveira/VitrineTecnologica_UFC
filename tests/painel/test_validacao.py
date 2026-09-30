# -*- coding: utf-8 -*-
"""Regras dos campos do formulario (PRD secao 8).

A tabela da secao 8 tem uma linha por campo; aqui cada linha tem casos
validos e invalidos. Esta validacao e a que vale: a da interface serve so
para dar retorno imediato, e pode ter sido alterada pelo DevTools (T11).
"""
from __future__ import annotations

from datetime import date

import pytest

from painel.validacao import ANO_MIN, normaliza_numero_do_formulario, valida
from vitrine_core.acervo import LIMITES

CATEGORIAS = {"alimentos": "Alimentos", "engenharias": "Engenharias"}


def rascunho(**troca):
    """Formulario minimo valido para uma patente nova."""
    base = {
        "numero": "BR 10 2025 012345 6",
        "categoria": "Alimentos",
        "titulo": "Um titulo com tamanho aceitavel",
        "secoes": {
            "oQueE": "Uma descricao com pelo menos quarenta caracteres para passar."
        },
    }
    base.update(troca)
    return base


def val(dados, **kw):
    kw.setdefault("tem_capa", True)
    kw.setdefault("categorias", CATEGORIAS)
    return valida(dados, **kw)


class TestCaminhoFeliz:
    def test_minimo_valido(self):
        r = val(rascunho())
        assert r.ok, r.erros
        assert r.dados["numero"] == "BR 10 2025 012345-6"
        assert r.dados["tipo"]["sigla"] == "PI"
        assert r.dados["ano"] == 2025

    def test_avisa_que_nao_tem_pdf(self):
        r = val(rascunho())
        assert "pdf" in r.avisos

    def test_sem_aviso_quando_tem_pdf(self):
        assert "pdf" not in val(rascunho(), tem_pdf=True).avisos

    def test_dados_nao_sao_um_objeto(self):
        for bruto in (None, "x", 123, []):
            r = val(bruto)
            assert not r.ok


class TestNumero:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("BR 10 2025 012345 6", "BR 10 2025 012345-6"),
            ("BR 10 2025 012345-6", "BR 10 2025 012345-6"),
            ("br1020250123456", "BR 10 2025 012345-6"),
            ("  BR  20  2019  000001  2  ", "BR 20 2019 000001-2"),
            ("Pedido BR 10 2020 111111 3 depositado", "BR 10 2020 111111-3"),
        ],
    )
    def test_formatos_aceitos(self, entrada, esperado):
        assert normaliza_numero_do_formulario(entrada) == esperado

    @pytest.mark.parametrize(
        "entrada",
        ["", None, "BR 30 2025 012345 6", "BR 10 202 012345 6", "12345", "xyz"],
    )
    def test_formatos_recusados(self, entrada):
        assert normaliza_numero_do_formulario(entrada) is None
        assert "numero" in val(rascunho(numero=entrada)).erros

    def test_tipo_sai_da_especie(self):
        assert val(rascunho(numero="BR 20 2025 012345 6")).dados["tipo"]["sigla"] == "MU"

    def test_ano_antigo_demais(self):
        r = val(rascunho(numero=f"BR 10 {ANO_MIN - 1} 012345 6"))
        assert "numero" in r.erros and "ano" in r.erros["numero"]

    def test_ano_no_futuro(self):
        r = val(rascunho(numero=f"BR 10 {date.today().year + 2} 012345 6"))
        assert "numero" in r.erros

    def test_ano_que_vem_e_aceito(self):
        """O pedido depositado no fim do ano entra no sistema com data do ano
        seguinte."""
        r = val(rascunho(numero=f"BR 10 {date.today().year + 1} 012345 6"))
        assert "numero" not in r.erros

    def test_numero_duplicado(self):
        r = val(
            rascunho(),
            numeros_existentes={"BR 10 2025 012345-6": 42},
        )
        assert "numero" in r.erros
        assert "42" in r.erros["numero"]

    def test_a_lixeira_tambem_conta(self):
        """Reaproveitar o numero criaria duas patentes com o mesmo pedido no
        INPI; a mensagem precisa deixar claro que a lixeira conta."""
        r = val(rascunho(), numeros_existentes={"BR 10 2025 012345-6": 12})
        assert "lixeira" in r.erros["numero"]

    def test_em_edicao_o_numero_nao_e_validado(self):
        """Editando, o numero vem do nome da pasta e nao e editavel."""
        r = val(rascunho(numero="lixo"), id_editando=5)
        assert "numero" not in r.erros
        assert "numero" not in r.dados


class TestCategoria:
    def test_precisa_estar_na_lista(self):
        r = val(rascunho(categoria="Astrologia"))
        assert "categoria" in r.erros

    def test_vazia(self):
        assert "categoria" in val(rascunho(categoria="")).erros

    def test_area_valida(self):
        assert val(rascunho(categoria="Engenharias")).dados["categoria"] == "Engenharias"


class TestTitulo:
    def test_obrigatorio(self):
        assert "titulo" in val(rascunho(titulo="")).erros

    def test_curto_demais(self):
        r = val(rascunho(titulo="curto"))
        assert "titulo" in r.erros and "curto" in r.erros["titulo"]

    def test_longo_demais(self):
        r = val(rascunho(titulo="a" * (LIMITES["titulo"][1] + 1)))
        assert "titulo" in r.erros and "longo" in r.erros["titulo"]

    def test_nos_limites_exatos(self):
        lo, hi = LIMITES["titulo"]
        assert val(rascunho(titulo="a" * lo)).ok
        assert val(rascunho(titulo="a" * hi)).ok

    def test_maiusculas_e_aviso_nao_erro(self):
        """A interface oferece "Converter para caixa de frase"; recusar
        travaria quem colou o titulo de um documento em caixa alta."""
        r = val(rascunho(titulo="TITULO TODO EM MAIUSCULAS AQUI"))
        assert r.ok
        assert "titulo" in r.avisos

    def test_quebra_de_linha_vira_espaco(self):
        r = val(rascunho(titulo="Titulo com\nquebra no meio"))
        assert r.dados["titulo"] == "Titulo com quebra no meio"

    def test_caractere_bidi_e_removido(self):
        r = val(rascunho(titulo="Titulo com bidi‮ escondido"))
        assert "‮" not in r.dados["titulo"]

    def test_o_tamanho_vale_para_o_texto_limpo(self):
        assert "titulo" in val(rascunho(titulo="   curto   ")).erros


class TestSecoes:
    def test_oQueE_obrigatorio(self):
        assert "secoes.oQueE" in val(rascunho(secoes={})).erros

    def test_oQueE_curto_demais(self):
        r = val(rascunho(secoes={"oQueE": "curto"}))
        assert "secoes.oQueE" in r.erros

    def test_opcionais_podem_faltar(self):
        assert val(rascunho()).ok

    @pytest.mark.parametrize("campo", ["problema", "exemploDeUso", "beneficio"])
    def test_opcional_longo_demais(self, campo):
        r = val(rascunho(secoes={"oQueE": "a" * 50, campo: "b" * 901}))
        assert f"secoes.{campo}" in r.erros

    def test_secoes_de_outro_tipo(self):
        assert "secoes" in val(rascunho(secoes="texto")).erros


class TestDiferenciais:
    def test_lista_valida(self):
        r = val(rascunho(secoes={"oQueE": "a" * 50, "diferenciais": ["Bom item", "Outro"]}))
        assert r.dados["secoes"]["diferenciais"] == ["Bom item", "Outro"]

    def test_acima_de_8(self):
        itens = [f"Item numero {i}" for i in range(9)]
        r = val(rascunho(secoes={"oQueE": "a" * 50, "diferenciais": itens}))
        assert "secoes.diferenciais" in r.erros

    def test_exatamente_8(self):
        itens = [f"Item numero {i}" for i in range(8)]
        assert val(rascunho(secoes={"oQueE": "a" * 50, "diferenciais": itens})).ok

    def test_item_curto(self):
        r = val(rascunho(secoes={"oQueE": "a" * 50, "diferenciais": ["Bom item", "x"]}))
        assert "secoes.diferenciais.1" in r.erros

    def test_item_longo(self):
        r = val(rascunho(secoes={"oQueE": "a" * 50, "diferenciais": ["a" * 201]}))
        assert "secoes.diferenciais.0" in r.erros

    def test_linha_em_branco_e_ignorada(self):
        """O editor de diferenciais permite acrescentar uma linha vazia; ela
        nao deveria virar erro nem item."""
        r = val(rascunho(secoes={"oQueE": "a" * 50, "diferenciais": ["Bom item", "", "  "]}))
        assert r.ok
        assert r.dados["secoes"]["diferenciais"] == ["Bom item"]

    def test_de_outro_tipo(self):
        r = val(rascunho(secoes={"oQueE": "a" * 50, "diferenciais": "um; dois"}))
        assert "secoes.diferenciais" in r.erros


class TestTrl:
    def test_ausente_e_valido(self):
        r = val(rascunho())
        assert r.ok and "trl" not in r.dados

    def test_faixa_valida(self):
        r = val(rascunho(trl={"min": 5, "max": 6, "estimado": True}))
        assert r.dados["trl"] == {"min": 5, "max": 6, "estimado": True}

    def test_invertido(self):
        r = val(rascunho(trl={"min": 7, "max": 3}))
        assert "trl" in r.erros and "maior" in r.erros["trl"]

    @pytest.mark.parametrize("v", [0, 10, -1])
    def test_fora_da_faixa(self, v):
        assert "trl" in val(rascunho(trl={"min": v, "max": 9})).erros

    @pytest.mark.parametrize("v", ["5", 5.5, None, True])
    def test_nao_inteiro(self, v):
        """True merece atencao: bool e subclasse de int em Python, e um
        isinstance desatento aceitaria `true` como TRL 1."""
        assert "trl" in val(rascunho(trl={"min": v, "max": 9})).erros

    def test_estimado_de_outro_tipo(self):
        r = val(rascunho(trl={"min": 1, "max": 2, "estimado": "sim"}))
        assert "trl" in r.erros

    def test_trl_de_outro_tipo(self):
        assert "trl" in val(rascunho(trl="TRL 5-6")).erros


class TestCapa:
    def test_obrigatoria_em_patente_nova(self):
        assert "capa" in val(rascunho(), tem_capa=False).erros

    def test_nao_obrigatoria_em_edicao(self):
        """Editando, a capa que ja esta no acervo continua valendo."""
        r = val(rascunho(), tem_capa=False, id_editando=3)
        assert "capa" not in r.erros
