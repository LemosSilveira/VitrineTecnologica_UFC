# -*- coding: utf-8 -*-
"""Historico em JSON Lines e backup antes de cada alteracao."""
from __future__ import annotations

import json
import os

import pytest

from painel import auditoria, backup, config


class TestAuditoria:
    def test_grava_uma_linha_por_acao(self, ambiente):
        for i in range(3):
            auditoria.registra("salvar", id=i)
        linhas = config.caminho_auditoria().read_text(encoding="utf-8").splitlines()
        assert len(linhas) == 3
        for ln in linhas:
            json.loads(ln)  # cada linha e um JSON valido por si

    def test_campos_obrigatorios(self, ambiente):
        r = auditoria.registra("salvar", id=61, numero="BR 10 2025 012345-6")
        assert r["acao"] == "salvar"
        assert r["resultado"] == "ok"
        assert r["usuario"]
        assert r["maquina"]
        assert r["ts"]
        assert r["id"] == 61

    def test_campos_none_nao_entram(self, ambiente):
        """Uma linha com dez chaves nulas nao ajuda ninguem a ler o historico."""
        r = auditoria.registra("rodar_build", id=None, numero=None)
        assert "id" not in r and "numero" not in r

    def test_so_acrescenta_nunca_reescreve(self, ambiente):
        auditoria.registra("primeira")
        antes = config.caminho_auditoria().read_text(encoding="utf-8")
        auditoria.registra("segunda")
        depois = config.caminho_auditoria().read_text(encoding="utf-8")
        assert depois.startswith(antes)

    def test_registro_gigante_e_encurtado(self, ambiente):
        """Um campo enorme nao pode inflar o log sem limite."""
        auditoria.registra("salvar", resumo="x" * 10_000)
        linha = config.caminho_auditoria().read_text(encoding="utf-8").strip()
        assert len(linha) < 5000
        assert "grande demais" in json.loads(linha)["resumo"]

    def test_falha_de_escrita_nao_derruba(self, ambiente, monkeypatch):
        """Falhar ao gravar o historico nao pode impedir a acao que ja
        aconteceu: um log perdido e um problema, uma patente perdida e maior."""

        def explode(*a, **kw):
            raise OSError("disco cheio")

        monkeypatch.setattr("pathlib.Path.open", explode)
        assert auditoria.registra("salvar")["acao"] == "salvar"

    def test_le_do_mais_recente_para_o_mais_antigo(self, ambiente):
        for i in range(5):
            auditoria.registra("acao", id=i)
        pagina = auditoria.le(1)
        assert [ln["id"] for ln in pagina["linhas"]] == [4, 3, 2, 1, 0]

    def test_paginacao(self, ambiente):
        for i in range(120):
            auditoria.registra("acao", id=i)
        p1 = auditoria.le(1, 50)
        p3 = auditoria.le(3, 50)
        assert p1["total"] == 120 and p1["paginas"] == 3
        assert len(p1["linhas"]) == 50 and len(p3["linhas"]) == 20
        assert p1["linhas"][0]["id"] == 119

    @pytest.mark.parametrize("pagina", [0, -1, 999, None, "x"])
    def test_pagina_invalida_nao_quebra(self, ambiente, pagina):
        auditoria.registra("acao")
        try:
            r = auditoria.le(pagina)
        except (TypeError, ValueError):
            pytest.fail("pagina invalida deveria ser tratada, nao levantar")
        assert 1 <= r["pagina"] <= max(1, r["paginas"])

    def test_linha_corrompida_nao_derruba_a_leitura(self, ambiente):
        """A tela Historico precisa mostrar que algo se perdeu, nao ficar
        vazia."""
        auditoria.registra("boa")
        with config.caminho_auditoria().open("a", encoding="utf-8") as f:
            f.write("{ isto nao e json\n")
        auditoria.registra("outra boa")

        linhas = auditoria.le(1)["linhas"]
        assert len(linhas) == 3
        assert any("ilegivel" in ln.get("acao", "") for ln in linhas)

    def test_sem_arquivo_devolve_vazio(self, ambiente):
        assert auditoria.le(1) == {"linhas": [], "pagina": 1, "paginas": 0, "total": 0}
        assert auditoria.conta() == 0


class TestBackup:
    def test_cria_copia_da_pasta_e_do_patentes_js(self, ambiente):
        pasta = ambiente.add_patente(1)
        b = backup.cria(
            "salvar",
            patente_id=1,
            pasta_patente=pasta,
            patentes_js=ambiente.site / "js" / "data" / "patentes.js",
        )
        assert (b.pasta / "acervo" / pasta.name).is_dir()
        assert (b.pasta / "site" / "js" / "data" / "patentes.js").is_file()
        assert list((b.pasta / "acervo" / pasta.name).glob("*.pdf"))

    def test_metadados(self, ambiente):
        b = backup.cria("ocultar", patente_id=7)
        assert b.acao == "ocultar"
        assert b.patente_id == 7
        assert b.usuario
        assert "patente 7" in b.descricao()

    def test_acao_sem_patente(self, ambiente):
        """Acrescentar uma area tecnologica nao toca em nenhuma patente."""
        b = backup.cria("nova-area")
        assert b.patente_id is None
        assert "vitrine" in b.descricao()

    def test_dois_backups_no_mesmo_segundo_nao_se_sobrescrevem(self, ambiente):
        a = backup.cria("salvar", patente_id=1)
        b = backup.cria("salvar", patente_id=1)
        assert a.id != b.id
        assert a.pasta.is_dir() and b.pasta.is_dir()

    def test_lista_do_mais_recente_para_o_mais_antigo(self, ambiente):
        ids = [backup.cria("salvar", patente_id=i).id for i in range(3)]
        assert [b.id for b in backup.lista()] == sorted(ids, reverse=True)

    def test_retencao_mantem_50(self, ambiente):
        for i in range(60):
            backup.cria("salvar", patente_id=1)
        assert len(backup.lista()) <= backup.MAX_BACKUPS

    def test_retencao_nunca_apaga_o_ultimo_de_cada_patente(self, ambiente):
        """Sem esta excecao, 55 edicoes numa patente apagariam o unico backup
        de todas as outras."""
        antigo = backup.cria("salvar", patente_id=999)
        for _ in range(60):
            backup.cria("salvar", patente_id=1)

        restantes = backup.lista()
        assert antigo.id in {b.id for b in restantes}
        assert 999 in {b.patente_id for b in restantes}

    def test_restaura_a_pasta_da_patente(self, ambiente):
        pasta = ambiente.add_patente(1)
        (pasta / "patente.json").write_text(
            '{"versao": 1, "campos": {}}', encoding="utf-8"
        )
        b = backup.cria("salvar", patente_id=1, pasta_patente=pasta)

        # estraga o estado atual
        (pasta / "patente.json").write_text("ESTRAGADO", encoding="utf-8")
        for f in pasta.glob("*.pdf"):
            f.unlink()

        backup.restaura(b.id, acervo=ambiente.acervo, site=ambiente.site)
        assert (pasta / "patente.json").read_text(encoding="utf-8").startswith("{")
        assert list(pasta.glob("*.pdf"))

    def test_restaura_o_patentes_js(self, ambiente):
        js = ambiente.site / "js" / "data" / "patentes.js"
        bom = js.read_text(encoding="utf-8")
        b = backup.cria("salvar", patentes_js=js)

        js.write_text("ESTRAGADO", encoding="utf-8")
        backup.restaura(b.id, acervo=ambiente.acervo, site=ambiente.site)
        assert js.read_text(encoding="utf-8") == bom

    @pytest.mark.parametrize(
        "id_backup",
        ["", "..", "../../Windows", "..\\..\\Windows", "a/b", "a\\b", "nao-existe"],
    )
    def test_id_de_backup_malicioso_e_recusado(self, ambiente, id_backup):
        """O id vem da interface: nao pode virar caminho sem conferir."""
        with pytest.raises(backup.ErroDeBackup):
            backup.restaura(id_backup, acervo=ambiente.acervo, site=ambiente.site)

    def test_falha_ao_criar_nao_deixa_pasta_pela_metade(self, ambiente, monkeypatch):
        chamadas = {"n": 0}
        real = backup.shutil.copytree

        def falha(*a, **kw):
            chamadas["n"] += 1
            raise OSError("disco cheio")

        monkeypatch.setattr(backup.shutil, "copytree", falha)
        pasta = ambiente.add_patente(1)
        with pytest.raises(backup.ErroDeBackup, match="copia de seguranca"):
            backup.cria("salvar", patente_id=1, pasta_patente=pasta)

        assert chamadas["n"] == 1
        assert backup.lista() == []
