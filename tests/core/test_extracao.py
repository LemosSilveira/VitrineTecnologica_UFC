# -*- coding: utf-8 -*-
"""Fatiamento das secoes, limpeza de paragrafo, diferenciais, TRL e resumo.

Trabalha sobre o texto ja extraido do PDF, entao nao precisa de PyMuPDF nem
das fichas reais -- a conferencia contra as 60 fichas e o teste de ouro da
Fase 2.
"""
from __future__ import annotations

import pytest

from vitrine_core.extracao import (
    RESUMO_MAX,
    faz_resumo,
    limpa_diferenciais,
    limpa_paragrafo,
    parse_trl,
    secoes_do_pdf,
)

TRAVESSAO = "–"
RETICENCIAS = "…"
SOFT_HYPHEN = "­"


class TestSecoesDoPdf:
    FICHA = (
        "Titulo qualquer\n"
        "O que é?\nUm ingrediente em po.\n"
        "Problema que resolve\nFalta de praticidade.\n"
        "Exemplo de uso\nMolhos e sopas.\n"
        "Diferenciais competitivos\n✅ Alto teor proteico\n✅ Sabor natural\n"
        "Benefício principal\nAgrega sabor.\n"
        "Nível de maturidade\nTRL 5-6\n"
    )

    def test_separa_as_cinco_secoes_e_o_trl(self):
        bruto, avisos = secoes_do_pdf(self.FICHA)
        assert avisos == []
        assert bruto["oQueE"].strip() == "Um ingrediente em po."
        assert bruto["problema"].strip() == "Falta de praticidade."
        assert bruto["exemploDeUso"].strip() == "Molhos e sopas."
        assert "Alto teor proteico" in bruto["diferenciais"]
        assert bruto["beneficio"].strip() == "Agrega sabor."
        assert "TRL 5-6" in bruto["_trl"]

    def test_cabecalho_ausente_vira_aviso_sem_quebrar_o_resto(self):
        texto = self.FICHA.replace("Exemplo de uso\nMolhos e sopas.\n", "")
        bruto, avisos = secoes_do_pdf(texto)
        assert any("Exemplo de uso" in a for a in avisos)
        assert "exemploDeUso" not in bruto
        assert bruto["problema"].strip() == "Falta de praticidade."

    def test_texto_vazio_avisa_de_todas(self):
        bruto, avisos = secoes_do_pdf("")
        assert bruto == {}
        assert len(avisos) == 6

    def test_a_ultima_secao_vai_ate_o_fim(self):
        bruto, _ = secoes_do_pdf("Nível de maturidade\nTRL 9 (estimado)")
        assert bruto["_trl"].strip() == "TRL 9 (estimado)"


class TestLimpaParagrafo:
    def test_junta_linhas_com_espaco(self):
        assert limpa_paragrafo("uma frase\nquebrada em duas") == "uma frase quebrada em duas"

    def test_hifen_no_fim_da_linha_cola_a_palavra(self):
        assert limpa_paragrafo("micro-\nondas") == "micro-ondas"

    def test_remove_hifen_condicional_invisivel(self):
        assert limpa_paragrafo(f"pala{SOFT_HYPHEN}vra") == "palavra"

    def test_descarta_linhas_em_branco(self):
        assert limpa_paragrafo("a\n\n\n  \nb") == "a b"

    def test_vazio(self):
        assert limpa_paragrafo("") == ""


class TestLimpaDiferenciais:
    @pytest.mark.parametrize("marcador", ["✅", "✔", "☑", "▪", "•", "-"])
    def test_reconhece_todos_os_marcadores(self, marcador):
        s = f"{marcador} Primeiro\n{marcador} Segundo"
        assert limpa_diferenciais(s) == ["Primeiro", "Segundo"]

    def test_continuacao_sem_marcador_entra_no_item_anterior(self):
        s = "✅ Um item que\ncontinua na linha de baixo\n✅ Outro"
        assert limpa_diferenciais(s) == ["Um item que continua na linha de baixo", "Outro"]

    def test_tira_ponto_e_virgula_do_fim(self):
        assert limpa_diferenciais("✅ Alto teor proteico;") == ["Alto teor proteico"]

    def test_texto_sem_marcador_nenhum_vira_um_item(self):
        assert limpa_diferenciais("so uma linha solta") == ["so uma linha solta"]

    def test_vazio_vira_lista_vazia(self):
        assert limpa_diferenciais("") == []
        assert limpa_diferenciais("\n  \n") == []


class TestParseTrl:
    def test_valor_unico(self):
        assert parse_trl("TRL 4") == {
            "min": 4, "max": 4, "estimado": False, "texto": "TRL 4",
        }

    @pytest.mark.parametrize("sep", ["-", "–", "—", " - ", " – "])
    def test_faixa_com_qualquer_travessao(self, sep):
        t = parse_trl(f"TRL 5{sep}6")
        assert (t["min"], t["max"]) == (5, 6)
        assert t["texto"] == f"TRL 5{TRAVESSAO}6"

    def test_faixa_invertida_e_corrigida(self):
        t = parse_trl("TRL 7-3")
        assert (t["min"], t["max"]) == (3, 7)
        assert t["texto"] == f"TRL 3{TRAVESSAO}7"

    def test_estimado_entra_no_texto(self):
        t = parse_trl("TRL 5-6 (estimado)")
        assert t["estimado"] is True
        assert t["texto"] == f"TRL 5{TRAVESSAO}6 (estimado)"

    def test_estimada_no_feminino_tambem_conta(self):
        # "estimad" e o prefixo comum a estimado/estimada/estimativa
        assert parse_trl("TRL 4 — maturidade estimada")["estimado"] is True

    @pytest.mark.parametrize("s", ["", "sem nivel declarado", "TRL"])
    def test_sem_trl_devolve_none(self, s):
        assert parse_trl(s) is None


class TestFazResumo:
    def test_texto_curto_passa_inteiro(self):
        assert faz_resumo("uma frase curta") == "uma frase curta"

    def test_texto_longo_e_cortado_com_reticencias(self):
        r = faz_resumo("palavra " * 60)
        assert r.endswith(RETICENCIAS)
        assert len(r) <= RESUMO_MAX + 1

    def test_nao_corta_no_meio_da_palavra(self):
        r = faz_resumo("abcdefgh " * 30)
        assert " " not in r[-2:]
        assert not r.removesuffix(RETICENCIAS).endswith("abcdefg")

    def test_tira_pontuacao_solta_antes_das_reticencias(self):
        r = faz_resumo("a" * 155 + " , mais texto depois do limite")
        assert not r.removesuffix(RETICENCIAS).endswith(",")

    def test_no_limite_exato_nao_ganha_reticencias(self):
        assert faz_resumo("x" * RESUMO_MAX) == "x" * RESUMO_MAX
