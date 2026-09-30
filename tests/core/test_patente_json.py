# -*- coding: utf-8 -*-
"""Esquema do `patente.json` -- a sobreposicao que o painel grava (PRD 4.3).

O arquivo e escrito por software, mas validado como se viesse de um
atacante: e ele que carrega o texto que vai para a vitrine publica, e a
equipe pode editar o JSON a mao num aperto.
"""
from __future__ import annotations

import json

import pytest

from vitrine_core.acervo import (
    LIMITES,
    PatenteJsonInvalido,
    Sobreposicao,
    le_patente_json,
)

CATEGORIAS = {"alimentos": "Alimentos", "engenharias": "Engenharias"}


@pytest.fixture
def grava(tmp_path):
    """Grava um patente.json na pasta temporaria e devolve a pasta.

    Aceita um dict (serializado) ou uma string crua, para poder testar JSON
    malformado. E uma funcao, e nao um atributo pendurado no `tmp_path`,
    porque `pathlib.Path` usa __slots__ e nao aceita atributos novos.
    """

    def _grava(dados):
        alvo = tmp_path / "patente.json"
        if isinstance(dados, str):
            alvo.write_text(dados, encoding="utf-8")
        else:
            alvo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        return tmp_path

    return _grava


def base(**campos):
    return {"versao": 1, "campos": campos}


class TestAusenteOuMinimo:
    def test_sem_arquivo_devolve_none(self, tmp_path):
        """O caso das 60 patentes atuais: elas so ganham um patente.json
        quando alguem as edita pelo painel."""
        assert le_patente_json(tmp_path) is None

    def test_minimo_valido(self, grava):
        s = le_patente_json(grava({"versao": 1}))
        assert isinstance(s, Sobreposicao)
        assert s.oculta is False
        assert s.campos == {}

    def test_campos_opcionais_do_painel_sao_aceitos(self, grava):
        s = le_patente_json(
            grava(
                {
                    "versao": 1,
                    "atualizadoEm": "2026-09-29T14:02:11-03:00",
                    "atualizadoPor": "usuario.windows",
                }
            )
        )
        assert s.campos == {}


class TestErrosDeEstrutura:
    def test_json_quebrado(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="JSON"):
            le_patente_json(grava("{ nao fecha"))

    def test_nao_e_objeto(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="objeto"):
            le_patente_json(grava("[1, 2]"))

    @pytest.mark.parametrize("versao", [None, 0, 2, "1", 1.0])
    def test_versao_errada(self, grava, versao):
        with pytest.raises(PatenteJsonInvalido, match="versao"):
            le_patente_json(grava({"versao": versao}))

    @pytest.mark.parametrize("valor", ["true", 1, None, "sim"])
    def test_oculta_precisa_ser_booleano(self, grava, valor):
        with pytest.raises(PatenteJsonInvalido, match="oculta"):
            le_patente_json(grava({"versao": 1, "oculta": valor}))

    def test_oculta_true(self, grava):
        assert le_patente_json(grava({"versao": 1, "oculta": True})).oculta is True


class TestCamposDesconhecidos:
    """Campo desconhecido e ERRO, nao algo a ignorar.

    Um `titluo` com erro de digitacao passaria despercebido para sempre: a
    equipe veria a correcao salva no arquivo e a vitrine continuaria com o
    titulo velho, sem ninguem entender por que.
    """

    def test_na_raiz(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="desconhecido"):
            le_patente_json(grava({"versao": 1, "inventado": 1}))

    def test_em_campos(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="titluo"):
            le_patente_json(grava(base(titluo="x" * 20)))

    def test_em_secoes(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="desconhecido"):
            le_patente_json(grava(base(secoes={"oQue": "x" * 50})))

    def test_em_trl(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="desconhecido"):
            le_patente_json(grava(base(trl={"min": 1, "max": 2, "extra": 3})))

    def test_a_mensagem_lista_o_que_era_esperado(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="titulo"):
            le_patente_json(grava(base(titluo="x" * 20)))


class TestTitulo:
    def test_valido(self, grava):
        s = le_patente_json(grava(base(titulo="Um titulo aceitavel")))
        assert s.campos["titulo"] == "Um titulo aceitavel"

    def test_curto_demais(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="minimo"):
            le_patente_json(grava(base(titulo="curto")))

    def test_longo_demais(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="maximo"):
            le_patente_json(grava(base(titulo="a" * (LIMITES["titulo"][1] + 1))))

    def test_nos_limites_exatos(self, grava):
        lo, hi = LIMITES["titulo"]
        assert le_patente_json(grava(base(titulo="a" * lo))).campos["titulo"]
        assert le_patente_json(grava(base(titulo="a" * hi))).campos["titulo"]

    @pytest.mark.parametrize("valor", [123, None, [], {}, True])
    def test_precisa_ser_texto(self, grava, valor):
        with pytest.raises(PatenteJsonInvalido, match="texto"):
            le_patente_json(grava(base(titulo=valor)))

    def test_quebra_de_linha_vira_espaco(self, grava):
        s = le_patente_json(grava(base(titulo="Titulo com\nquebra de linha")))
        assert s.campos["titulo"] == "Titulo com quebra de linha"

    def test_caractere_bidi_e_removido(self, grava):
        """U+202E inverte visualmente o resto da linha: daria para escrever um
        titulo que PARECE outra coisa na vitrine (PRD 5.7)."""
        s = le_patente_json(grava(base(titulo="Titulo‮ invertido")))
        assert "‮" not in s.campos["titulo"]

    def test_caractere_de_controle_e_removido(self, grava):
        s = le_patente_json(grava(base(titulo="Titulo\x00com\x07nulo")))
        assert "\x00" not in s.campos["titulo"]

    def test_o_tamanho_e_medido_depois_da_limpeza(self, grava):
        """10 caracteres visiveis mais espacos nao viram um titulo valido de
        12: o limite vale para o texto que vai ao ar."""
        with pytest.raises(PatenteJsonInvalido, match="minimo"):
            le_patente_json(grava(base(titulo="  curto   ")))


class TestCategoria:
    def test_precisa_existir_no_mapa(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="nao existe"):
            le_patente_json(grava(base(categoria="Astrologia")), CATEGORIAS)

    def test_area_do_mapa_passa(self, grava):
        s = le_patente_json(grava(base(categoria="Alimentos")), CATEGORIAS)
        assert s.campos["categoria"] == "Alimentos"

    def test_sem_mapa_nao_valida_a_area(self, grava):
        """Quem chama sem o mapa (uma ferramenta de inspecao, por exemplo) le
        o arquivo sem exigir o dados/categorias.json."""
        s = le_patente_json(grava(base(categoria="Qualquer")))
        assert s.campos["categoria"] == "Qualquer"

    @pytest.mark.parametrize("valor", ["", "   ", 1, None])
    def test_vazia_ou_de_outro_tipo(self, grava, valor):
        with pytest.raises(PatenteJsonInvalido, match="categoria"):
            le_patente_json(grava(base(categoria=valor)), CATEGORIAS)


class TestSecoes:
    def test_secao_de_texto_valida(self, grava):
        s = le_patente_json(grava(base(secoes={"oQueE": "a" * 50})))
        assert s.campos["secoes"]["oQueE"] == "a" * 50

    def test_oQueE_curto_demais(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="secoes.oQueE"):
            le_patente_json(grava(base(secoes={"oQueE": "curto"})))

    def test_secao_longa_demais(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="maximo"):
            le_patente_json(grava(base(secoes={"problema": "a" * 901})))

    def test_null_apaga_a_secao_de_proposito(self, grava):
        """Distinguir "ausente" de "null" e o que permite apagar uma secao que
        veio do PDF: ausente = continua vindo do PDF, null = apagada."""
        s = le_patente_json(grava(base(secoes={"problema": None})))
        assert s.campos["secoes"]["problema"] is None
        assert "oQueE" not in s.campos["secoes"]

    def test_secoes_precisa_ser_objeto(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="secoes"):
            le_patente_json(grava(base(secoes=["oQueE"])))


class TestDiferenciais:
    def test_lista_valida(self, grava):
        s = le_patente_json(
            grava(base(secoes={"diferenciais": ["Primeiro", "Segundo"]}))
        )
        assert s.campos["secoes"]["diferenciais"] == ["Primeiro", "Segundo"]

    def test_no_maximo_8(self, grava):
        n = LIMITES["diferenciais_max"]
        ok = [f"Item {i}" for i in range(n)]
        assert len(le_patente_json(
            grava(base(secoes={"diferenciais": ok}))
        ).campos["secoes"]["diferenciais"]) == n

        with pytest.raises(PatenteJsonInvalido, match="maximo"):
            le_patente_json(grava(base(secoes={"diferenciais": ok + ["Mais um"]})))

    def test_item_curto_demais(self, grava):
        with pytest.raises(PatenteJsonInvalido, match=r"diferenciais\[1\]"):
            le_patente_json(grava(base(secoes={"diferenciais": ["Bom item", "x"]})))

    def test_item_longo_demais(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="maximo"):
            le_patente_json(grava(base(secoes={"diferenciais": ["a" * 201]})))

    def test_lista_vazia_vira_none(self, grava):
        s = le_patente_json(grava(base(secoes={"diferenciais": []})))
        assert s.campos["secoes"]["diferenciais"] is None

    def test_precisa_ser_lista(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="lista"):
            le_patente_json(grava(base(secoes={"diferenciais": "um; dois"})))


class TestTrl:
    def test_faixa_valida(self, grava):
        s = le_patente_json(grava(base(trl={"min": 5, "max": 6})))
        assert s.campos["trl"] == {"min": 5, "max": 6, "estimado": False}

    def test_texto_nunca_vem_do_json(self, grava):
        """`trl.texto` e sempre recalculado pelo build (PRD 4.3): aceitar o
        texto do arquivo deixaria a barra e o rotulo se contradizerem."""
        with pytest.raises(PatenteJsonInvalido, match="desconhecido"):
            le_patente_json(
                grava(base(trl={"min": 5, "max": 6, "texto": "TRL 9"}))
            )

    def test_estimado(self, grava):
        s = le_patente_json(grava(base(trl={"min": 4, "max": 4, "estimado": True})))
        assert s.campos["trl"]["estimado"] is True

    def test_null_apaga_o_trl(self, grava):
        s = le_patente_json(grava(base(trl=None)))
        assert s.campos["trl"] is None

    def test_min_maior_que_max(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="maior que"):
            le_patente_json(grava(base(trl={"min": 7, "max": 3})))

    @pytest.mark.parametrize("v", [0, 10, -1, 99])
    def test_fora_da_faixa_1_a_9(self, grava, v):
        with pytest.raises(PatenteJsonInvalido, match="TRL vai de"):
            le_patente_json(grava(base(trl={"min": v, "max": 9})))

    @pytest.mark.parametrize("v", ["5", 5.5, None, True])
    def test_precisa_ser_inteiro(self, grava, v):
        """`True` merece atencao: em Python bool e subclasse de int, entao um
        isinstance(v, int) desatento aceitaria `true` como TRL 1."""
        with pytest.raises(PatenteJsonInvalido, match="inteiro"):
            le_patente_json(grava(base(trl={"min": v, "max": 9})))

    def test_estimado_precisa_ser_booleano(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="estimado"):
            le_patente_json(grava(base(trl={"min": 1, "max": 2, "estimado": "sim"})))

    def test_trl_precisa_ser_objeto(self, grava):
        with pytest.raises(PatenteJsonInvalido, match="trl"):
            le_patente_json(grava(base(trl="TRL 5-6")))
