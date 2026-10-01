# -*- coding: utf-8 -*-
"""Nomes gerados, pacote de publicacao, integridade e auditoria (PRD 12.2)."""
from __future__ import annotations

import base64
import json
import zipfile

import pytest

from conftest import escreve_imagem
from painel import auditoria, backup, config, publicacao
from painel.app import Trava, TravaOcupada
from painel.armazenamento import grava_patente
from vitrine_core.nomes import (
    CAMINHO_MAX,
    RESERVADOS_WINDOWS,
    TITULO_MAX_NO_NOME,
    ARQUIVO_RE,
    NomeInvalido,
    nome_arquivo_patente,
    nome_seguro,
)


# --------------------------------------------------------------------------
# Nomes gerados pelo painel (PRD 5.7)
# --------------------------------------------------------------------------

class TestNomesSeguros:
    @pytest.mark.parametrize("reservado", sorted(RESERVADOS_WINDOWS))
    def test_nomes_reservados_do_windows(self, reservado):
        """"CON.pdf" nao pode ser criado no Windows, e a mensagem de erro do
        sistema nao explica por que."""
        gerado = nome_seguro(reservado)
        assert gerado.upper() not in RESERVADOS_WINDOWS
        assert gerado.startswith(reservado)

    @pytest.mark.parametrize(
        "bruto",
        [
            "..\\..\\Windows\\System32",
            "../../etc/passwd",
            "C:\\Windows\\notepad.exe",
            "\\\\servidor\\compartilhado\\x",
            "a/b/c",
            "a:b",
            "arquivo*?<>|.txt",
            '"aspas"',
        ],
    )
    def test_separadores_de_caminho_nao_sobrevivem(self, bruto):
        gerado = nome_seguro(bruto)
        for proibido in "/\\:*?<>|\"":
            assert proibido not in gerado, f"{proibido!r} em {gerado!r}"
        assert ".." not in gerado

    def test_titulo_de_400_caracteres_e_cortado(self):
        gerado = nome_seguro("palavra " * 60)
        assert len(gerado) <= TITULO_MAX_NO_NOME

    @pytest.mark.parametrize("bruto", ["titulo.", "titulo ", "titulo. . ", ". titulo"])
    def test_ponto_e_espaco_nas_pontas_saem(self, bruto):
        """O Windows remove ponto e espaco do fim em silencio, e o nome gravado
        deixaria de bater com o esperado."""
        gerado = nome_seguro(bruto)
        assert not gerado.endswith((".", " "))
        assert not gerado.startswith((".", " "))

    def test_acento_e_preservado(self):
        assert nome_seguro("Camarão em Pó Natural") == "Camarão em Pó Natural"

    def test_nome_de_arquivo_bate_com_o_padrao_do_build(self):
        nome = nome_arquivo_patente(
            61, "Engenharias", "BR 10 2025 012345-6", "Um titulo qualquer", ".pdf"
        )
        assert nome == "61. Engenharias - BR 10 2025 012345 6 - Um titulo qualquer.pdf"
        m = ARQUIVO_RE.match(nome.removesuffix(".pdf"))
        assert m and m.group("cat").strip(" -") == "Engenharias"

    def test_titulo_hostil_ainda_gera_nome_valido(self):
        nome = nome_arquivo_patente(
            61,
            "Engenharias",
            "BR 10 2025 012345-6",
            "..\\..\\CON" + "x" * 400,
            ".pdf",
        )
        assert ARQUIVO_RE.match(nome.removesuffix(".pdf"))
        assert ".." not in nome and "\\" not in nome

    def test_caminho_longo_encurta_o_titulo(self, tmp_path):
        """O titulo completo fica no patente.json; no nome do arquivo ele cede
        para o caminho caber."""
        # profundidade calculada para sobrar espaco ao prefixo (`61.
        # Engenharias - BR 10 2025 012345 6 - `, 40 caracteres) e a extensao,
        # mas nao ao titulo inteiro
        folga = CAMINHO_MAX - len(str(tmp_path)) - 60
        fundo = tmp_path / ("p" * max(10, folga))
        nome = nome_arquivo_patente(
            61, "Engenharias", "BR 10 2025 012345-6", "titulo " * 20, ".pdf", fundo
        )
        assert len(str(fundo / nome)) <= CAMINHO_MAX
        # e o nome continua reconhecivel pelo build
        assert ARQUIVO_RE.match(nome.removesuffix(".pdf"))

    def test_caminho_impossivel_erra_com_mensagem_util(self, tmp_path):
        fundo = tmp_path / ("p" * 100) / ("q" * 100) / ("r" * 60)
        with pytest.raises(NomeInvalido, match="mais perto da raiz"):
            nome_arquivo_patente(
                61, "Engenharias", "BR 10 2025 012345-6", "titulo", ".pdf", fundo
            )

    def test_numero_invalido(self):
        with pytest.raises(NomeInvalido):
            nome_arquivo_patente(1, "Alimentos", "numero torto", "titulo", ".pdf")

    def test_grava_patente_com_titulo_hostil(self, ambiente, tmp_path):
        """Ponta a ponta: um titulo com `..` e nome reservado nao escapa da
        pasta da patente."""
        capa = escreve_imagem(tmp_path / "capa.png", 900)
        pasta = grava_patente(
            ambiente.acervo,
            patente_id=61,
            numero="BR 10 2025 012345-6",
            categoria="Alimentos",
            titulo="..\\..\\CON  aux  " + "x" * 300,
            campos={"titulo": "t", "categoria": "Alimentos"},
            capa=capa,
        )
        assert pasta.parent == ambiente.acervo
        for f in pasta.iterdir():
            assert len(str(f)) < CAMINHO_MAX + 40
            assert f.parent == pasta


# --------------------------------------------------------------------------
# Pacote de publicacao (PRD 5.9)
# --------------------------------------------------------------------------

class TestPacote:
    def _suja_o_site(self, site):
        """Enche o site com tudo que NAO pode ir para a web."""
        (site / "admin" / "painel").mkdir(parents=True)
        (site / "admin" / "painel" / "api.py").write_text("segredo", encoding="utf-8")
        (site / "tests" / "specs").mkdir(parents=True)
        (site / "tests" / "specs" / "home.spec.js").write_text("x", encoding="utf-8")
        (site / "scripts" / "vitrine_core").mkdir(parents=True, exist_ok=True)
        (site / "scripts" / "vitrine_core" / "build.py").write_text("x", encoding="utf-8")
        (site / "dados").mkdir(exist_ok=True)
        (site / "dados" / "categorias.json").write_text("{}", encoding="utf-8")
        (site / ".git").mkdir(exist_ok=True)
        (site / ".git" / "config").write_text("[core]", encoding="utf-8")
        (site / ".env").write_text("SENHA=123", encoding="utf-8")
        (site / "rascunho.py").write_text("print(1)", encoding="utf-8")
        (site / "19,47,52").write_text("listagem solta", encoding="utf-8")
        (site / "README.md").write_text("# doc", encoding="utf-8")
        (site / "notas.txt").write_text("interno", encoding="utf-8")
        # e um patente.json dentro da pasta de assets de uma patente
        for p in (site / "assets" / "patentes").iterdir():
            if p.is_dir():
                (p / "patente.json").write_text("{}", encoding="utf-8")
                (p / "original.pdf").write_text("original", encoding="utf-8")

    def test_o_zip_nao_leva_nada_interno(self, api):
        api.rodar_build()
        self._suja_o_site(api._ambiente.site)

        r = api.gerar_pacote()
        assert r["ok"] and r["dados"]["gerado"] is True

        with zipfile.ZipFile(config.pasta_pacotes() / r["dados"]["nome"]) as z:
            nomes = z.namelist()

        proibidos = [
            n
            for n in nomes
            if n.startswith(("admin/", "tests/", "scripts/", "dados/", ".git"))
            or n.endswith((".py", ".md", ".json", ".txt", ".env"))
            or n in ("19,47,52", ".env", "rascunho.py")
        ]
        assert proibidos == [], proibidos

    def test_o_zip_leva_tudo_que_o_patentes_js_referencia(self, api):
        api.rodar_build()
        r = api.gerar_pacote()
        with zipfile.ZipFile(config.pasta_pacotes() / r["dados"]["nome"]) as z:
            nomes = set(z.namelist())

        for p in publicacao.le_patentes_js(api._ambiente.site):
            for chave in ("capa400", "capa800", "ficha600", "ficha1620"):
                v = (p.get("imagens") or {}).get(chave)
                if v:
                    assert v in nomes, v
            if p.get("pdf"):
                assert p["pdf"] in nomes

    def test_os_arquivos_do_site_entram(self, api):
        api.rodar_build()
        r = api.gerar_pacote()
        with zipfile.ZipFile(config.pasta_pacotes() / r["dados"]["nome"]) as z:
            nomes = set(z.namelist())
        assert "index.html" in nomes
        assert "js/data/patentes.js" in nomes

    def test_a_pasta_de_uma_patente_oculta_nao_entra(self, api):
        """Com a patente oculta, nem o PDF nem a ficha dela podem estar no
        pacote: e o que impede o acesso por URL direta."""
        # duas patentes: ocultando uma, a vitrine nao fica vazia (o que
        # bloquearia o pacote por outro motivo)
        api._ambiente.add_patente(2)
        api.rodar_build()
        antes = {p.name for p in (api._ambiente.site / "assets" / "patentes").iterdir()}
        assert len(antes) == 2

        api.alternar_oculta(1, True)
        r = api.gerar_pacote()
        assert r["ok"] and r["dados"]["gerado"] is True, r

        with zipfile.ZipFile(config.pasta_pacotes() / r["dados"]["nome"]) as z:
            nomes = z.namelist()
        das_patentes = [n for n in nomes if n.startswith("assets/patentes/")]
        assert das_patentes  # a patente 2 continua la
        slug_oculto = next(s for s in antes if s.startswith("1-"))
        assert not any(slug_oculto in n for n in das_patentes)

    def test_pasta_orfa_bloqueia_o_pacote(self, api):
        """Uma pasta sobrando deixaria o PDF de uma patente oculta acessivel
        por URL direta -- justamente o que ocultar deveria impedir."""
        api.rodar_build()
        orfa = api._ambiente.site / "assets" / "patentes" / "99-patente-que-saiu"
        orfa.mkdir()
        (orfa / "ficha.pdf").write_text("x", encoding="utf-8")

        r = api.gerar_pacote()
        assert r["dados"]["gerado"] is False
        assert any(
            not c["ok"] and c["chave"] == "orfas" for c in r["dados"]["checagens"]
        )

    def test_o_sha256_e_do_arquivo_gerado(self, api):
        import hashlib

        api.rodar_build()
        r = api.gerar_pacote()
        caminho = config.pasta_pacotes() / r["dados"]["nome"]
        assert hashlib.sha256(caminho.read_bytes()).hexdigest() == r["dados"]["sha256"]

    def test_dois_pacotes_do_mesmo_estado_tem_o_mesmo_sha(self, api):
        """A data fixa nas entradas do zip torna o SHA-256 algo que a equipe
        pode comparar de verdade."""
        api.rodar_build()
        a = api.gerar_pacote()["dados"]["sha256"]
        b = api.gerar_pacote()["dados"]["sha256"]
        assert a == b

    def test_o_pacote_vai_para_fora_do_repositorio(self, api):
        api.rodar_build()
        r = api.gerar_pacote()
        caminho = config.pasta_pacotes() / r["dados"]["nome"]
        assert not caminho.is_relative_to(api._ambiente.site)


# --------------------------------------------------------------------------
# Integridade
# --------------------------------------------------------------------------

class TestIntegridade:
    def test_excecao_no_meio_do_salvar_nao_deixa_rastro(self, api, tmp_path, monkeypatch):
        """O `salvar` promete "nada foi alterado". Vale para o caminho de erro
        tambem."""
        ambiente = api._ambiente
        js = ambiente.site / "js" / "data" / "patentes.js"
        antes_js = js.read_text(encoding="utf-8")
        antes_acervo = sorted(p.name for p in ambiente.acervo.iterdir())

        capa = escreve_imagem(tmp_path / "capa.png", 900)
        t = api.receber_arquivo(
            "capa", "c.png", base64.b64encode(capa.read_bytes()).decode("ascii")
        )

        def explode(*a, **kw):
            raise RuntimeError("falha simulada no meio da gravacao")

        monkeypatch.setattr("painel.api.armazenamento.grava_patente", explode)
        r = api.salvar(
            {
                "numero": "BR 10 2025 055555 5",
                "categoria": "Alimentos",
                "titulo": "Patente que nao deveria ser gravada",
                "secoes": {"oQueE": "Uma descricao com mais de quarenta caracteres."},
            },
            t["dados"]["token"],
        )
        assert r["ok"] is False

        assert js.read_text(encoding="utf-8") == antes_js
        assert sorted(p.name for p in ambiente.acervo.iterdir()) == antes_acervo

    def test_o_backup_existe_mesmo_quando_o_salvar_falha(self, api, tmp_path, monkeypatch):
        """O backup e criado ANTES de escrever: se a gravacao falha, ele ja
        esta la -- e e o que permite voltar atras."""
        capa = escreve_imagem(tmp_path / "capa.png", 900)
        t = api.receber_arquivo(
            "capa", "c.png", base64.b64encode(capa.read_bytes()).decode("ascii")
        )

        def explode(*a, **kw):
            raise RuntimeError("falha simulada")

        monkeypatch.setattr("painel.api.armazenamento.grava_patente", explode)
        api.salvar(
            {
                "numero": "BR 10 2025 055555 5",
                "categoria": "Alimentos",
                "titulo": "Patente que nao deveria ser gravada",
                "secoes": {"oQueE": "Uma descricao com mais de quarenta caracteres."},
            },
            t["dados"]["token"],
        )
        assert any(b.acao == "salvar" for b in backup.lista())

    def test_recorte_invalido_nao_deixa_pasta_no_acervo(self, api, tmp_path):
        """Uma pasta vazia faria o build acusar "sem imagem de capa" e travar a
        vitrine inteira ate alguem apaga-la a mao."""
        retrato = escreve_imagem(tmp_path / "r.png", 600, 900)
        t = api.receber_arquivo(
            "capa", "r.png", base64.b64encode(retrato.read_bytes()).decode("ascii")
        )
        antes = sorted(p.name for p in api._ambiente.acervo.iterdir())

        r = api.salvar(
            {
                "numero": "BR 10 2025 044444 4",
                "categoria": "Alimentos",
                "titulo": "Patente com recorte invalido no teste",
                "secoes": {"oQueE": "Uma descricao com mais de quarenta caracteres."},
                "recorte": {"x": 0, "y": 0, "lado": 5000},
            },
            t["dados"]["token"],
        )
        assert r["ok"] is False
        assert sorted(p.name for p in api._ambiente.acervo.iterdir()) == antes

    def test_segunda_instancia_e_recusada(self, ambiente):
        """Dois paineis abertos gravariam no mesmo patente.json e rodariam o
        build ao mesmo tempo."""
        with Trava() as primeira:
            assert primeira.caminho.is_file()
            with pytest.raises(TravaOcupada, match="já está aberto"):
                Trava().adquire()

    def test_a_trava_e_liberada_ao_fechar(self, ambiente):
        with Trava():
            pass
        segunda = Trava()
        segunda.adquire()  # nao levanta
        segunda.libera()

    def test_a_trava_nao_depende_de_o_arquivo_existir(self, ambiente):
        """Um painel encerrado pelo Gerenciador de Tarefas deixa o arquivo
        para tras; checar por existencia impediria o proximo de abrir para
        sempre."""
        caminho = config.caminho_trava()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text("9999\n", encoding="utf-8")
        t = Trava()
        t.adquire()
        t.libera()

    def test_build_com_erro_nao_reescreve_o_patentes_js(self, api):
        """Ponta a ponta pela Api: a vitrine anterior fica de pe."""
        api.rodar_build()
        js = api._ambiente.site / "js" / "data" / "patentes.js"
        bom = js.read_text(encoding="utf-8")

        pasta = next(api._ambiente.acervo.glob("1. *"))
        (pasta / "patente.json").write_text(
            '{"versao": 1, "campos": {"titulo": "curto"}}', encoding="utf-8"
        )
        r = api.rodar_build()
        assert r["dados"]["erros"]
        assert r["dados"]["vitrineAtualizada"] is False
        assert js.read_text(encoding="utf-8") == bom


# --------------------------------------------------------------------------
# Auditoria
# --------------------------------------------------------------------------

class TestAuditoriaDasAcoes:
    def _linhas(self):
        texto = config.caminho_auditoria().read_text(encoding="utf-8")
        return [json.loads(ln) for ln in texto.splitlines() if ln.strip()]

    def test_cada_acao_escreve_exatamente_uma_linha(self, api, tmp_path):
        capa = escreve_imagem(tmp_path / "capa.png", 900)
        t = api.receber_arquivo(
            "capa", "c.png", base64.b64encode(capa.read_bytes()).decode("ascii")
        )
        api.salvar(
            {
                "numero": "BR 10 2025 033333 3",
                "categoria": "Alimentos",
                "titulo": "Patente para conferir o historico",
                "secoes": {"oQueE": "Uma descricao com mais de quarenta caracteres."},
            },
            t["dados"]["token"],
        )
        api.alternar_oculta(1, True)
        api.alternar_oculta(1, False)
        api.rodar_build()
        api.excluir(1, "BR 10 2025 000001-1")

        acoes = [ln["acao"] for ln in self._linhas()]
        assert acoes == ["criar", "ocultar", "mostrar", "rodar_build", "excluir"]

    def test_toda_linha_tem_usuario_maquina_e_resultado(self, api):
        api.rodar_build()
        for ln in self._linhas():
            assert ln["usuario"] and ln["maquina"] and ln["resultado"]
            assert ln["ts"]

    def test_o_historico_guarda_o_sha_do_que_entrou(self, api, tmp_path):
        capa = escreve_imagem(tmp_path / "capa.png", 900)
        t = api.receber_arquivo(
            "capa", "c.png", base64.b64encode(capa.read_bytes()).decode("ascii")
        )
        api.salvar(
            {
                "numero": "BR 10 2025 022222 2",
                "categoria": "Alimentos",
                "titulo": "Patente para conferir o sha do historico",
                "secoes": {"oQueE": "Uma descricao com mais de quarenta caracteres."},
            },
            t["dados"]["token"],
        )
        import hashlib

        esperado = hashlib.sha256(capa.read_bytes()).hexdigest()
        assert self._linhas()[-1]["sha256"]["capa"] == esperado

    def test_o_historico_nao_guarda_o_conteudo_dos_campos(self, api, tmp_path):
        """O log diz QUE o titulo mudou, nao para o que: para isso existe o
        backup."""
        capa = escreve_imagem(tmp_path / "capa.png", 900)
        t = api.receber_arquivo(
            "capa", "c.png", base64.b64encode(capa.read_bytes()).decode("ascii")
        )
        titulo = "Titulo muito especifico que nao deveria estar no log"
        api.salvar(
            {
                "numero": "BR 10 2025 011111 1",
                "categoria": "Alimentos",
                "titulo": titulo,
                "secoes": {"oQueE": "Uma descricao com mais de quarenta caracteres."},
            },
            t["dados"]["token"],
        )
        texto = config.caminho_auditoria().read_text(encoding="utf-8")
        assert titulo not in texto
        # mas registra QUAIS campos mudaram
        assert "titulo" in self._linhas()[-1]["resumo"]

    def test_acao_que_falha_e_registrada_como_erro(self, api):
        pasta = next(api._ambiente.acervo.glob("1. *"))
        (pasta / "patente.json").write_text(
            '{"versao": 1, "campos": {"titulo": "curto"}}', encoding="utf-8"
        )
        api.rodar_build()
        assert self._linhas()[-1]["resultado"] == "erro"
