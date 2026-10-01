# -*- coding: utf-8 -*-
"""Superficie da Api, caminhos maliciosos e destinos de lista fechada.

A `Api` e a fronteira de seguranca do painel: o pywebview expoe **todo metodo
publico** da classe passada em `js_api`. Estes testes existem para que ela
continue sendo exatamente a tabela 5.3 do PRD, e para que nenhum argumento
vindo da interface consiga escrever fora do site e do acervo (T5).
"""
from __future__ import annotations

import base64

import pytest

from painel import config
from painel.api import LINKS, PASTAS_ABRIVEIS, Api

# A tabela 5.3 do PRD, palavra por palavra. Acrescentar um metodo aqui e uma
# decisao de seguranca: passa a ser chamavel pelo JavaScript da janela.
SUPERFICIE = {
    "estado",
    "configurar",
    "escolher_pasta",
    "listar",
    "obter",
    "escolher_arquivo",
    "receber_arquivo",
    "ler_ficha",
    "ler_texto_ficha",
    "previa",
    "salvar",
    "alternar_oculta",
    "excluir",
    "rodar_build",
    "historico",
    "restaurar",
    "gerar_pacote",
    "abrir_pasta",
    "abrir_link",
    "ver_site_local",
}

# Argumentos hostis, usados em varredura contra todos os metodos.
#
# Os ids sao explicitos porque o pytest monta o nome do teste a partir do
# valor: o caso de 10 MB geraria um id de 10 MB e estouraria o limite de
# 32767 caracteres da variavel PYTEST_CURRENT_TEST no Windows.
HOSTIS = [
    pytest.param(None, id="None"),
    pytest.param(123, id="int"),
    pytest.param(-1, id="negativo"),
    pytest.param(True, id="bool"),
    pytest.param([], id="lista"),
    pytest.param({}, id="dict"),
    pytest.param("", id="vazio"),
    pytest.param("   ", id="espacos"),
    pytest.param("..", id="ponto-ponto"),
    pytest.param("../../Windows", id="traversal-unix"),
    pytest.param("..\\..\\Windows", id="traversal-windows"),
    pytest.param("C:\\", id="raiz-do-disco"),
    pytest.param("C:\\Windows\\System32", id="system32"),
    pytest.param("\\\\servidor\\compartilhado", id="unc"),
    pytest.param("/etc/passwd", id="etc-passwd"),
    pytest.param("file:///C:/Windows", id="file-url"),
    pytest.param("\x00", id="nulo"),
    pytest.param("a\x00b", id="nulo-no-meio"),
    pytest.param("x" * 10_000_000, id="texto-de-10MB"),
]


class TestSuperficieDaApi:
    def test_os_metodos_publicos_sao_exatamente_os_da_tabela_53(self):
        publicos = {
            n
            for n in dir(Api)
            if not n.startswith("_") and callable(getattr(Api, n))
        }
        assert publicos == SUPERFICIE

    def test_nenhum_atributo_publico_alem_dos_metodos(self):
        """Um atributo publico tambem fica visivel para o JavaScript."""
        atributos = {
            n
            for n in dir(Api)
            if not n.startswith("_") and not callable(getattr(Api, n))
        }
        assert atributos == set()

    def test_todo_metodo_devolve_ok_ou_erro(self, api):
        """Nenhum metodo pode devolver None nem levantar: a interface trata
        sempre a mesma forma de resposta."""
        for nome in sorted(SUPERFICIE):
            metodo = getattr(api, nome)
            n_args = metodo.__wrapped__.__code__.co_argcount - 1 if hasattr(
                metodo, "__wrapped__"
            ) else 0
            try:
                r = metodo() if n_args == 0 else metodo(*([None] * n_args))
            except TypeError:
                # assinatura com mais argumentos obrigatorios: tenta com 3
                r = metodo(None, None, None)
            assert isinstance(r, dict), nome
            assert "ok" in r, nome
            if not r["ok"]:
                assert "codigo" in r["erro"] and "mensagem" in r["erro"], nome


class TestArgumentosHostis:
    """Varredura: nenhum argumento hostil pode derrubar nem escrever fora."""

    @staticmethod
    def _foto(raiz):
        return {p: p.stat().st_mtime_ns for p in raiz.rglob("*") if p.is_file()}

    @pytest.mark.parametrize("valor", HOSTIS)
    def test_metodos_de_um_argumento(self, api, valor):
        for nome in (
            "obter",
            "escolher_pasta",
            "escolher_arquivo",
            "ler_ficha",
            "ler_texto_ficha",
            "historico",
            "abrir_pasta",
            "abrir_link",
            "previa",
        ):
            r = getattr(api, nome)(valor)
            assert isinstance(r, dict) and "ok" in r, f"{nome}({valor!r})"

    @pytest.mark.parametrize("valor", HOSTIS)
    def test_configurar(self, api, ambiente, valor):
        antes = self._foto(ambiente.site), self._foto(ambiente.acervo)
        r = api.configurar(valor, valor)
        assert r["ok"] is False or valor == str(ambiente.site)
        assert (self._foto(ambiente.site), self._foto(ambiente.acervo)) == antes

    @pytest.mark.parametrize("valor", HOSTIS)
    def test_salvar_nao_escreve_nada_com_lixo(self, api, ambiente, valor):
        """O ponto central: um `salvar` com dados invalidos nao pode deixar
        nenhum rastro no acervo nem no site."""
        antes_site = self._foto(ambiente.site)
        antes_acervo = self._foto(ambiente.acervo)

        r = api.salvar(valor, valor, valor, valor)
        assert r["ok"] is False

        assert self._foto(ambiente.site) == antes_site
        assert self._foto(ambiente.acervo) == antes_acervo

    @pytest.mark.parametrize("valor", HOSTIS)
    def test_excluir_e_alternar(self, api, ambiente, valor):
        antes = self._foto(ambiente.acervo)
        assert api.excluir(valor, valor)["ok"] is False
        assert api.alternar_oculta(valor, valor)["ok"] is False
        assert api.restaurar(valor, valor)["ok"] is False
        assert self._foto(ambiente.acervo) == antes

    @pytest.mark.parametrize("valor", HOSTIS)
    def test_receber_arquivo(self, api, ambiente, valor):
        antes = self._foto(ambiente.acervo)
        r = api.receber_arquivo("pdf", valor, valor)
        assert r["ok"] is False
        assert self._foto(ambiente.acervo) == antes

    def test_nada_escapa_para_fora_das_raizes(self, api, ambiente, tmp_path):
        """Confere o sistema de arquivos INTEIRO do tmp_path antes e depois:
        um caminho malicioso que escrevesse fora do site e do acervo apareceria
        como arquivo novo em algum lugar."""
        alvos = ["..\\..\\invadido.txt", "C:\\invadido.txt", "/invadido.txt"]
        antes = {p for p in tmp_path.rglob("*")}

        for alvo in alvos:
            api.salvar({"titulo": alvo, "numero": alvo, "categoria": alvo}, alvo, alvo)
            api.configurar(alvo, alvo)
            api.receber_arquivo("capa", alvo, alvo)

        novos = {p for p in tmp_path.rglob("*")} - antes
        # o que aparecer tem de estar dentro do site, do acervo, do appdata ou
        # do localappdata -- nunca solto
        for p in novos:
            assert any(
                p.is_relative_to(r)
                for r in (ambiente.site, ambiente.acervo, ambiente.appdata, ambiente.local)
            ), p


class TestDestinosDeListaFechada:
    @pytest.mark.parametrize(
        "chave",
        [
            "https://evil.example",
            "http://127.0.0.1:1/x",
            "javascript:alert(1)",
            "file:///C:/Windows",
            "ufcinova/../evil",
            "",
            None,
            123,
        ],
    )
    def test_abrir_link_recusa_o_que_nao_esta_na_lista(self, api, chave, monkeypatch):
        """Com URL livre, um texto vindo de uma ficha poderia abrir qualquer
        coisa no navegador da pessoa."""
        abertos = []
        monkeypatch.setattr("webbrowser.open", abertos.append)
        r = api.abrir_link(chave)
        assert r["ok"] is False
        assert abertos == []

    def test_as_chaves_conhecidas_sao_https_da_ufc(self):
        for url in LINKS.values():
            assert url.startswith("https://")
            assert "ufc" in url

    @pytest.mark.parametrize(
        "tipo",
        ["C:\\", "C:\\Windows", "..", "../..", "quarentena", "backups", "", None, 123],
    )
    def test_abrir_pasta_recusa_o_que_nao_esta_na_lista(self, api, tipo, monkeypatch):
        chamados = []
        monkeypatch.setattr(Api, "_abre_no_sistema", staticmethod(chamados.append))
        r = api.abrir_pasta(tipo)
        assert r["ok"] is False
        assert chamados == []

    def test_so_tres_pastas_sao_abriveis(self):
        assert set(PASTAS_ABRIVEIS) == {"pacotes", "acervo", "site"}


class TestServidorLocal:
    def test_escuta_so_em_127001(self, api, monkeypatch):
        """Nenhuma outra maquina da rede pode alcancar a vitrine local (T2)."""
        monkeypatch.setattr("webbrowser.open", lambda *a: None)
        api.ver_site_local()
        try:
            host, _porta = api._servidor_local._httpd.server_address[:2]
            assert host == "127.0.0.1"
        finally:
            api._servidor_local.para()

    def test_recusa_metodos_de_escrita(self, api, monkeypatch):
        import urllib.error
        import urllib.request

        monkeypatch.setattr("webbrowser.open", lambda *a: None)
        url = api.ver_site_local()["dados"]["url"]
        try:
            req = urllib.request.Request(url, method="POST", data=b"x")
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(req, timeout=5)
            assert exc.value.code == 405
        finally:
            api._servidor_local.para()


class TestConfigurarCaminhos:
    def test_site_igual_ao_acervo(self, api, ambiente):
        r = api.configurar(str(ambiente.site), str(ambiente.site))
        assert r["ok"] is False
        assert "mesma pasta" in r["erro"]["mensagem"]

    def test_acervo_dentro_do_site(self, api, ambiente):
        dentro = ambiente.site / "acervo"
        (dentro / "1. BR 10 2020 000001 1").mkdir(parents=True)
        r = api.configurar(str(ambiente.site), str(dentro))
        assert r["ok"] is False
        assert "dentro da pasta do site" in r["erro"]["mensagem"]

    def test_pasta_sem_index_html(self, api, tmp_path, ambiente):
        outra = tmp_path / "qualquer"
        outra.mkdir()
        r = api.configurar(str(outra), str(ambiente.acervo))
        assert r["ok"] is False
        assert "index.html" in r["erro"]["mensagem"]
