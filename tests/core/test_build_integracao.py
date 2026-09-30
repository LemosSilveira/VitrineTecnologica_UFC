# -*- coding: utf-8 -*-
"""O build de ponta a ponta, sobre um acervo sintetico.

Monta um acervo de mentira em `tmp_path` -- pastas no padrao, PDFs gerados
com o mesmo template de secoes das fichas reais e capas PNG -- e roda
`roda_build` nele. E o unico jeito de cobrir oculta, lixeira, patente sem
PDF e a limpeza de assets sem mexer no acervo de verdade, que e somente
leitura.
"""
from __future__ import annotations

import json

import pymupdf
import pytest
from PIL import Image

from vitrine_core.build import roda_build

FICHA = """{titulo}
O que é?
{oQueE}
Problema que resolve
Um problema qualquer que esta tecnologia resolve.
Exemplo de uso
Uso em laboratorio e na industria.
Diferenciais competitivos
- Primeiro diferencial
- Segundo diferencial
Benefício principal
O beneficio principal desta tecnologia.
Nível de maturidade
TRL 5-6
"""


def escreve_pdf(caminho, titulo: str, o_que_e: str) -> None:
    """PDF com o titulo em fonte grande (e assim que o build o identifica).

    Os diferenciais usam `-` como marcador, e nao o ✅ das fichas reais: a
    Helvetica embutida no PyMuPDF nao tem o emoji e o escreveria como `?`.
    `limpa_diferenciais` reconhece os dois.
    """
    doc = pymupdf.open()
    pagina = doc.new_page(width=810, height=1012.5)
    pagina.insert_textbox(
        pymupdf.Rect(40, 40, 770, 200), titulo, fontsize=28, fontname="helv"
    )
    corpo = FICHA.format(titulo="", oQueE=o_que_e).strip()
    pagina.insert_textbox(
        pymupdf.Rect(40, 220, 770, 980), corpo, fontsize=11, fontname="helv"
    )
    doc.save(caminho)
    doc.close()


def escreve_capa(caminho, lado: int = 900) -> None:
    Image.new("RGB", (lado, lado), (92, 6, 157)).save(caminho)


@pytest.fixture
def acervo(tmp_path):
    """Fabrica de acervo sintetico. Devolve (raiz_acervo, add, raiz_site)."""
    raiz = tmp_path / "acervo"
    raiz.mkdir()
    site = tmp_path / "site"
    (site / "js" / "data").mkdir(parents=True)
    (site / "scripts").mkdir(parents=True)

    def add(
        pid: int,
        *,
        categoria: str = "Alimentos",
        titulo: str | None = None,
        com_pdf: bool = True,
        com_capa: bool = True,
        patente_json: dict | None = None,
        prefixo_pasta: str = "",
    ):
        titulo = titulo or f"Tecnologia numero {pid} para testes"
        numero = f"BR 10 2025 {pid:06d} 1"
        pasta = raiz / f"{prefixo_pasta}{pid}. {numero}"
        pasta.mkdir()
        nome = f"{pid}. {categoria} - {numero} - {titulo}"
        if com_pdf:
            escreve_pdf(pasta / f"{nome}.pdf", titulo, f"O que a tecnologia {pid} e.")
        if com_capa:
            escreve_capa(pasta / f"{nome}.png")
        if patente_json is not None:
            (pasta / "patente.json").write_text(
                json.dumps(patente_json, ensure_ascii=False), encoding="utf-8"
            )
        return pasta

    return raiz, add, site


CATS = None  # usa o dados/categorias.json do repositorio


def build(acervo):
    raiz, _add, site = acervo
    return roda_build(raiz, site, CATS), site


def patentes_js(site):
    return (site / "js" / "data" / "patentes.js").read_text(encoding="utf-8")


def slugs_em_assets(site):
    base = site / "assets" / "patentes"
    return sorted(p.name for p in base.iterdir()) if base.is_dir() else []


class TestCaminhoFeliz:
    def test_duas_patentes_entram_na_vitrine(self, acervo):
        _raiz, add, _site = acervo
        add(1)
        add(2, categoria="Engenharias")
        res, site = build(acervo)

        assert res.erros == []
        assert [p["id"] for p in res.patentes] == [1, 2]
        assert "window.PATENTES" in patentes_js(site)
        assert len(slugs_em_assets(site)) == 2

    def test_gera_os_cinco_arquivos_por_patente(self, acervo):
        _raiz, add, _site = acervo
        add(1)
        _res, site = build(acervo)
        pasta = (site / "assets" / "patentes" / slugs_em_assets(site)[0])
        assert sorted(f.name for f in pasta.iterdir()) == [
            "capa-400.webp",
            "capa-800.webp",
            "ficha-1620.webp",
            "ficha-600.webp",
            "ficha.pdf",
        ]

    def test_extrai_as_secoes_e_o_trl(self, acervo):
        _raiz, add, _site = acervo
        add(1)
        res, _site = build(acervo)
        p = res.patentes[0]
        assert p["secoes"]["oQueE"]
        assert p["secoes"]["diferenciais"] == ["Primeiro diferencial", "Segundo diferencial"]
        assert p["trl"]["min"] == 5 and p["trl"]["max"] == 6
        assert p["trl"]["texto"].startswith("TRL 5")

    def test_e_idempotente(self, acervo):
        _raiz, add, _site = acervo
        add(1)
        res1, site = build(acervo)
        antes = {
            f: f.stat().st_mtime_ns
            for f in (site / "assets").rglob("*")
            if f.is_file()
        }
        res2, _ = build(acervo)
        depois = {
            f: f.stat().st_mtime_ns
            for f in (site / "assets").rglob("*")
            if f.is_file()
        }
        assert res1.js_mudou is True
        assert res2.js_mudou is False
        assert antes == depois


class TestOculta:
    def test_sai_do_patentes_js(self, acervo):
        _raiz, add, _site = acervo
        add(1)
        add(2, patente_json={"versao": 1, "oculta": True})
        res, site = build(acervo)

        assert [p["id"] for p in res.patentes] == [1]
        assert res.ocultas == [2]
        assert "Tecnologia numero 2" not in patentes_js(site)

    def test_nao_e_erro_nem_impede_o_build(self, acervo):
        _raiz, add, _site = acervo
        add(1, patente_json={"versao": 1, "oculta": True})
        res, _site = build(acervo)
        assert res.erros == []

    def test_os_assets_dela_sao_removidos(self, acervo):
        """Esconder so no cliente nao bastaria: o PDF e a ficha nao podem ficar
        acessiveis por URL direta (PRD 4.3)."""
        _raiz, add, _site = acervo
        pasta = add(1)
        add(2)
        _res, site = build(acervo)
        assert len(slugs_em_assets(site)) == 2

        (pasta / "patente.json").write_text(
            json.dumps({"versao": 1, "oculta": True}), encoding="utf-8"
        )
        res2, _ = build(acervo)
        assert res2.ocultas == [1]
        assert len(slugs_em_assets(site)) == 1
        assert not any("numero-1" in s for s in slugs_em_assets(site))

    def test_volta_a_vitrine_quando_deixa_de_estar_oculta(self, acervo):
        _raiz, add, _site = acervo
        pasta = add(1, patente_json={"versao": 1, "oculta": True})
        _res, site = build(acervo)
        assert slugs_em_assets(site) == []

        (pasta / "patente.json").write_text(
            json.dumps({"versao": 1, "oculta": False}), encoding="utf-8"
        )
        res2, _ = build(acervo)
        assert [p["id"] for p in res2.patentes] == [1]
        assert len(slugs_em_assets(site)) == 1

    def test_aparece_no_relatorio(self, acervo):
        _raiz, add, _site = acervo
        add(1)
        add(2, patente_json={"versao": 1, "oculta": True})
        _res, site = build(acervo)
        rel = (site / "scripts" / "build_report.md").read_text(encoding="utf-8")
        assert "Ocultas" in rel


class TestMerge:
    """Prioridade campo a campo: patente.json > texto do PDF > nome do arquivo."""

    def test_titulo_editado_vence_o_do_pdf(self, acervo):
        _raiz, add, _site = acervo
        add(1, patente_json={"versao": 1, "campos": {"titulo": "Titulo corrigido pela equipe"}})
        res, _site = build(acervo)
        assert res.patentes[0]["titulo"] == "Titulo corrigido pela equipe"

    def test_campo_ausente_continua_vindo_do_pdf(self, acervo):
        _raiz, add, _site = acervo
        add(1, patente_json={"versao": 1, "campos": {"titulo": "Titulo corrigido pela equipe"}})
        res, _site = build(acervo)
        # so o titulo foi editado; as secoes continuam as do PDF
        assert "O que a tecnologia 1 e" in res.patentes[0]["secoes"]["oQueE"]

    def test_secao_editada_vence_a_do_pdf(self, acervo):
        _raiz, add, _site = acervo
        novo = "Texto novo escrito pela equipe para esta secao, bem mais claro."
        add(1, patente_json={"versao": 1, "campos": {"secoes": {"oQueE": novo}}})
        res, _site = build(acervo)
        assert res.patentes[0]["secoes"]["oQueE"] == novo

    def test_secao_apagada_com_null(self, acervo):
        _raiz, add, _site = acervo
        add(1, patente_json={"versao": 1, "campos": {"secoes": {"problema": None}}})
        res, _site = build(acervo)
        assert res.patentes[0]["secoes"]["problema"] is None
        # as outras continuam
        assert res.patentes[0]["secoes"]["exemploDeUso"]

    def test_categoria_editada(self, acervo):
        _raiz, add, _site = acervo
        add(1, patente_json={"versao": 1, "campos": {"categoria": "Engenharias"}})
        res, _site = build(acervo)
        assert res.patentes[0]["categoria"] == "Engenharias"

    def test_numero_ano_e_tipo_nao_saem_do_json(self, acervo):
        """Eles vem sempre do nome da pasta. Nem existe campo para eles no
        esquema -- tentar sobrepor da erro de campo desconhecido."""
        _raiz, add, _site = acervo
        add(1, patente_json={"versao": 1, "campos": {"numero": "BR 20 1999 000000-0"}})
        res, _site = build(acervo)
        assert res.erros and "desconhecido" in res.erros[0]

    def test_trl_editado_tem_o_texto_recalculado(self, acervo):
        _raiz, add, _site = acervo
        add(1, patente_json={"versao": 1, "campos": {"trl": {"min": 8, "max": 9, "estimado": True}}})
        res, _site = build(acervo)
        trl = res.patentes[0]["trl"]
        assert (trl["min"], trl["max"]) == (8, 9)
        assert trl["estimado"] is True
        assert trl["texto"].startswith("TRL 8") and "estimado" in trl["texto"]

    def test_trl_apagado_com_null(self, acervo):
        _raiz, add, _site = acervo
        add(1, patente_json={"versao": 1, "campos": {"trl": None}})
        res, _site = build(acervo)
        assert res.patentes[0]["trl"] is None

    def test_resumo_e_sempre_recalculado(self, acervo):
        _raiz, add, _site = acervo
        novo = "Uma descricao nova e bem especifica desta tecnologia, escrita pela equipe."
        add(1, patente_json={"versao": 1, "campos": {"secoes": {"oQueE": novo}}})
        res, _site = build(acervo)
        assert res.patentes[0]["resumo"].startswith("Uma descricao nova")

    def test_json_invalido_e_erro_e_tira_a_patente_da_vitrine(self, acervo):
        _raiz, add, _site = acervo
        add(1)
        add(2, patente_json={"versao": 1, "campos": {"titulo": "curto"}})
        res, _site = build(acervo)
        assert [p["id"] for p in res.patentes] == [1]
        assert any("patente.json invalido" in e for e in res.erros)


class TestSemPdf:
    MINIMO = {
        "versao": 1,
        "campos": {
            "titulo": "Tecnologia cadastrada sem ficha",
            "categoria": "Alimentos",
            "secoes": {
                "oQueE": "Uma tecnologia cadastrada manualmente, sem a ficha em PDF."
            },
        },
    }

    def test_entra_na_vitrine_com_os_campos_minimos(self, acervo):
        _raiz, add, _site = acervo
        add(1, com_pdf=False, patente_json=self.MINIMO)
        res, _site = build(acervo)

        assert res.erros == []
        p = res.patentes[0]
        assert p["titulo"] == "Tecnologia cadastrada sem ficha"
        assert p["pdf"] is None
        assert p["imagens"]["ficha600"] is None
        assert p["imagens"]["ficha1620"] is None
        assert p["imagens"]["capa400"].endswith("capa-400.webp")

    def test_gera_aviso_e_nao_erro(self, acervo):
        _raiz, add, _site = acervo
        add(1, com_pdf=False, patente_json=self.MINIMO)
        res, _site = build(acervo)
        assert any("sem PDF" in a for a in res.avisos)

    def test_nao_gera_os_arquivos_da_ficha(self, acervo):
        _raiz, add, _site = acervo
        add(1, com_pdf=False, patente_json=self.MINIMO)
        _res, site = build(acervo)
        pasta = site / "assets" / "patentes" / slugs_em_assets(site)[0]
        assert sorted(f.name for f in pasta.iterdir()) == ["capa-400.webp", "capa-800.webp"]

    def test_o_json_vira_null_no_patentes_js(self, acervo):
        _raiz, add, _site = acervo
        add(1, com_pdf=False, patente_json=self.MINIMO)
        _res, site = build(acervo)
        js = patentes_js(site)
        assert "pdf: null" in js
        assert "ficha600: null" in js

    @pytest.mark.parametrize("faltando", ["titulo", "categoria", "secoes"])
    def test_sem_os_minimos_e_erro(self, acervo, faltando):
        _raiz, add, _site = acervo
        campos = dict(self.MINIMO["campos"])
        campos.pop(faltando)
        add(1, com_pdf=False, patente_json={"versao": 1, "campos": campos})
        res, _site = build(acervo)
        assert res.patentes == []
        assert any("sem PDF" in e for e in res.erros)

    def test_sem_pdf_e_sem_json_nenhum_e_erro(self, acervo):
        _raiz, add, _site = acervo
        add(1, com_pdf=False)
        res, _site = build(acervo)
        assert res.patentes == []
        assert any("sem PDF" in e for e in res.erros)

    def test_sem_capa_continua_sendo_erro(self, acervo):
        """A capa e obrigatoria: sem ela o card da grade nao existe."""
        _raiz, add, _site = acervo
        add(1, com_capa=False)
        res, _site = build(acervo)
        assert res.patentes == []
        assert any("sem imagem de capa" in e for e in res.erros)


class TestLixeira:
    def test_pasta_com_underscore_e_ignorada(self, acervo):
        """Excluir no painel move a pasta para `_lixeira`: nada e apagado de
        verdade, e o build simplesmente nao a ve (PRD 4.6)."""
        raiz, add, _site = acervo
        add(1)
        (raiz / "_lixeira").mkdir()
        add(2, prefixo_pasta="_")
        res, _site = build(acervo)
        assert [p["id"] for p in res.patentes] == [1]
        assert res.erros == []

    def test_pasta_com_ponto_e_ignorada(self, acervo):
        raiz, add, _site = acervo
        add(1)
        (raiz / ".backup").mkdir()
        res, _site = build(acervo)
        assert [p["id"] for p in res.patentes] == [1]
        assert res.erros == []

    def test_os_assets_da_excluida_saem_da_vitrine(self, acervo):
        raiz, add, _site = acervo
        pasta = add(1)
        add(2)
        _res, site = build(acervo)
        assert len(slugs_em_assets(site)) == 2

        pasta.rename(raiz / f"_{pasta.name}__20260929-120000")
        res2, _ = build(acervo)
        assert [p["id"] for p in res2.patentes] == [2]
        assert len(slugs_em_assets(site)) == 1


class TestGravacaoSoSemErro:
    def test_com_erro_o_patentes_js_anterior_fica_de_pe(self, acervo):
        """Reescrever com erro publicaria uma vitrine incompleta: as patentes
        que falharam sumiriam do site sem ninguem ter pedido (PRD 6.2)."""
        raiz, add, _site = acervo
        add(1)
        add(2)
        _res, site = build(acervo)
        bom = patentes_js(site)
        assert "Tecnologia numero 2" in bom

        # quebra a patente 2 com um patente.json invalido
        (raiz / "2. BR 10 2025 000002 1" / "patente.json").write_text(
            '{"versao": 1, "campos": {"titulo": "curto"}}', encoding="utf-8"
        )
        res2, _ = build(acervo)

        assert res2.erros
        assert res2.js_mudou is False
        assert patentes_js(site) == bom  # intacto

    def test_com_erro_os_assets_nao_sao_limpos(self, acervo):
        """Limpar com erro apagaria os assets de uma patente que ficou de fora
        por um problema temporario."""
        raiz, add, _site = acervo
        add(1)
        add(2)
        _res, site = build(acervo)
        antes = slugs_em_assets(site)

        (raiz / "2. BR 10 2025 000002 1" / "patente.json").write_text(
            '{"versao": 1, "campos": {"titulo": "curto"}}', encoding="utf-8"
        )
        res2, _ = build(acervo)
        assert res2.erros
        assert slugs_em_assets(site) == antes

    def test_o_relatorio_e_escrito_mesmo_com_erro(self, acervo):
        """O relatorio e como a equipe descobre o que deu errado: ele sai
        sempre, ao contrario do patentes.js."""
        _raiz, add, _site = acervo
        add(1, patente_json={"versao": 1, "campos": {"titulo": "curto"}})
        res, site = build(acervo)
        assert res.erros
        rel = (site / "scripts" / "build_report.md").read_text(encoding="utf-8")
        assert "## Erros" in rel
        assert "patente.json invalido" in rel


class TestLimpezaDeAssets:
    def test_pasta_orfa_por_mudanca_de_titulo_e_removida(self, acervo):
        """O slug vem do titulo: corrigir o titulo cria uma pasta nova, e a
        antiga ficaria orfa em assets/patentes."""
        _raiz, add, _site = acervo
        pasta = add(1)
        _res, site = build(acervo)
        antigo = slugs_em_assets(site)[0]

        (pasta / "patente.json").write_text(
            json.dumps(
                {"versao": 1, "campos": {"titulo": "Um titulo completamente diferente"}}
            ),
            encoding="utf-8",
        )
        res2, _ = build(acervo)
        novos = slugs_em_assets(site)
        assert antigo not in novos
        assert len(novos) == 1
        assert antigo in res2.assets_removidos

    def test_pasta_estranha_em_assets_e_removida(self, acervo):
        _raiz, add, _site = acervo
        add(1)
        _res, site = build(acervo)
        intruso = site / "assets" / "patentes" / "99-pasta-que-nao-deveria-estar-aqui"
        intruso.mkdir()
        (intruso / "lixo.txt").write_text("x", encoding="utf-8")

        res2, _ = build(acervo)
        assert not intruso.exists()
        assert "99-pasta-que-nao-deveria-estar-aqui" in res2.assets_removidos

    def test_nao_mexe_em_nada_fora_de_assets_patentes(self, acervo):
        _raiz, add, _site = acervo
        add(1)
        _res, site = build(acervo)
        outra = site / "assets" / "img"
        outra.mkdir(parents=True)
        (outra / "logo.svg").write_text("<svg/>", encoding="utf-8")

        build(acervo)
        assert (outra / "logo.svg").exists()
