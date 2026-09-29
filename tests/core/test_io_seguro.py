# -*- coding: utf-8 -*-
"""Escrita atomica, idempotencia e confinamento de caminho.

`dentro_de` e a barreira que impede a interface do painel de pedir uma
escrita fora do site ou do acervo (PRD 5.7). Os casos abaixo sao os do
modelo de ameacas T5.
"""
from __future__ import annotations

import os

import pytest

from vitrine_core.io_seguro import dentro_de, escreve_atomico, write_if_changed


class TestEscritaAtomica:
    def test_cria_o_arquivo_e_as_pastas(self, tmp_path):
        alvo = tmp_path / "a" / "b" / "c.txt"
        escreve_atomico(alvo, b"conteudo")
        assert alvo.read_bytes() == b"conteudo"

    def test_sobrescreve(self, tmp_path):
        alvo = tmp_path / "x.txt"
        escreve_atomico(alvo, b"antes")
        escreve_atomico(alvo, b"depois")
        assert alvo.read_bytes() == b"depois"

    def test_nao_deixa_temporario_para_tras(self, tmp_path):
        alvo = tmp_path / "x.txt"
        escreve_atomico(alvo, b"dados")
        assert [p.name for p in tmp_path.iterdir()] == ["x.txt"]

    def test_falha_no_meio_preserva_o_arquivo_anterior(self, tmp_path, monkeypatch):
        alvo = tmp_path / "patentes.js"
        escreve_atomico(alvo, b"versao boa")

        def explode(*a, **k):
            raise OSError("disco cheio")

        monkeypatch.setattr(os, "replace", explode)
        with pytest.raises(OSError):
            escreve_atomico(alvo, b"versao pela metade")

        assert alvo.read_bytes() == b"versao boa"
        # e nem o temporario sobra ao lado
        assert [p.name for p in tmp_path.iterdir()] == ["patentes.js"]


class TestWriteIfChanged:
    def test_primeira_escrita_devolve_true(self, tmp_path):
        assert write_if_changed(tmp_path / "a.txt", b"x") is True

    def test_conteudo_igual_nao_reescreve(self, tmp_path):
        alvo = tmp_path / "a.txt"
        write_if_changed(alvo, b"x")
        antes = alvo.stat().st_mtime_ns

        assert write_if_changed(alvo, b"x") is False
        # o mtime intacto e o que mantem o `git status` limpo entre builds
        assert alvo.stat().st_mtime_ns == antes

    def test_conteudo_diferente_reescreve(self, tmp_path):
        alvo = tmp_path / "a.txt"
        write_if_changed(alvo, b"x")
        assert write_if_changed(alvo, b"y") is True
        assert alvo.read_bytes() == b"y"

    def test_conteudo_vazio_e_valido(self, tmp_path):
        alvo = tmp_path / "a.txt"
        assert write_if_changed(alvo, b"") is True
        assert write_if_changed(alvo, b"") is False


class TestDentroDe:
    def test_arquivo_dentro(self, tmp_path):
        assert dentro_de(tmp_path, tmp_path / "sub" / "arquivo.txt")

    def test_a_propria_raiz_conta_como_dentro(self, tmp_path):
        assert dentro_de(tmp_path, tmp_path)

    def test_irmao_fica_de_fora(self, tmp_path):
        (tmp_path / "site").mkdir()
        (tmp_path / "acervo").mkdir()
        assert not dentro_de(tmp_path / "site", tmp_path / "acervo" / "x")

    @pytest.mark.parametrize(
        "relativo",
        ["..", "../fora.txt", "sub/../../fora.txt", "./sub/../..", "..\\..\\Windows"],
    )
    def test_path_traversal_e_recusado(self, tmp_path, relativo):
        raiz = tmp_path / "site"
        raiz.mkdir()
        assert not dentro_de(raiz, raiz / relativo)

    def test_prefixo_parecido_nao_engana(self, tmp_path):
        # "site-antigo" comeca com "site", mas nao esta dentro dele
        (tmp_path / "site").mkdir()
        (tmp_path / "site-antigo").mkdir()
        assert not dentro_de(tmp_path / "site", tmp_path / "site-antigo" / "x.txt")

    def test_caminho_absoluto_de_outro_lugar(self, tmp_path):
        assert not dentro_de(tmp_path, "C:\\Windows\\System32" if os.name == "nt" else "/etc")
