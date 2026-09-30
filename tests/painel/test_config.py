# -*- coding: utf-8 -*-
"""Configuracao do painel e validacao das duas pastas do projeto."""
from __future__ import annotations

import json

import pytest

from painel import config


class TestOndeAsCoisasFicam:
    def test_dados_e_local_sao_pastas_diferentes(self, ambiente):
        assert config.pasta_dados() != config.pasta_local()

    def test_o_que_nao_pode_ser_perdido_fica_em_appdata(self, ambiente):
        """Backups e historico ficam em %APPDATA%: atualizar o programa
        substitui a pasta dele, e o historico precisa sobreviver a isso."""
        assert config.pasta_backups().is_relative_to(ambiente.appdata)
        assert config.caminho_auditoria().is_relative_to(ambiente.appdata)
        assert config.caminho_config().is_relative_to(ambiente.appdata)

    def test_o_descartavel_fica_em_localappdata(self, ambiente):
        assert config.pasta_quarentena().is_relative_to(ambiente.local)
        assert config.pasta_pacotes().is_relative_to(ambiente.local)
        assert config.caminho_trava().is_relative_to(ambiente.local)
        assert config.caminho_log().is_relative_to(ambiente.local)

    def test_nada_e_gravado_dentro_do_repositorio(self, ambiente):
        """Um arquivo do painel dentro do site iria para o pacote de
        publicacao se a lista de permissoes algum dia crescer."""
        for p in (
            config.pasta_backups(),
            config.pasta_quarentena(),
            config.caminho_auditoria(),
            config.caminho_config(),
        ):
            assert not p.is_relative_to(ambiente.site)
            assert not p.is_relative_to(ambiente.acervo)


class TestValidaPastaSite:
    def test_pasta_da_vitrine_passa(self, ambiente):
        assert config.valida_pasta_site(str(ambiente.site)) == ambiente.site

    def test_pasta_qualquer_e_recusada(self, ambiente, tmp_path):
        outra = tmp_path / "documentos"
        outra.mkdir()
        with pytest.raises(config.ErroDeConfig, match="index.html"):
            config.valida_pasta_site(str(outra))

    def test_falta_de_uma_marca_ja_recusa(self, ambiente):
        (ambiente.site / "js" / "data" / "patentes.js").unlink()
        with pytest.raises(config.ErroDeConfig, match="patentes.js"):
            config.valida_pasta_site(str(ambiente.site))

    def test_pasta_inexistente(self, tmp_path):
        with pytest.raises(config.ErroDeConfig, match="nao existe"):
            config.valida_pasta_site(str(tmp_path / "nao-existe"))

    @pytest.mark.parametrize("valor", [None, 123, "", "   ", [], {}, True])
    def test_tipo_errado(self, valor):
        with pytest.raises(config.ErroDeConfig):
            config.valida_pasta_site(valor)

    def test_caminho_absurdamente_longo(self):
        with pytest.raises(config.ErroDeConfig, match="longo"):
            config.valida_pasta_site("C:\\" + "a" * 5000)


class TestValidaPastaAcervo:
    def test_acervo_com_uma_pasta_no_padrao_passa(self, ambiente):
        ambiente.add_patente(1)
        assert config.valida_pasta_acervo(str(ambiente.acervo)) == ambiente.acervo

    def test_acervo_vazio_e_recusado(self, ambiente):
        with pytest.raises(config.ErroDeConfig, match="acervo"):
            config.valida_pasta_acervo(str(ambiente.acervo))

    def test_pasta_fora_do_padrao_nao_conta(self, ambiente):
        (ambiente.acervo / "minhas fichas").mkdir()
        with pytest.raises(config.ErroDeConfig, match="padrao"):
            config.valida_pasta_acervo(str(ambiente.acervo))

    def test_so_a_lixeira_nao_conta(self, ambiente):
        """Um acervo em que todas as patentes foram excluidas nao e um acervo
        valido para configurar: provavelmente e a pasta errada."""
        (ambiente.acervo / "_lixeira" / "1. BR 10 2020 000001 1").mkdir(parents=True)
        with pytest.raises(config.ErroDeConfig):
            config.valida_pasta_acervo(str(ambiente.acervo))


class TestValidaParDePastas:
    def test_par_valido(self, ambiente):
        ambiente.add_patente(1)
        s, a = config.valida_par_de_pastas(str(ambiente.site), str(ambiente.acervo))
        assert (s, a) == (ambiente.site, ambiente.acervo)

    def test_mesma_pasta(self, ambiente):
        ambiente.add_patente(1)
        with pytest.raises(config.ErroDeConfig, match="mesma pasta"):
            config.valida_par_de_pastas(str(ambiente.site), str(ambiente.site))

    def test_acervo_dentro_do_site(self, ambiente):
        """As fichas originais tem centenas de MB e os metadados de quem as
        gerou: dentro do site, iriam para o ar junto com a vitrine."""
        dentro = ambiente.site / "acervo"
        dentro.mkdir()
        (dentro / "1. BR 10 2020 000001 1").mkdir()
        with pytest.raises(config.ErroDeConfig, match="dentro da pasta do site"):
            config.valida_par_de_pastas(str(ambiente.site), str(dentro))

    def test_site_dentro_do_acervo(self, ambiente, tmp_path):
        ambiente.add_patente(1)
        dentro = ambiente.acervo / "site"
        dentro.mkdir()
        (dentro / "index.html").write_text("x", encoding="utf-8")
        (dentro / "js" / "data").mkdir(parents=True)
        (dentro / "js" / "data" / "patentes.js").write_text("x", encoding="utf-8")
        (dentro / "scripts").mkdir()
        (dentro / "scripts" / "build_patentes.py").write_text("x", encoding="utf-8")
        with pytest.raises(config.ErroDeConfig, match="dentro do acervo"):
            config.valida_par_de_pastas(str(dentro), str(ambiente.acervo))


class TestConfigJson:
    def test_ida_e_volta(self, ambiente):
        ambiente.add_patente(1)
        cfg = config.Config(
            pastaSite=str(ambiente.site),
            pastaAcervo=str(ambiente.acervo),
            proximoPasso="Envie o zip para a STI.",
        )
        config.salva(cfg)
        lido = config.carrega()
        assert lido.pastaSite == str(ambiente.site)
        assert lido.proximoPasso == "Envie o zip para a STI."
        assert lido.versao == config.VERSAO_CONFIG

    def test_arquivo_ausente_devolve_vazia(self, ambiente):
        assert config.carrega().completa() is False

    def test_arquivo_corrompido_devolve_vazia(self, ambiente):
        """Sem excecao: o painel abre na tela de primeira execucao, que e o
        comportamento certo tanto na estreia quanto depois de um arquivo
        corrompido."""
        config.caminho_config().parent.mkdir(parents=True, exist_ok=True)
        config.caminho_config().write_text("{ nao fecha", encoding="utf-8")
        assert config.carrega().pastaSite == ""

    def test_campo_desconhecido_no_arquivo_e_ignorado(self, ambiente):
        config.caminho_config().parent.mkdir(parents=True, exist_ok=True)
        config.caminho_config().write_text(
            json.dumps({"pastaSite": "x", "inventado": 1}), encoding="utf-8"
        )
        assert config.carrega().pastaSite == "x"

    def test_completa_confere_as_pastas_de_novo(self, ambiente):
        """A pasta pode ter sido movida ou renomeada desde a ultima sessao."""
        ambiente.add_patente(1)
        cfg = config.Config(
            pastaSite=str(ambiente.site), pastaAcervo=str(ambiente.acervo)
        )
        assert cfg.completa() is True

        cfg.pastaAcervo = str(ambiente.acervo / "sumiu")
        assert cfg.completa() is False

    def test_gravacao_e_atomica(self, ambiente):
        """Nao pode sobrar .tmp ao lado do config.json."""
        ambiente.add_patente(1)
        config.salva(config.Config(pastaSite=str(ambiente.site)))
        nomes = sorted(p.name for p in config.pasta_dados().iterdir())
        assert nomes == ["config.json"]
