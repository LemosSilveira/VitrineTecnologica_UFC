# -*- coding: utf-8 -*-
"""Quarentena, gravacao no acervo e lixeira."""
from __future__ import annotations

import base64
import json

import pytest

from conftest import escreve_imagem, escreve_pdf
from painel import armazenamento
from painel.armazenamento import ErroDeArmazenamento, Quarentena
from vitrine_core.acervo import le_patente_json
from vitrine_core.nomes import ARQUIVO_RE, PASTA_RE


@pytest.fixture
def quarentena(ambiente):
    return Quarentena(ambiente.local / "quarentena")


@pytest.fixture
def pdf_bom(tmp_path):
    return escreve_pdf(tmp_path / "ficha.pdf", "Titulo da ficha de teste")


@pytest.fixture
def capa_boa(tmp_path):
    return escreve_imagem(tmp_path / "capa.png", 900)


class TestQuarentenaEntrada:
    def test_recebe_pdf_do_disco(self, quarentena, pdf_bom):
        item = quarentena.recebe_do_disco("pdf", str(pdf_bom))
        assert item.tipo == "pdf"
        assert item.caminho.is_file()
        assert item.tamanho > 0

    def test_o_nome_de_origem_nao_e_usado(self, quarentena, tmp_path):
        """E do nome que viria `..\\..\\Windows` e `CON.pdf` (T5). O arquivo
        na quarentena tem nome fixo."""
        origem = escreve_pdf(tmp_path / "CON..\\..\\perigoso.pdf".replace("\\", "_"), "T")
        item = quarentena.recebe_do_disco("pdf", str(origem))
        assert item.caminho.name == "entrada.pdf"

    def test_recebe_base64(self, quarentena, pdf_bom):
        b64 = base64.b64encode(pdf_bom.read_bytes()).decode("ascii")
        item = quarentena.recebe_base64("pdf", b64)
        assert item.caminho.read_bytes() == pdf_bom.read_bytes()

    def test_aceita_data_url(self, quarentena, pdf_bom):
        b64 = base64.b64encode(pdf_bom.read_bytes()).decode("ascii")
        item = quarentena.recebe_base64("pdf", f"data:application/pdf;base64,{b64}")
        assert item.tipo == "pdf"

    def test_base64_invalido(self, quarentena):
        with pytest.raises(ErroDeArmazenamento, match="ler o arquivo"):
            quarentena.recebe_base64("pdf", "isto nao e base64!!!")

    def test_base64_grande_demais_nem_e_decodificado(self, quarentena):
        """O limite e conferido no comprimento do TEXTO: decodificar 33 MB de
        base64 so para descobrir que passa do limite seria desperdicio."""
        with pytest.raises(ErroDeArmazenamento, match="limite"):
            quarentena.recebe_base64("pdf", "A" * (34 * 1024 * 1024))

    def test_recebe_capa(self, quarentena, capa_boa):
        item = quarentena.recebe_do_disco("capa", str(capa_boa))
        assert item.tipo == "capa"
        assert (item.largura, item.altura) == (900, 900)
        assert item.quadrada is True

    def test_capa_nao_quadrada_e_sinalizada(self, quarentena, tmp_path):
        img = escreve_imagem(tmp_path / "retrato.png", 600, 900)
        item = quarentena.recebe_do_disco("capa", str(img))
        assert item.quadrada is False

    def test_capa_pequena_avisa(self, quarentena, tmp_path):
        img = escreve_imagem(tmp_path / "pequena.png", 500)
        item = quarentena.recebe_do_disco("capa", str(img))
        assert any("borrada" in a for a in item.avisos)

    @pytest.mark.parametrize("tipo", ["", "outro", None, 123, "PDF"])
    def test_tipo_desconhecido(self, quarentena, tipo):
        with pytest.raises(ErroDeArmazenamento, match="Tipo de arquivo"):
            quarentena.recebe_bytes(tipo, b"%PDF-1.4")

    def test_arquivo_inexistente(self, quarentena, tmp_path):
        with pytest.raises(ErroDeArmazenamento, match="nao existe"):
            quarentena.recebe_do_disco("pdf", str(tmp_path / "sumiu.pdf"))

    def test_arquivo_recusado_nao_fica_no_disco(self, quarentena, tmp_path):
        """Nao ha motivo para guardar o que foi recusado."""
        ruim = tmp_path / "ruim.pdf"
        ruim.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        with pytest.raises(ErroDeArmazenamento):
            quarentena.recebe_do_disco("pdf", str(ruim))
        assert list(quarentena.raiz.iterdir()) == []


class TestQuarentenaToken:
    def test_token_resolve(self, quarentena, pdf_bom):
        item = quarentena.recebe_do_disco("pdf", str(pdf_bom))
        assert quarentena.obtem(item.token) is item

    @pytest.mark.parametrize(
        "token",
        ["", None, 123, "abc", "../../etc/passwd", "z" * 32, "A" * 32, [], {}],
    )
    def test_token_invalido(self, quarentena, token):
        """A interface so trabalha com token: um caminho de disco nunca chega
        nem sai dela."""
        with pytest.raises(ErroDeArmazenamento, match="nao esta mais disponivel"):
            quarentena.obtem(token)

    def test_token_de_arquivo_apagado(self, quarentena, pdf_bom):
        item = quarentena.recebe_do_disco("pdf", str(pdf_bom))
        item.caminho.unlink()
        with pytest.raises(ErroDeArmazenamento):
            quarentena.obtem(item.token)

    def test_descarta(self, quarentena, pdf_bom):
        item = quarentena.recebe_do_disco("pdf", str(pdf_bom))
        quarentena.descarta(item.token)
        assert not item.caminho.parent.exists()

    def test_descarta_token_invalido_nao_quebra(self, quarentena):
        quarentena.descarta("nao-existe")
        quarentena.descarta(None)

    def test_limpa_sessoes_antigas(self, quarentena, pdf_bom):
        quarentena.recebe_do_disco("pdf", str(pdf_bom))
        quarentena.recebe_do_disco("pdf", str(pdf_bom))
        assert quarentena.limpa_sessoes_antigas() == 2
        assert list(quarentena.raiz.iterdir()) == []


class TestIdsENumeros:
    def test_proximo_id_em_acervo_vazio(self, ambiente):
        assert armazenamento.proximo_id(ambiente.acervo) == 1

    def test_proximo_id_e_o_maior_mais_um(self, ambiente):
        ambiente.add_patente(1)
        ambiente.add_patente(7)
        ambiente.add_patente(3)
        assert armazenamento.proximo_id(ambiente.acervo) == 8

    def test_a_lixeira_conta_para_o_proximo_id(self, ambiente):
        """IDs nunca sao reaproveitados: `patente.html?id=N` pode estar num
        e-mail ou indexada, e apontaria para outra tecnologia (PRD 4.5)."""
        ambiente.add_patente(1)
        lixeira = ambiente.acervo / "_lixeira"
        lixeira.mkdir()
        (lixeira / "9. BR 10 2020 000009 1__20260929-120000").mkdir()
        assert armazenamento.proximo_id(ambiente.acervo) == 10

    def test_numeros_usados(self, ambiente):
        ambiente.add_patente(1, numero="BR 10 2025 000001 1")
        ambiente.add_patente(2, numero="BR 20 2024 000002 2")
        usados = armazenamento.numeros_usados(ambiente.acervo)
        assert usados["BR 10 2025 000001-1"] == 1
        assert usados["BR 20 2024 000002-2"] == 2

    def test_numeros_da_lixeira_tambem_contam(self, ambiente):
        ambiente.add_patente(1)
        lixeira = ambiente.acervo / "_lixeira"
        lixeira.mkdir()
        (lixeira / "5. BR 10 2020 000005 1__20260929-120000").mkdir()
        usados = armazenamento.numeros_usados(ambiente.acervo)
        assert usados["BR 10 2020 000005-1"] == 5

    def test_pasta_da_patente(self, ambiente):
        pasta = ambiente.add_patente(3)
        assert armazenamento.pasta_da_patente(ambiente.acervo, 3) == pasta
        assert armazenamento.pasta_da_patente(ambiente.acervo, 99) is None


class TestGravaPatente:
    CAMPOS = {
        "titulo": "Tecnologia gravada pelo painel",
        "categoria": "Alimentos",
        "secoes": {"oQueE": "Uma descricao com mais de quarenta caracteres aqui."},
    }

    def test_cria_a_pasta_no_padrao(self, ambiente, pdf_bom, capa_boa):
        pasta = armazenamento.grava_patente(
            ambiente.acervo,
            patente_id=61,
            numero="BR 10 2025 012345-6",
            categoria="Alimentos",
            titulo=self.CAMPOS["titulo"],
            campos=self.CAMPOS,
            pdf=pdf_bom,
            capa=capa_boa,
        )
        assert pasta.name == "61. BR 10 2025 012345 6"
        assert PASTA_RE.match(pasta.name)

    def test_os_nomes_batem_com_o_padrao_do_build(self, ambiente, pdf_bom, capa_boa):
        """Se o nome nao casar com ARQUIVO_RE, o build nao extrai a area nem o
        titulo do nome -- e a patente cairia no caminho de erro."""
        pasta = armazenamento.grava_patente(
            ambiente.acervo,
            patente_id=61,
            numero="BR 10 2025 012345-6",
            categoria="Engenharias",
            titulo=self.CAMPOS["titulo"],
            campos=self.CAMPOS,
            pdf=pdf_bom,
            capa=capa_boa,
        )
        for f in pasta.iterdir():
            if f.suffix in (".pdf", ".png"):
                m = ARQUIVO_RE.match(f.stem)
                assert m, f.name
                assert m.group("cat").strip(" -") == "Engenharias"

    def test_grava_o_patente_json(self, ambiente, capa_boa):
        pasta = armazenamento.grava_patente(
            ambiente.acervo,
            patente_id=61,
            numero="BR 10 2025 012345-6",
            categoria="Alimentos",
            titulo=self.CAMPOS["titulo"],
            campos=self.CAMPOS,
            usuario="fulano",
            capa=capa_boa,
        )
        dados = json.loads((pasta / "patente.json").read_text(encoding="utf-8"))
        assert dados["versao"] == 1
        assert dados["atualizadoPor"] == "fulano"
        assert dados["campos"]["titulo"] == self.CAMPOS["titulo"]
        # e precisa passar pelo proprio esquema do core
        assert le_patente_json(pasta).campos["titulo"] == self.CAMPOS["titulo"]

    def test_capa_e_reencodada_para_png(self, ambiente, tmp_path):
        jpg = escreve_imagem(tmp_path / "capa.jpg", 900)
        pasta = armazenamento.grava_patente(
            ambiente.acervo,
            patente_id=61,
            numero="BR 10 2025 012345-6",
            categoria="Alimentos",
            titulo=self.CAMPOS["titulo"],
            campos=self.CAMPOS,
            capa=jpg,
        )
        imagens = [f for f in pasta.iterdir() if f.suffix == ".png"]
        assert len(imagens) == 1
        assert imagens[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_trocar_a_capa_remove_a_antiga(self, ambiente, capa_boa, tmp_path):
        """Duas imagens na pasta fariam o build escolher a primeira em ordem
        alfabetica -- a antiga poderia continuar sendo publicada."""
        args = dict(
            patente_id=61,
            numero="BR 10 2025 012345-6",
            categoria="Alimentos",
            campos=self.CAMPOS,
        )
        armazenamento.grava_patente(
            ambiente.acervo, titulo="Primeiro titulo da patente", capa=capa_boa, **args
        )
        nova = escreve_imagem(tmp_path / "nova.png", 1000)
        pasta = armazenamento.grava_patente(
            ambiente.acervo, titulo="Segundo titulo bem diferente", capa=nova, **args
        )
        assert len([f for f in pasta.iterdir() if f.suffix == ".png"]) == 1

    def test_o_pdf_vai_para_o_acervo_como_veio(self, ambiente, pdf_bom, capa_boa):
        """O original e a fonte da verdade; a higienizacao acontece na
        publicacao, sobre a copia."""
        pasta = armazenamento.grava_patente(
            ambiente.acervo,
            patente_id=61,
            numero="BR 10 2025 012345-6",
            categoria="Alimentos",
            titulo=self.CAMPOS["titulo"],
            campos=self.CAMPOS,
            pdf=pdf_bom,
            capa=capa_boa,
        )
        gravado = next(f for f in pasta.iterdir() if f.suffix == ".pdf")
        assert gravado.read_bytes() == pdf_bom.read_bytes()

    def test_editar_reaproveita_a_pasta_existente(self, ambiente, capa_boa):
        pasta = ambiente.add_patente(5)
        nova = armazenamento.grava_patente(
            ambiente.acervo,
            patente_id=5,
            numero="BR 10 2025 000005-1",
            categoria="Alimentos",
            titulo="Titulo corrigido pela equipe",
            campos={**self.CAMPOS, "titulo": "Titulo corrigido pela equipe"},
            capa=capa_boa,
        )
        assert nova == pasta
        assert len(list(ambiente.acervo.glob("5. *"))) == 1


class TestOcultaELixeira:
    def test_alterna_oculta(self, ambiente):
        pasta = ambiente.add_patente(1)
        armazenamento.alterna_oculta(ambiente.acervo, 1, True)
        assert le_patente_json(pasta).oculta is True
        armazenamento.alterna_oculta(ambiente.acervo, 1, False)
        assert le_patente_json(pasta).oculta is False

    def test_ocultar_preserva_os_campos_editados(self, ambiente):
        pasta = ambiente.add_patente(
            1,
            patente_json={
                "versao": 1,
                "campos": {"titulo": "Titulo editado pela equipe"},
            },
        )
        armazenamento.alterna_oculta(ambiente.acervo, 1, True)
        sobre = le_patente_json(pasta)
        assert sobre.oculta is True
        assert sobre.campos["titulo"] == "Titulo editado pela equipe"

    def test_ocultar_patente_inexistente(self, ambiente):
        with pytest.raises(ErroDeArmazenamento, match="Nao encontrei"):
            armazenamento.alterna_oculta(ambiente.acervo, 99, True)

    def test_ocultar_com_json_invalido_erra_antes(self, ambiente):
        pasta = ambiente.add_patente(1)
        (pasta / "patente.json").write_text("{ quebrado", encoding="utf-8")
        with pytest.raises(ErroDeArmazenamento, match="invalido"):
            armazenamento.alterna_oculta(ambiente.acervo, 1, True)

    def test_move_para_lixeira(self, ambiente):
        pasta = ambiente.add_patente(1)
        destino = armazenamento.move_para_lixeira(ambiente.acervo, 1)
        assert not pasta.exists()
        assert destino.is_dir()
        assert destino.parent.name == "_lixeira"
        assert list(destino.glob("*.pdf"))

    def test_nada_e_apagado(self, ambiente):
        pasta = ambiente.add_patente(1)
        antes = sorted(f.name for f in pasta.iterdir())
        destino = armazenamento.move_para_lixeira(ambiente.acervo, 1)
        assert sorted(f.name for f in destino.iterdir()) == antes

    def test_excluir_duas_vezes_no_mesmo_segundo_nao_aninha(self, ambiente):
        """Recadastrar e excluir de novo em sequencia cai no mesmo timestamp.
        Sem nome unico, `shutil.move` moveria a segunda pasta PARA DENTRO da
        primeira, em silencio."""
        ambiente.add_patente(1)
        primeiro = armazenamento.move_para_lixeira(ambiente.acervo, 1)
        ambiente.add_patente(1)
        segundo = armazenamento.move_para_lixeira(ambiente.acervo, 1)

        assert segundo != primeiro
        assert segundo.parent == primeiro.parent  # irmas, nao aninhadas
        lixeira = sorted(p.name for p in (ambiente.acervo / "_lixeira").iterdir())
        assert len(lixeira) == 2
        # as duas guardam a ficha: nenhuma foi engolida pela outra
        assert list(primeiro.glob("*.pdf")) and list(segundo.glob("*.pdf"))

    def test_a_lixeira_sai_da_vitrine(self, ambiente):
        from vitrine_core.acervo import lista_pastas

        ambiente.add_patente(1)
        ambiente.add_patente(2)
        armazenamento.move_para_lixeira(ambiente.acervo, 1)
        assert [p.name[:2].strip(". ") for p in lista_pastas(ambiente.acervo)] == ["2"]

    def test_excluir_patente_inexistente(self, ambiente):
        with pytest.raises(ErroDeArmazenamento, match="Nao encontrei"):
            armazenamento.move_para_lixeira(ambiente.acervo, 99)
