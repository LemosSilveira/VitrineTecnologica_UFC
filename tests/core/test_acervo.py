# -*- coding: utf-8 -*-
"""Leitura das pastas do acervo e do mapa de areas tecnologicas."""
from __future__ import annotations

import json

import pytest

from vitrine_core.acervo import (
    TIPOS,
    ErroDeConfiguracao,
    arquivos_da_pasta,
    carrega_categorias,
    caminho_categorias_padrao,
    lista_pastas,
)
from vitrine_core.nomes import chave


class TestTipos:
    def test_as_duas_especies_do_inpi(self):
        assert TIPOS["10"]["sigla"] == "PI"
        assert TIPOS["20"]["sigla"] == "MU"
        assert TIPOS["10"]["nome"] == "Patente de Invenção"
        assert TIPOS["20"]["nome"] == "Modelo de Utilidade"


class TestListaPastas:
    def test_ordena_por_id_numerico_e_nao_alfabetico(self, tmp_path):
        for nome in ["10. BR 10 2020 000001 1", "2. BR 10 2020 000002 2", "1. x"]:
            (tmp_path / nome).mkdir()
        assert [p.name[:3].strip(". ") for p in lista_pastas(tmp_path)] == ["1", "2", "10"]

    def test_ignora_arquivos_soltos(self, tmp_path):
        (tmp_path / "1. pasta").mkdir()
        (tmp_path / "leia-me.txt").write_text("x", encoding="utf-8")
        assert [p.name for p in lista_pastas(tmp_path)] == ["1. pasta"]

    def test_pasta_sem_prefixo_numerico_vai_para_o_fim(self, tmp_path):
        (tmp_path / "1. primeira").mkdir()
        (tmp_path / "sem numero").mkdir()
        assert [p.name for p in lista_pastas(tmp_path)][-1] == "sem numero"


class TestArquivosDaPasta:
    def test_classifica_por_extensao(self, tmp_path):
        for nome in ["ficha.pdf", "capa.png", "outra.JPG", "texto.docx"]:
            (tmp_path / nome).write_bytes(b"x")
        a = arquivos_da_pasta(tmp_path)
        assert [p.name for p in a.pdfs] == ["ficha.pdf"]
        assert [p.name for p in a.imagens] == ["capa.png", "outra.JPG"]
        assert [p.name for p in a.outros] == ["texto.docx"]

    def test_extensao_maiuscula_conta_como_imagem(self, tmp_path):
        (tmp_path / "CAPA.PNG").write_bytes(b"x")
        assert len(arquivos_da_pasta(tmp_path).imagens) == 1

    def test_ordem_estavel_com_varios_pdfs(self, tmp_path):
        for nome in ["b.pdf", "a.pdf", "c.pdf"]:
            (tmp_path / nome).write_bytes(b"x")
        # o build sempre usa o [0]: a escolha nao pode mudar entre execucoes
        assert [p.name for p in arquivos_da_pasta(tmp_path).pdfs] == [
            "a.pdf", "b.pdf", "c.pdf",
        ]

    def test_subpasta_nao_entra(self, tmp_path):
        (tmp_path / "sub").mkdir()
        a = arquivos_da_pasta(tmp_path)
        assert (a.pdfs, a.imagens, a.outros) == ([], [], [])


class TestCarregaCategorias:
    def test_o_arquivo_do_repositorio_carrega(self):
        mapa = carrega_categorias()
        assert mapa[chave("Alimentos")] == "Alimentos"
        assert mapa[chave("Ciencias da Saude")] == "Ciências da Saúde"
        # duas chaves apontando para o mesmo nome exibido
        assert mapa["quimico"] == mapa["quimicos"] == "Química"

    def test_cobre_as_10_areas_da_vitrine(self):
        assert len(set(carrega_categorias().values())) == 10

    def test_o_caminho_padrao_existe(self):
        assert caminho_categorias_padrao().is_file()

    def _grava(self, tmp_path, dados):
        p = tmp_path / "categorias.json"
        p.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        return p

    def test_arquivo_ausente_erra_com_o_caminho_na_mensagem(self, tmp_path):
        alvo = tmp_path / "nao-existe.json"
        with pytest.raises(ErroDeConfiguracao, match="nao-existe.json"):
            carrega_categorias(alvo)

    def test_json_invalido(self, tmp_path):
        p = tmp_path / "categorias.json"
        p.write_text("{ isto nao e json", encoding="utf-8")
        with pytest.raises(ErroDeConfiguracao, match="JSON"):
            carrega_categorias(p)

    def test_versao_desconhecida(self, tmp_path):
        p = self._grava(tmp_path, {"versao": 2, "mapa": {"a": "A"}})
        with pytest.raises(ErroDeConfiguracao, match="versao"):
            carrega_categorias(p)

    @pytest.mark.parametrize(
        "dados",
        [
            {"versao": 1},
            {"versao": 1, "mapa": {}},
            {"versao": 1, "mapa": []},
            {"versao": 1, "mapa": "alimentos"},
        ],
    )
    def test_mapa_ausente_ou_vazio(self, tmp_path, dados):
        p = self._grava(tmp_path, dados)
        with pytest.raises(ErroDeConfiguracao, match="mapa"):
            carrega_categorias(p)

    @pytest.mark.parametrize("mapa", [{"a": 1}, {"a": ""}, {"": "A"}, {"a": None}])
    def test_entrada_que_nao_e_texto_para_texto(self, tmp_path, mapa):
        p = self._grava(tmp_path, {"versao": 1, "mapa": mapa})
        with pytest.raises(ErroDeConfiguracao, match="texto"):
            carrega_categorias(p)

    def test_conteudo_que_nao_e_objeto(self, tmp_path):
        p = tmp_path / "categorias.json"
        p.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ErroDeConfiguracao, match="objeto"):
            carrega_categorias(p)
