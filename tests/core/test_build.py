# -*- coding: utf-8 -*-
"""Serializacao do patentes.js e paridade com o build legado.

A parte mais delicada e `js_string`: o `patentes.js` e carregado como script
classico, entao um caractere mal escapado vindo de uma ficha nao da erro de
dados -- quebra o arquivo inteiro e a vitrine fica vazia.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from vitrine_core.build import js_string, serializa

# Escritos como escape de proposito: U+2028 e U+2029 sao invisiveis, e um
# deles colado como espaco comum por engano faria o teste passar sem testar
# nada.
U2028 = " "
U2029 = " "


class TestJsString:
    def test_texto_simples(self):
        assert js_string("simples") == '"simples"'

    def test_acento_e_simbolo_passam_intactos(self):
        # o arquivo e UTF-8: nao ha motivo para escapar acento
        assert js_string("Compósito (τf)") == '"Compósito (τf)"'

    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ('aspas "aqui"', r'"aspas \"aqui\""'),
            ("barra \\ invertida", r'"barra \\ invertida"'),
            ("quebra\nde linha", r'"quebra\nde linha"'),
            ("retorno\rcarro", r'"retorno\rcarro"'),
            ("tab\taqui", r'"tab\taqui"'),
        ],
    )
    def test_escapes_basicos(self, entrada, esperado):
        assert js_string(entrada) == esperado

    @pytest.mark.parametrize(
        "ch,escape", [(U2028, "\\u2028"), (U2029, "\\u2029")]
    )
    def test_separadores_de_linha_do_javascript(self, ch, escape):
        """U+2028 e U+2029 terminam uma linha para o parser de JS, mesmo
        dentro de uma string entre aspas. Sem escapar, quebram o arquivo."""
        assert js_string(f"a{ch}b") == f'"a{escape}b"'

    def test_nao_fecha_a_tag_script(self):
        assert js_string("texto </script> mais") == r'"texto <\/script> mais"'

    def test_barra_e_escapada_antes_das_aspas(self):
        # ordem importa: escapar as aspas primeiro produziria \\" e quebraria
        assert js_string('\\"') == r'"\\\""'

    def test_vazio(self):
        assert js_string("") == '""'


PATENTE = {
    "id": 1,
    "slug": "1-teste",
    "numero": "BR 10 2014 030019-8",
    "ano": 2014,
    "tipo": {"sigla": "PI", "nome": "Patente de Invenção"},
    "categoria": "Alimentos",
    "titulo": "Título",
    "resumo": "Resumo",
    "secoes": {"oQueE": "Algo", "diferenciais": ["um", "dois"], "beneficio": None},
    "trl": {"min": 5, "max": 6, "estimado": False, "texto": "TRL 5–6"},
    "imagens": {"dimensoesCapa": [800, 800]},
    "pdf": None,
}
CATEGORIAS = [{"nome": "Alimentos", "total": 1}]


class TestSerializa:
    @pytest.fixture
    def js(self):
        return serializa([PATENTE], CATEGORIAS)

    def test_cabecalho_avisa_que_o_arquivo_e_gerado(self, js):
        assert js.startswith("/* ARQUIVO GERADO por scripts/build_patentes.py")

    def test_define_as_duas_globais(self, js):
        assert "window.PATENTES = [" in js
        assert "window.CATEGORIAS = [" in js

    def test_termina_com_quebra_de_linha(self, js):
        assert js.endswith("];\n")

    def test_none_vira_null(self, js):
        assert "beneficio: null" in js
        assert "pdf: null" in js
        assert "None" not in js

    def test_booleano_vira_minusculo(self, js):
        assert "estimado: false" in js
        assert "False" not in js

    def test_lista_so_de_numeros_fica_em_uma_linha(self, js):
        assert "dimensoesCapa: [800, 800]" in js

    def test_lista_de_textos_fica_em_varias_linhas(self, js):
        assert "diferenciais: [\n" in js
        assert '"um",\n' in js
        assert '"dois"\n' in js

    def test_listas_vazias(self):
        js = serializa([], [])
        assert "window.PATENTES = [\n];" in js
        assert "window.CATEGORIAS = [\n];" in js

    def test_categoria_com_acento_no_nome(self):
        js = serializa([], [{"nome": "Ciências da Saúde", "total": 4}])
        assert '{ nome: "Ciências da Saúde", total: 4 }' in js

    def test_tipo_nao_suportado_erra_em_vez_de_gerar_lixo(self):
        with pytest.raises(TypeError):
            serializa([{"x": {1, 2}}], [])


class TestParidadeComOLegado:
    """As funcoes puras precisam dar exatamente o mesmo resultado de antes.

    `tests/fixtures/build_legado.py` e a copia do build de antes da extracao
    do pacote (PRD 6.1). Enquanto este teste passar, a refatoracao nao mudou
    comportamento nenhum -- e se um dia uma mudanca for intencional, ela tem
    de aparecer aqui e ser justificada, nao passar despercebida.
    """

    AMOSTRAS = [
        "",
        "simples",
        'com "aspas" e \\ barra',
        "linha1\nlinha2\ttab",
        f"separadores {U2028} e {U2029}",
        "</script>",
        "Compósito cerâmico estável para micro-ondas (τf próximo de zero)",
        "Ciências da Saúde",
        "  espacos   demais  ",
        "quebra-\nda palavra",
        "TRL 5-6 (estimado)",
        "TRL 7—3",
        "TRL 4",
        "sem nivel declarado",
        "✅ Item um\n✅ Item dois;\n  continuacao",
        "palavra " * 60,
        "A" * 300,
        "Molho Agridoce — com Hortaliças Não Convencionais!",
        "soft­hyphen no meio",
    ]

    @pytest.fixture(scope="class")
    @staticmethod
    def legado():
        caminho = Path(__file__).resolve().parents[1] / "fixtures" / "build_legado.py"
        spec = importlib.util.spec_from_file_location("build_legado", caminho)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["build_legado"] = mod  # @dataclass precisa achar o modulo
        spec.loader.exec_module(mod)
        return mod

    @pytest.mark.parametrize(
        "nome",
        [
            "sem_acento",
            "chave",
            "so_letras",
            "slugify",
            "normaliza_espacos",
            "js_string",
            "faz_resumo",
            "limpa_paragrafo",
            "limpa_diferenciais",
            "parse_trl",
        ],
    )
    def test_funcao_pura_da_o_mesmo_resultado(self, legado, nome):
        from vitrine_core import build, extracao, nomes

        atual = next(
            getattr(m, nome) for m in (nomes, extracao, build) if hasattr(m, nome)
        )
        antigo = getattr(legado, nome)

        for s in self.AMOSTRAS:
            assert atual(s) == antigo(s), f"{nome}({s!r})"

    def test_serializa_da_o_mesmo_arquivo(self, legado):
        assert serializa([PATENTE], CATEGORIAS) == legado.serializa([PATENTE], CATEGORIAS)

    def test_os_regex_sao_os_mesmos(self, legado):
        from vitrine_core.nomes import ARQUIVO_RE, PASTA_RE

        assert PASTA_RE.pattern == legado.PASTA_RE.pattern
        assert ARQUIVO_RE.pattern == legado.ARQUIVO_RE.pattern

    def test_o_mapa_de_areas_em_json_bate_com_a_constante_do_legado(self, legado):
        """O CATEGORIA_MAP saiu do codigo para dados/categorias.json (A5).
        O conteudo tem de ser o mesmo, senao o build classificaria diferente."""
        from vitrine_core.acervo import carrega_categorias

        assert carrega_categorias() == legado.CATEGORIA_MAP

    def test_as_secoes_da_ficha_sao_as_mesmas(self, legado):
        from vitrine_core.extracao import SECOES

        assert SECOES == legado.SECOES

    def test_os_tipos_do_inpi_sao_os_mesmos(self, legado):
        from vitrine_core.acervo import IMG_EXTS, TIPOS

        assert TIPOS == legado.TIPOS
        assert IMG_EXTS == legado.IMG_EXTS

    def test_as_constantes_de_imagem_sao_as_mesmas(self, legado):
        from vitrine_core import imagens

        for nome in (
            "WEBP_CAPA_Q",
            "WEBP_FICHA_LG_Q",
            "WEBP_FICHA_SM_Q",
            "CAPA_LARGURAS",
            "FICHA_ZOOM",
            "FICHA_SM_LARGURA",
        ):
            assert getattr(imagens, nome) == getattr(legado, nome), nome

    def test_os_limites_de_texto_sao_os_mesmos(self, legado):
        from vitrine_core.extracao import RESUMO_MAX
        from vitrine_core.nomes import SLUG_MAX

        assert RESUMO_MAX == legado.RESUMO_MAX
        assert SLUG_MAX == legado.SLUG_MAX
