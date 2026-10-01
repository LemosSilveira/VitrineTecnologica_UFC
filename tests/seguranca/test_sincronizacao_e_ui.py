# -*- coding: utf-8 -*-
"""A cópia do site em `admin/ui/site/` e a casca da interface.

Dois riscos que estes testes cobrem:

1. A cópia divergir do site. Se isso acontecer, a prévia do painel deixa de
   mostrar o que a vitrine mostra, e o erro só apareceria quando alguém
   comparasse as duas telas a olho (PRD 12.2).
2. A interface ganhar `<script>` ou `<style>` inline. A CSP da janela não
   concede `'unsafe-inline'`, então isso quebraria a tela -- e, se alguém
   "consertasse" afrouxando a política, ela deixaria de proteger.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
UI = RAIZ / "admin" / "ui"
SINCRONIZA = RAIZ / "admin" / "sincroniza_site.py"


def _html_sem_comentarios(caminho: Path) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", caminho.read_text(encoding="utf-8"))


class TestSincronizacao:
    def test_a_copia_esta_igual_ao_site(self):
        """Se falhar: rode `python admin/sincroniza_site.py`."""
        r = subprocess.run(
            [sys.executable, str(SINCRONIZA), "--conferir"],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr

    def test_copia_o_render_js(self):
        """É o arquivo que faz a prévia do painel ser idêntica ao site."""
        assert (UI / "site" / "js" / "render.js").is_file()

    def test_copia_as_fontes(self):
        fontes = list((UI / "site" / "assets" / "fonts").glob("*.woff2"))
        assert len(fontes) >= 6

    def test_nao_copia_o_que_o_painel_nao_usa(self):
        """`admin/ui/site/` não é um espelho do repositório: o servidor da
        janela serve essa pasta, e tudo que estiver lá fica alcançável."""
        copiados = {p.relative_to(UI / "site").as_posix() for p in (UI / "site").rglob("*") if p.is_file()}
        assert not any(c.startswith("js/data/") for c in copiados)
        assert not any(c.startswith("assets/patentes/") for c in copiados)
        assert "index.html" not in copiados


class TestCascaDaInterface:
    @pytest.fixture(scope="class")
    @staticmethod
    def html():
        return _html_sem_comentarios(UI / "index.html")

    def test_a_csp_nao_concede_inline(self, html):
        m = re.search(
            r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"', html
        )
        assert m, "nenhuma CSP na <meta> do painel"
        csp = m.group(1)
        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp
        for diretiva in (
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "object-src 'none'",
            "base-uri 'none'",
            "form-action 'none'",
        ):
            assert diretiva in csp, diretiva

    def test_a_janela_nao_faz_requisicao_de_rede(self, html):
        """`connect-src 'none'`: a interface fala com o Python pela ponte do
        pywebview, não por HTTP. Qualquer fetch é bug ou injeção."""
        m = re.search(r'content="([^"]*connect-src[^"]*)"', html)
        assert m and "connect-src 'none'" in m.group(1)

    def test_nenhum_script_ou_estilo_inline(self, html):
        assert [m[0] for m in re.finditer(r"<script(?![^>]*\ssrc=)[^>]*>", html)] == []
        assert [m[0] for m in re.finditer(r"<style[\s>]", html)] == []
        assert [m[0] for m in re.finditer(r"\sstyle\s*=\s*\"", html)] == []

    def test_nenhum_link_externo(self, html):
        """A janela nunca navega para fora: links externos passam por
        `api.abrir_link(chave)`, que só conhece destinos de lista fechada."""
        externos = re.findall(r'(?:href|src)="(https?://[^"]+)"', html)
        assert externos == []

    def test_carrega_o_css_e_o_js_do_site(self, html):
        for arquivo in (
            "site/css/tokens.css",
            "site/css/base.css",
            "site/css/components.css",
            "site/js/ui.js",
            "site/js/render.js",
        ):
            assert arquivo in html, arquivo

    def test_so_um_ponto_toca_a_ponte_do_pywebview(self):
        """Espalhar `window.pywebview` pelas telas garantiria que uma delas
        esquecesse de tratar erro ou de esperar a ponte ficar pronta.

        Procura o USO (`window.pywebview`), não a palavra: os comentários de
        outros arquivos explicam a ponte, e devem continuar podendo.
        """
        arquivos = [p for p in UI.rglob("*.js") if "site" not in p.parts]
        usam = sorted(
            p.relative_to(UI).as_posix()
            for p in arquivos
            if re.search(r"window\s*\.\s*pywebview", p.read_text(encoding="utf-8"))
        )
        assert usam == ["api-cliente.js"], usam

    def test_o_cliente_cobre_a_tabela_53(self):
        """A lista do JS tem de bater com a superfície do Python."""
        from painel.api import Api

        js = (UI / "api-cliente.js").read_text(encoding="utf-8")
        bloco = re.search(r"var METODOS = \[(.*?)\];", js, re.S).group(1)
        no_js = set(re.findall(r'"([a-z_]+)"', bloco))

        no_python = {
            n for n in dir(Api) if not n.startswith("_") and callable(getattr(Api, n))
        }
        assert no_js == no_python


class TestFolhaDeEstiloDoPainel:
    @pytest.fixture(scope="class")
    @staticmethod
    def css():
        return (UI / "painel.css").read_text(encoding="utf-8")

    def test_a_escala_de_erro_esta_definida(self, css):
        for token in (
            "--c-danger:",
            "--c-danger-700:",
            "--c-danger-800:",
            "--c-danger-100:",
            "--c-danger-50:",
        ):
            assert token in css, token

    def test_usa_a_cor_aprovada(self, css):
        assert "#ed455a" in css.lower()

    def test_o_tom_base_nao_e_usado_como_cor_de_texto(self, css):
        """#ED455A rende 3,41:1 no fundo: passa no mínimo de 3:1 de componente
        de interface, reprova nos 4,5:1 de texto. Texto usa o tom 700.

        Regras de ícone (`svg` no seletor) são a exceção legítima: um ícone É
        um componente gráfico, e 3:1 é o limite certo para ele.
        """
        culpados = []
        for bloco in css.split("}"):
            if "{" not in bloco:
                continue
            seletor, _, corpo = bloco.rpartition("{")
            seletor = seletor.split("*/")[-1].strip()
            if "svg" in seletor:
                continue
            if re.search(r"(^|[\s;])color:\s*var\(--c-danger\)", corpo):
                culpados.append(seletor)
        assert culpados == [], culpados

    def test_nao_redefine_tokens_do_site(self, css):
        """O painel acrescenta a escala de erro e as medidas dele; redefinir
        uma cor da marca faria a prévia mentir sobre a vitrine."""
        definidos = set(re.findall(r"^\s*(--[a-z0-9-]+):", css, re.M))
        proibidos = {
            d
            for d in definidos
            if d.startswith(("--c-brand", "--c-text", "--c-bg", "--c-surface", "--ff-", "--s-"))
        }
        assert proibidos == set()
