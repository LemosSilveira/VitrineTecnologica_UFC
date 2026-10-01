# -*- coding: utf-8 -*-
"""Normalizacao de texto, slugs e os regex do acervo.

Os casos vem das inconsistencias reais das 60 pastas, documentadas na tabela
"O que o build resolve sozinho" do README. Cada teste cita o ID que o
motivou, para que ninguem "simplifique" um regex e quebre uma pasta que
ninguem lembra que existe.
"""
from __future__ import annotations

import pytest

from vitrine_core.nomes import (
    ARQUIVO_RE,
    PASTA_RE,
    chave,
    normaliza_espacos,
    sem_acento,
    slugify,
    so_letras,
)


class TestNormalizacao:
    def test_sem_acento_preserva_a_letra(self):
        assert sem_acento("Ciências da Saúde") == "Ciencias da Saude"
        assert sem_acento("Compósito cerâmico") == "Composito ceramico"

    def test_sem_acento_nao_mexe_em_simbolo_sem_diacritico(self):
        # o tau do titulo da 12 nao e uma letra acentuada: tem de sobreviver
        assert sem_acento("τf") == "τf"

    def test_chave_colapsa_espaco_e_caixa(self):
        assert chave("  Ciências   da  SAÚDE ") == "ciencias da saude"

    def test_so_letras_descarta_pontuacao(self):
        assert so_letras("Molho Agridoce (v2)!") == "molhoagridocev2"

    def test_normaliza_espacos(self):
        assert normaliza_espacos("a  b\n c\t") == "a b c"

    @pytest.mark.parametrize("f", [sem_acento, chave, so_letras, normaliza_espacos])
    def test_string_vazia_nao_quebra(self, f):
        assert f("") == ""


class TestSlugify:
    def test_basico(self):
        assert slugify("Camarão em Pó Natural") == "camarao-em-po-natural"

    def test_pontuacao_vira_um_hifen_so(self):
        assert slugify("Molho  Agridoce — com  Hortaliças!") == (
            "molho-agridoce-com-hortalicas"
        )

    def test_nao_deixa_hifen_nas_pontas(self):
        assert slugify("  -- Título -- ") == "titulo"

    def test_corta_no_limite_sem_partir_palavra(self):
        s = slugify("abcdef ghijkl mnopqr", limite=14)
        assert s == "abcdef"
        assert not s.endswith("-")

    def test_palavra_unica_maior_que_o_limite_e_cortada(self):
        # sem hifen para recuar, o corte seco e o unico comportamento possivel
        assert slugify("abcdefghijkl", limite=5) == "abcde"


class TestPastaRe:
    @pytest.mark.parametrize(
        "nome,pid,esp,ano,seq,dv",
        [
            ("1. BR 10 2014 030019 8", 1, "10", "2014", "030019", "8"),
            # ids 13, 18, 21, 22, 30...: "_" no fim da pasta
            ("13. BR 10 2019 001234 5_", 13, "10", "2019", "001234", "5"),
            # numero com hifen antes do digito verificador
            ("19. BR 10 2022 019303-7", 19, "10", "2022", "019303", "7"),
            # modelo de utilidade
            ("42. BR 20 2018 001111 2", 42, "20", "2018", "001111", "2"),
        ],
    )
    def test_aceita_as_variacoes_reais(self, nome, pid, esp, ano, seq, dv):
        m = PASTA_RE.match(normaliza_espacos(nome))
        assert m is not None
        assert int(m.group("id")) == pid
        assert (m.group("esp"), m.group("ano")) == (esp, ano)
        assert (m.group("seq"), m.group("dv")) == (seq, dv)

    @pytest.mark.parametrize(
        "nome",
        [
            "_lixeira",
            "BR 10 2014 030019 8",  # sem o ID da vitrine
            "1. BR 10 2014 03019 8",  # sequencia com 5 digitos
            "1. US 10 2014 030019 8",  # nao e BR
            "leia-me.txt",
            "",
        ],
    )
    def test_recusa_o_que_nao_e_pasta_de_patente(self, nome):
        assert PASTA_RE.match(normaliza_espacos(nome)) is None


class TestArquivoRe:
    def test_extrai_categoria_e_titulo(self):
        m = ARQUIVO_RE.match(
            "1. Alimentos - BR 10 2014 030019 8 - Camarão em Pó Natural"
        )
        assert m.group("cat").strip(" -") == "Alimentos"
        assert m.group("titulo").strip() == "Camarão em Pó Natural"

    def test_traco_antes_do_br_e_opcional(self):
        # a patente 48 nao tem o traco entre a categoria e o "BR"
        m = ARQUIVO_RE.match("48. Engenharias BR 10 2021 000001 1 - Titulo")
        assert m is not None
        assert m.group("cat").strip(" -") == "Engenharias"

    def test_prefixo_numerico_pode_divergir_da_pasta(self):
        # "037.", "048.", "4." aparecem nos arquivos; o ID vem sempre da pasta
        m = ARQUIVO_RE.match("037. Alimentos - BR 10 2019 000002 3 - Titulo")
        assert m.group("cat").strip(" -") == "Alimentos"

    def test_arquivo_sem_titulo_no_nome(self):
        # id 47: o titulo sai do texto do PDF, nao do nome
        m = ARQUIVO_RE.match("47. Química - BR 10 2020 000003 4 -")
        assert m is not None
        assert m.group("titulo").strip() == ""
