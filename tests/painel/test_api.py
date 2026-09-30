# -*- coding: utf-8 -*-
"""A Api de ponta a ponta: os fluxos da secao 9 do PRD."""
from __future__ import annotations

import base64
import json

import pytest

from conftest import escreve_imagem, escreve_pdf
from painel import config
from painel.api import Api


@pytest.fixture
def pdf(tmp_path):
    return escreve_pdf(tmp_path / "ficha.pdf", "Camarao em Po Natural para Testes")


@pytest.fixture
def capa(tmp_path):
    return escreve_imagem(tmp_path / "capa.png", 900)


def token(api, tipo, caminho):
    r = api.receber_arquivo(
        tipo, caminho.name, base64.b64encode(caminho.read_bytes()).decode("ascii")
    )
    assert r["ok"], r
    return r["dados"]["token"]


def rascunho(**troca):
    base = {
        "numero": "BR 10 2025 099999 9",
        "categoria": "Alimentos",
        "titulo": "Tecnologia cadastrada pelo painel nos testes",
        "secoes": {
            "oQueE": "Uma descricao com mais de quarenta caracteres para o teste."
        },
    }
    base.update(troca)
    return base


class TestFormatoDaResposta:
    def test_sucesso(self, api):
        r = api.estado()
        assert set(r) == {"ok", "dados"}
        assert r["ok"] is True

    def test_erro_tem_codigo_e_mensagem(self, api):
        r = api.abrir_link("https://evil.example")
        assert r["ok"] is False
        assert set(r["erro"]) >= {"codigo", "mensagem"}

    def test_erro_nao_traz_stack_trace(self, api, monkeypatch):
        """Nenhum detalhe tecnico volta para a janela: o stack trace vai para o
        log, que fica fora dela."""

        def explode(*a, **kw):
            raise RuntimeError("caminho interno C:\\Users\\segredo\\x.py linha 42")

        monkeypatch.setattr(api, "_lista_patentes", explode)
        r = api.listar()
        assert r["ok"] is False
        texto = json.dumps(r, ensure_ascii=False)
        assert "segredo" not in texto
        assert "Traceback" not in texto
        assert "RuntimeError" not in texto
        assert r["erro"]["codigo"].startswith("E-")


class TestEstadoEConfiguracao:
    def test_estado_sem_configuracao(self, ambiente, dialogos_falsos):
        api = Api(dialogos=dialogos_falsos)
        dados = api.estado()["dados"]
        assert dados["configurado"] is False
        assert dados["naVitrine"] == 0

    def test_estado_configurado(self, api):
        dados = api.estado()["dados"]
        assert dados["configurado"] is True
        assert dados["naVitrine"] == 1
        assert dados["areas"] == 10
        assert dados["usuario"]

    def test_configurar(self, ambiente, dialogos_falsos):
        ambiente.add_patente(1)
        api = Api(dialogos=dialogos_falsos)
        r = api.configurar(str(ambiente.site), str(ambiente.acervo))
        assert r["ok"] and r["dados"]["configurado"] is True
        assert config.carrega().pastaSite == str(ambiente.site)

    def test_configurar_com_pasta_errada(self, ambiente, dialogos_falsos, tmp_path):
        api = Api(dialogos=dialogos_falsos)
        r = api.configurar(str(tmp_path), str(ambiente.acervo))
        assert r["ok"] is False
        assert "index.html" in r["erro"]["mensagem"]

    def test_escolher_pasta_usa_o_seletor_nativo(self, api, dialogos_falsos, ambiente):
        dialogos_falsos.pasta = str(ambiente.site)
        r = api.escolher_pasta("site")
        assert r["dados"]["caminho"] == str(ambiente.site)
        assert dialogos_falsos.chamadas[-1][0] == "pasta"

    def test_escolher_pasta_cancelado(self, api, dialogos_falsos):
        dialogos_falsos.pasta = None
        assert api.escolher_pasta("acervo")["dados"]["cancelado"] is True

    def test_escolher_pasta_valida_na_hora(self, api, dialogos_falsos, tmp_path):
        """A pessoa recebe o retorno no passo, nao ao clicar em salvar."""
        dialogos_falsos.pasta = str(tmp_path)
        assert api.escolher_pasta("site")["ok"] is False

    @pytest.mark.parametrize("tipo", ["", "outro", None, 123])
    def test_escolher_pasta_tipo_invalido(self, api, tipo):
        assert api.escolher_pasta(tipo)["ok"] is False


class TestArquivos:
    def test_receber_pdf(self, api, pdf):
        r = api.receber_arquivo(
            "pdf", "ficha.pdf", base64.b64encode(pdf.read_bytes()).decode("ascii")
        )
        assert r["ok"]
        assert r["dados"]["tipo"] == "pdf"
        assert r["dados"]["token"]

    def test_o_nome_original_volta_so_para_exibir(self, api, pdf):
        r = api.receber_arquivo(
            "pdf",
            "..\\..\\Windows\\CON.pdf",
            base64.b64encode(pdf.read_bytes()).decode("ascii"),
        )
        assert r["ok"]
        # volta para a tela, mas nao virou caminho em disco
        assert "nomeOriginal" in r["dados"]

    def test_receber_capa_informa_se_precisa_recorte(self, api, tmp_path):
        retrato = escreve_imagem(tmp_path / "retrato.png", 600, 900)
        r = api.receber_arquivo(
            "capa", "r.png", base64.b64encode(retrato.read_bytes()).decode("ascii")
        )
        assert r["dados"]["precisaRecorte"] is True

    def test_escolher_arquivo(self, api, dialogos_falsos, pdf):
        dialogos_falsos.arquivo = str(pdf)
        r = api.escolher_arquivo("pdf")
        assert r["ok"] and r["dados"]["token"]

    def test_escolher_arquivo_cancelado(self, api, dialogos_falsos):
        dialogos_falsos.arquivo = None
        assert api.escolher_arquivo("capa")["dados"]["cancelado"] is True

    def test_ler_ficha(self, api, pdf):
        r = api.ler_ficha(token(api, "pdf", pdf))
        assert r["ok"]
        dados = r["dados"]
        assert dados["titulo"]["valor"] == "Camarao em Po Natural para Testes"
        assert dados["titulo"]["origem"] == "pdf"
        assert dados["secoes"]["oQueE"]["valor"]

    def test_ler_ficha_com_token_de_imagem(self, api, capa):
        r = api.ler_ficha(token(api, "capa", capa))
        assert r["ok"] is False

    def test_ler_texto_ficha(self, api):
        texto = "O que é?\nAlgo com mais de quarenta caracteres nesta descricao.\n"
        r = api.ler_texto_ficha(texto)
        assert r["ok"]
        assert r["dados"]["secoes"]["oQueE"]["valor"]

    def test_ler_texto_gigante(self, api):
        r = api.ler_texto_ficha("x" * 25_000)
        assert r["ok"] is False
        assert "limite" in r["erro"]["mensagem"]

    @pytest.mark.parametrize("bruto", [None, 123, [], {}])
    def test_ler_texto_de_outro_tipo(self, api, bruto):
        assert api.ler_texto_ficha(bruto)["ok"] is False


class TestPrevia:
    def test_monta_o_objeto_no_formato_do_site(self, api, pdf, capa):
        r = api.previa(rascunho(), token(api, "capa", capa), token(api, "pdf", pdf))
        assert r["ok"]
        p = r["dados"]["patente"]
        # as mesmas chaves que window.PATENTES[i] tem
        assert set(p) >= {
            "id", "slug", "numero", "ano", "tipo", "categoria", "titulo",
            "resumo", "secoes", "trl", "imagens", "pdf",
        }
        assert p["imagens"]["capa400"].startswith("data:image/webp;base64,")
        assert p["imagens"]["ficha600"].startswith("data:image/webp;base64,")

    def test_resumo_e_calculado_como_no_build(self, api, capa):
        longo = "Palavra " * 60
        r = api.previa(rascunho(secoes={"oQueE": longo}), token(api, "capa", capa))
        resumo = r["dados"]["patente"]["resumo"]
        assert resumo.endswith("…")
        assert len(resumo) <= 161

    def test_sem_pdf_as_fichas_ficam_nulas(self, api, capa):
        r = api.previa(rascunho(), token(api, "capa", capa))
        p = r["dados"]["patente"]
        assert p["imagens"]["ficha600"] is None
        assert p["pdf"] is None

    def test_devolve_os_erros_sem_recusar(self, api, capa):
        """A previa mostra o card mesmo com campo invalido: e assim que a
        pessoa ve o efeito enquanto digita."""
        r = api.previa(rascunho(titulo="curto"), token(api, "capa", capa))
        assert r["ok"] is True
        assert r["dados"]["valido"] is False
        assert "titulo" in r["dados"]["erros"]

    def test_trl_recebe_o_texto_calculado(self, api, capa):
        r = api.previa(
            rascunho(trl={"min": 5, "max": 6, "estimado": True}),
            token(api, "capa", capa),
        )
        assert r["dados"]["patente"]["trl"]["texto"].startswith("TRL 5")
        assert "estimado" in r["dados"]["patente"]["trl"]["texto"]

    def test_nada_e_escrito_no_site(self, api, pdf, capa):
        antes = sorted(p.name for p in (api._ambiente.site / "assets").rglob("*")) if (
            api._ambiente.site / "assets"
        ).is_dir() else []
        api.previa(rascunho(), token(api, "capa", capa), token(api, "pdf", pdf))
        depois = sorted(p.name for p in (api._ambiente.site / "assets").rglob("*")) if (
            api._ambiente.site / "assets"
        ).is_dir() else []
        assert antes == depois


class TestSalvar:
    def test_cria_patente_nova(self, api, pdf, capa):
        r = api.salvar(rascunho(), token(api, "capa", capa), token(api, "pdf", pdf))
        assert r["ok"], r
        assert r["dados"]["novo"] is True
        assert r["dados"]["id"] == 2  # a 1 ja existe na fixture
        assert r["dados"]["build"]["erros"] == []

    def test_a_patente_entra_no_patentes_js(self, api, pdf, capa):
        api.salvar(rascunho(), token(api, "capa", capa), token(api, "pdf", pdf))
        js = (api._ambiente.site / "js" / "data" / "patentes.js").read_text(
            encoding="utf-8"
        )
        assert "Tecnologia cadastrada pelo painel" in js

    def test_grava_todos_os_campos_no_patente_json(self, api, pdf, capa):
        """Gravar so o que mudou faria uma releitura futura do PDF sobrescrever
        a correcao humana (PRD 9.1, passo 7)."""
        api.salvar(rascunho(), token(api, "capa", capa), token(api, "pdf", pdf))
        pasta = next(api._ambiente.acervo.glob("2. *"))
        campos = json.loads((pasta / "patente.json").read_text(encoding="utf-8"))["campos"]
        assert campos["titulo"] and campos["categoria"] and campos["secoes"]["oQueE"]

    def test_recusa_com_campo_invalido_e_devolve_por_campo(self, api, capa):
        r = api.salvar(rascunho(titulo="curto"), token(api, "capa", capa))
        assert r["ok"] is False
        assert r["erro"]["codigo"] == "E-VALID"
        assert "titulo" in r["erro"]["campos"]

    def test_sem_capa_recusa_patente_nova(self, api, pdf):
        r = api.salvar(rascunho(), None, token(api, "pdf", pdf))
        assert r["ok"] is False
        assert "capa" in r["erro"]["campos"]

    def test_cadastro_manual_sem_pdf(self, api, capa):
        r = api.salvar(rascunho(), token(api, "capa", capa))
        assert r["ok"], r
        assert r["dados"]["build"]["erros"] == []
        js = (api._ambiente.site / "js" / "data" / "patentes.js").read_text(
            encoding="utf-8"
        )
        assert "pdf: null" in js

    def test_cria_backup_antes(self, api, pdf, capa):
        from painel import backup

        api.salvar(rascunho(), token(api, "capa", capa), token(api, "pdf", pdf))
        assert any(b.acao == "salvar" for b in backup.lista())

    def test_registra_no_historico(self, api, pdf, capa):
        from painel import auditoria

        api.salvar(rascunho(), token(api, "capa", capa), token(api, "pdf", pdf))
        linhas = auditoria.le(1)["linhas"]
        assert linhas[0]["acao"] == "criar"
        assert linhas[0]["numero"] == "BR 10 2025 099999-9"
        assert "capa" in linhas[0]["sha256"] and "pdf" in linhas[0]["sha256"]

    def test_editar_patente_existente(self, api, capa):
        r = api.salvar(
            rascunho(titulo="Titulo corrigido pela equipe agora", id=1),
            token(api, "capa", capa),
            None,
            1,
        )
        assert r["ok"], r
        assert r["dados"]["novo"] is False
        pasta = next(api._ambiente.acervo.glob("1. *"))
        campos = json.loads((pasta / "patente.json").read_text(encoding="utf-8"))["campos"]
        assert campos["titulo"] == "Titulo corrigido pela equipe agora"

    def test_numero_duplicado_e_recusado(self, api, capa):
        r = api.salvar(rascunho(numero="BR 10 2025 000001 1"), token(api, "capa", capa))
        assert r["ok"] is False
        assert "numero" in r["erro"]["campos"]

    def test_o_token_e_descartado_depois_de_salvar(self, api, pdf, capa):
        t = token(api, "capa", capa)
        api.salvar(rascunho(), t)
        assert api.ler_ficha(t)["ok"] is False


class TestOcultarExcluir:
    def test_ocultar_tira_da_vitrine(self, api):
        r = api.alternar_oculta(1, True)
        assert r["ok"], r
        assert r["dados"]["build"]["ocultas"] == [1]
        js = (api._ambiente.site / "js" / "data" / "patentes.js").read_text(
            encoding="utf-8"
        )
        assert "Tecnologia numero 1" not in js

    def test_mostrar_devolve(self, api):
        api.alternar_oculta(1, True)
        r = api.alternar_oculta(1, False)
        assert r["dados"]["build"]["ocultas"] == []

    @pytest.mark.parametrize("valor", ["true", 1, None, "sim"])
    def test_oculta_precisa_ser_booleano(self, api, valor):
        assert api.alternar_oculta(1, valor)["ok"] is False

    def test_excluir_exige_o_numero(self, api):
        r = api.excluir(1, "qualquer coisa")
        assert r["ok"] is False
        assert r["erro"]["codigo"] == "E-CONFIRMA"
        assert "BR 10 2025 000001-1" in r["erro"]["mensagem"]

    def test_excluir_com_o_numero_certo(self, api):
        r = api.excluir(1, "BR 10 2025 000001-1")
        assert r["ok"], r
        assert (api._ambiente.acervo / "_lixeira").is_dir()

    def test_excluir_aceita_o_numero_sem_hifen(self, api):
        assert api.excluir(1, "BR 10 2025 000001 1")["ok"] is True

    def test_patente_inexistente(self, api):
        assert api.excluir(99, "BR 10 2025 000099-1")["ok"] is False
        assert api.alternar_oculta(99, True)["ok"] is False


class TestListarObter:
    def test_listar(self, api):
        r = api.listar()
        assert r["ok"]
        p = r["dados"]["patentes"][0]
        assert p["id"] == 1
        assert p["numero"] == "BR 10 2025 000001-1"
        assert p["temPdf"] and p["temCapa"]
        assert p["oculta"] is False

    def test_listar_mostra_json_invalido_sem_derrubar(self, api):
        pasta = next(api._ambiente.acervo.glob("1. *"))
        (pasta / "patente.json").write_text("{ quebrado", encoding="utf-8")
        p = api.listar()["dados"]["patentes"][0]
        assert p["problema"]

    def test_obter_preenche_a_partir_da_ficha(self, api):
        """O formulario abre preenchido mesmo numa patente que ninguem editou
        ainda."""
        r = api.obter(1)
        assert r["ok"]
        assert r["dados"]["campos"]["titulo"]
        assert r["dados"]["campos"]["secoes"]["oQueE"]
        assert r["dados"]["numero"] == "BR 10 2025 000001-1"
        assert "Alimentos" in r["dados"]["areas"]

    def test_obter_inexistente(self, api):
        assert api.obter(99)["ok"] is False

    @pytest.mark.parametrize("bruto", [None, "", "x", -1, 0, 10**9, True, [], {}])
    def test_id_invalido(self, api, bruto):
        assert api.obter(bruto)["ok"] is False


class TestHistoricoRestaurar:
    def test_historico_traz_linhas_e_backups(self, api, capa):
        api.salvar(rascunho(), token(api, "capa", capa))
        r = api.historico(1)
        assert r["ok"]
        assert r["dados"]["total"] >= 1
        assert r["dados"]["backups"]

    def test_restaurar_exige_confirmacao(self, api, capa):
        api.salvar(rascunho(), token(api, "capa", capa))
        id_backup = api.historico(1)["dados"]["backups"][0]["id"]
        r = api.restaurar(id_backup, "sim")
        assert r["ok"] is False
        assert r["erro"]["codigo"] == "E-CONFIRMA"

    def test_restaurar_faz_backup_do_estado_atual_antes(self, api, capa):
        """Sem isso, restaurar por engano nao teria volta."""
        from painel import backup

        api.salvar(rascunho(), token(api, "capa", capa))
        id_backup = api.historico(1)["dados"]["backups"][0]["id"]
        api.restaurar(id_backup, "RESTAURAR")
        assert any(b.acao == "antes-de-restaurar" for b in backup.lista())

    def test_restaurar_backup_inexistente(self, api):
        assert api.restaurar("2020-01-01_000000_salvar_1", "RESTAURAR")["ok"] is False


class TestBuildEPacote:
    def test_rodar_build(self, api):
        r = api.rodar_build()
        assert r["ok"]
        assert r["dados"]["patentes"] == 1
        assert r["dados"]["erros"] == []

    def test_gerar_pacote(self, api):
        import zipfile

        api.rodar_build()
        r = api.gerar_pacote()
        assert r["ok"], r
        assert r["dados"]["gerado"] is True
        assert len(r["dados"]["sha256"]) == 64

        pacote = config.pasta_pacotes() / r["dados"]["nome"]
        assert pacote.is_file()
        with zipfile.ZipFile(pacote) as z:
            nomes = z.namelist()
        assert "index.html" in nomes
        assert any(n.startswith("assets/patentes/") for n in nomes)

    def test_pacote_bloqueado_por_pendencia(self, api):
        api.rodar_build()
        # apaga um arquivo que o patentes.js referencia
        for f in (api._ambiente.site / "assets" / "patentes").rglob("capa-400.webp"):
            f.unlink()
        r = api.gerar_pacote()
        assert r["dados"]["gerado"] is False
        assert any(not c["ok"] for c in r["dados"]["checagens"])


class TestAtalhos:
    def test_abrir_link_conhecido(self, api, monkeypatch):
        abertos = []
        monkeypatch.setattr("webbrowser.open", abertos.append)
        assert api.abrir_link("ufcinova")["ok"] is True
        assert abertos == ["https://ufcinova.sitios.sti.ufc.br"]

    def test_ver_site_local_sobe_servidor_em_127001(self, api, monkeypatch):
        monkeypatch.setattr("webbrowser.open", lambda *a: None)
        r = api.ver_site_local()
        assert r["ok"]
        assert r["dados"]["url"].startswith("http://127.0.0.1:")
        api._servidor_local.para()

    def test_abrir_pasta_permitida(self, api, monkeypatch):
        chamados = []
        monkeypatch.setattr(Api, "_abre_no_sistema", staticmethod(chamados.append))
        assert api.abrir_pasta("pacotes")["ok"] is True
        assert chamados
