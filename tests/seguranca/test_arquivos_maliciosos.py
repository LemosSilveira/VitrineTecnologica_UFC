# -*- coding: utf-8 -*-
"""Arquivos hostis chegando pelo painel (PRD 12.2).

Os arquivos sao construidos em tempo de execucao, nao guardados como fixtures:
um PNG que declara 50.000x50.000 ou um PDF com `/JavaScript` dentro do
repositorio seriam sinalizados por antivirus e por scanners de seguranca, e a
vitrine nao precisa carregar isso.
"""
from __future__ import annotations

import base64
import io
import struct
import zlib

import pymupdf
import pytest
from PIL import Image

from conftest import escreve_imagem, escreve_pdf
from painel.armazenamento import ErroDeArmazenamento, Quarentena
from vitrine_core import imagens
from vitrine_core.imagens import ImagemInvalida, valida_capa_dados
from vitrine_core.pdf_seguro import TAMANHO_MAX, tokens_perigosos


@pytest.fixture
def quarentena(ambiente):
    return Quarentena(ambiente.local / "quarentena")


def b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode("ascii")


# --------------------------------------------------------------------------
# Fabricas de arquivo hostil
# --------------------------------------------------------------------------

def png_que_declara_tamanho_absurdo(largura: int, altura: int) -> bytes:
    """PNG valido de poucos bytes que DIZ ter largura x altura.

    E a bomba de descompressao classica: Pillow le o cabecalho e tentaria
    alocar largura*altura*3 bytes -- 7,5 GB para 50.000x50.000.
    """

    def pedaco(tipo: bytes, dados: bytes) -> bytes:
        return (
            struct.pack(">I", len(dados))
            + tipo
            + dados
            + struct.pack(">I", zlib.crc32(tipo + dados))
        )

    ihdr = struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + pedaco(b"IHDR", ihdr)
        + pedaco(b"IDAT", zlib.compress(b"\x00" * 16))
        + pedaco(b"IEND", b"")
    )


def jpeg_poliglota() -> bytes:
    """JPEG valido com um ZIP colado no fim.

    O arquivo abre como imagem E como arquivo compactado. Reencodar pelos
    pixels e o que descarta o apendice.
    """
    buf = io.BytesIO()
    Image.new("RGB", (900, 900), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue() + b"PK\x03\x04" + b"conteudo escondido no zip" * 20


def jpeg_com_metadados() -> bytes:
    """JPEG com EXIF preenchido, incluindo GPS."""
    im = Image.new("RGB", (900, 900), (40, 50, 60))
    exif = Image.Exif()
    exif[0x010F] = "FABRICANTE-SECRETO"  # Make
    exif[0x0110] = "MODELO-SECRETO"  # Model
    exif[0x013B] = "AUTOR-SECRETO"  # Artist
    exif[0x8298] = "COPYRIGHT-SECRETO"  # Copyright
    gps = exif.get_ifd(0x8825)
    gps[1] = "S"
    gps[2] = (3.0, 43.0, 0.0)  # Fortaleza, aproximado
    gps[3] = "W"
    gps[4] = (38.0, 32.0, 0.0)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def pdf_com_javascript() -> bytes:
    doc = pymupdf.open()
    doc.new_page(width=810, height=1012.5)
    cat = doc.pdf_catalog()
    doc.xref_set_key(cat, "OpenAction", "<</S/JavaScript/JS(app.alert\\(1\\))>>")
    doc.xref_set_key(
        cat, "Names", "<</JavaScript<</Names[(a)<</S/JavaScript/JS(x=1)>>]>>>>"
    )
    dados = doc.tobytes()
    doc.close()
    return dados


def pdf_com_anexo() -> bytes:
    doc = pymupdf.open()
    doc.new_page(width=810, height=1012.5)
    doc.embfile_add("segredo.txt", b"CONTEUDO-ANEXADO-SECRETO")
    dados = doc.tobytes()
    doc.close()
    return dados


def pdf_de_n_paginas(n: int) -> bytes:
    doc = pymupdf.open()
    for _ in range(n):
        doc.new_page(width=810, height=1012.5)
    dados = doc.tobytes()
    doc.close()
    return dados


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------

class TestPdfHostil:
    def test_maior_que_25MB(self, quarentena):
        grande = pdf_de_n_paginas(1) + b"\n%" + b"a" * (TAMANHO_MAX + 1)
        with pytest.raises(ErroDeArmazenamento, match="limite"):
            quarentena.recebe_bytes("pdf", grande)

    def test_base64_grande_nem_chega_a_decodificar(self, quarentena):
        with pytest.raises(ErroDeArmazenamento, match="limite"):
            quarentena.recebe_base64("pdf", "A" * (34 * 1024 * 1024))

    def test_png_com_extensao_pdf(self, quarentena, tmp_path):
        falso = tmp_path / "ficha.pdf"
        falso.write_bytes(escreve_imagem(tmp_path / "x.png").read_bytes())
        with pytest.raises(ErroDeArmazenamento, match="não é um PDF"):
            quarentena.recebe_do_disco("pdf", str(falso))

    def test_pdf_com_extensao_png_ainda_vale_como_pdf(self, quarentena, tmp_path):
        """O que decide e o conteudo, nao a extensao."""
        disfarcado = tmp_path / "ficha.png"
        disfarcado.write_bytes(pdf_de_n_paginas(1))
        assert quarentena.recebe_do_disco("pdf", str(disfarcado)).tipo == "pdf"

    def test_pdf_criptografado(self, quarentena, tmp_path):
        doc = pymupdf.open()
        doc.new_page(width=810, height=1012.5)
        alvo = tmp_path / "trancado.pdf"
        doc.save(
            alvo,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw="segredo",
            owner_pw="segredo",
        )
        doc.close()
        with pytest.raises(ErroDeArmazenamento, match="senha"):
            quarentena.recebe_do_disco("pdf", str(alvo))

    def test_pdf_corrompido(self, quarentena):
        with pytest.raises(ErroDeArmazenamento, match="Não conseguimos ler"):
            quarentena.recebe_bytes("pdf", b"%PDF-1.4\n" + b"\xff" * 5000)

    def test_pdf_de_seis_paginas(self, quarentena):
        with pytest.raises(ErroDeArmazenamento, match="6 páginas"):
            quarentena.recebe_bytes("pdf", pdf_de_n_paginas(6))

    def test_pagina_de_20000_pontos(self, quarentena):
        doc = pymupdf.open()
        doc.new_page(width=20000, height=20000)
        dados = doc.tobytes()
        doc.close()
        with pytest.raises(ErroDeArmazenamento, match="muito maior"):
            quarentena.recebe_bytes("pdf", dados)

    def test_pdf_vazio(self, quarentena):
        with pytest.raises(ErroDeArmazenamento):
            quarentena.recebe_bytes("pdf", b"")


class TestPdfPublicado:
    """O que o visitante baixa nao pode ter nada disso (PRD 5.4)."""

    def _publica(self, api, dados_pdf, tmp_path):
        pdf = tmp_path / "hostil.pdf"
        pdf.write_bytes(dados_pdf)
        capa = escreve_imagem(tmp_path / "capa.png", 900)
        t_pdf = api.receber_arquivo("pdf", "f.pdf", b64(pdf.read_bytes()))
        assert t_pdf["ok"], t_pdf
        t_capa = api.receber_arquivo("capa", "c.png", b64(capa.read_bytes()))
        r = api.salvar(
            {
                "numero": "BR 10 2025 077777 7",
                "categoria": "Alimentos",
                "titulo": "Patente com ficha hostil para o teste",
                "secoes": {"oQueE": "Uma descricao com mais de quarenta caracteres."},
            },
            t_capa["dados"]["token"],
            t_pdf["dados"]["token"],
        )
        assert r["ok"], r
        publicados = list(
            (api._ambiente.site / "assets" / "patentes").glob("*/ficha.pdf")
        )
        assert publicados
        return publicados

    def test_javascript_nao_sobrevive(self, api, tmp_path):
        for p in self._publica(api, pdf_com_javascript(), tmp_path):
            assert tokens_perigosos(p.read_bytes()) == [], p.parent.name

    def test_anexo_nao_sobrevive(self, api, tmp_path):
        for p in self._publica(api, pdf_com_anexo(), tmp_path):
            bruto = p.read_bytes()
            assert b"CONTEUDO-ANEXADO-SECRETO" not in bruto
            assert tokens_perigosos(bruto) == []

    def test_metadados_nao_sobrevivem(self, api, tmp_path):
        doc = pymupdf.open()
        doc.new_page(width=810, height=1012.5)
        doc.set_metadata({"author": "AUTOR-SECRETO", "title": "TITULO-INTERNO"})
        dados = doc.tobytes()
        doc.close()

        for p in self._publica(api, dados, tmp_path):
            bruto = p.read_bytes()
            assert b"AUTOR-SECRETO" not in bruto
            assert b"TITULO-INTERNO" not in bruto

    def test_o_original_no_acervo_fica_intacto(self, api, tmp_path):
        """O acervo e a fonte da verdade: a higienizacao vale para a copia
        publicada, nao para o original."""
        self._publica(api, pdf_com_javascript(), tmp_path)
        originais = list(api._ambiente.acervo.glob("*/*.pdf"))
        hostil = [p for p in originais if tokens_perigosos(p.read_bytes())]
        assert hostil, "o original deveria continuar com o JavaScript"


# --------------------------------------------------------------------------
# Imagem
# --------------------------------------------------------------------------

class TestImagemHostil:
    def test_bomba_de_descompressao(self, quarentena):
        """PNG de poucos bytes que declara 50.000x50.000: Pillow tentaria
        alocar 7,5 GB."""
        with pytest.raises(ErroDeArmazenamento):
            quarentena.recebe_bytes("capa", png_que_declara_tamanho_absurdo(50000, 50000))

    def test_no_limite_de_pixels(self):
        """Pouco acima de 40 megapixels tambem e recusado."""
        with pytest.raises(ImagemInvalida):
            valida_capa_dados(png_que_declara_tamanho_absurdo(7000, 7000))

    def test_arquivo_que_nao_e_imagem(self, quarentena):
        with pytest.raises(ErroDeArmazenamento, match="não é uma imagem"):
            quarentena.recebe_bytes("capa", b"%PDF-1.4\n" + b"\x00" * 500)

    def test_imagem_truncada(self, quarentena):
        boa = io.BytesIO()
        Image.new("RGB", (900, 900)).save(boa, format="PNG")
        with pytest.raises(ErroDeArmazenamento):
            quarentena.recebe_bytes("capa", boa.getvalue()[:200])

    def test_menor_que_400(self, quarentena, tmp_path):
        pequena = escreve_imagem(tmp_path / "p.png", 300)
        with pytest.raises(ErroDeArmazenamento, match="400"):
            quarentena.recebe_do_disco("capa", str(pequena))

    def test_entre_400_e_800_passa_com_aviso(self, quarentena, tmp_path):
        item = quarentena.recebe_do_disco("capa", str(escreve_imagem(tmp_path / "m.png", 500)))
        assert any("borrada" in a for a in item.avisos)

    def test_nao_quadrada_pede_recorte(self, quarentena, tmp_path):
        item = quarentena.recebe_do_disco(
            "capa", str(escreve_imagem(tmp_path / "r.png", 600, 900))
        )
        assert item.quadrada is False


class TestImagemPublicada:
    def _publica(self, api, dados_img, tmp_path, recorte=None):
        img = tmp_path / "capa.bin"
        img.write_bytes(dados_img)
        t = api.receber_arquivo("capa", "c.png", b64(dados_img))
        assert t["ok"], t
        dados = {
            "numero": "BR 10 2025 088888 8",
            "categoria": "Alimentos",
            "titulo": "Patente com capa hostil para o teste",
            "secoes": {"oQueE": "Uma descricao com mais de quarenta caracteres."},
        }
        if recorte:
            dados["recorte"] = recorte
        r = api.salvar(dados, t["dados"]["token"])
        assert r["ok"], r
        site = api._ambiente.site / "assets" / "patentes"
        return list(site.glob("*/capa-*.webp")), list(api._ambiente.acervo.glob("*/*.png"))

    def test_poliglota_perde_o_zip(self, api, tmp_path):
        """Reencodar pelos pixels descarta o apendice: o arquivo publicado nao
        e mais um ZIP valido."""
        publicadas, no_acervo = self._publica(
            api, jpeg_poliglota(), tmp_path, recorte={"x": 0, "y": 0, "lado": 900}
        )
        for p in publicadas + no_acervo:
            bruto = p.read_bytes()
            assert b"PK\x03\x04" not in bruto, p.name
            assert b"conteudo escondido" not in bruto, p.name

    def test_exif_e_gps_nao_sobrevivem(self, api, tmp_path):
        publicadas, no_acervo = self._publica(
            api, jpeg_com_metadados(), tmp_path, recorte={"x": 0, "y": 0, "lado": 900}
        )
        for p in publicadas + no_acervo:
            bruto = p.read_bytes()
            for segredo in (
                b"FABRICANTE-SECRETO",
                b"MODELO-SECRETO",
                b"AUTOR-SECRETO",
                b"COPYRIGHT-SECRETO",
            ):
                assert segredo not in bruto, f"{segredo!r} em {p.name}"
            assert b"Exif" not in bruto, p.name


class TestRecorte:
    """As coordenadas vem da interface: nao se confia nelas."""

    def _tenta(self, api, tmp_path, recorte):
        img = escreve_imagem(tmp_path / "r.png", 600, 900)
        t = api.receber_arquivo("capa", "r.png", b64(img.read_bytes()))
        return api.salvar(
            {
                "numero": "BR 10 2025 066666 6",
                "categoria": "Alimentos",
                "titulo": "Patente para testar o recorte da capa",
                "secoes": {"oQueE": "Uma descricao com mais de quarenta caracteres."},
                "recorte": recorte,
            },
            t["dados"]["token"],
        )

    def test_recorte_valido(self, api, tmp_path):
        assert self._tenta(api, tmp_path, {"x": 0, "y": 150, "lado": 600})["ok"] is True

    @pytest.mark.parametrize(
        "recorte",
        [
            {"x": -10, "y": 0, "lado": 600},
            {"x": 0, "y": 0, "lado": 601},  # passa da largura
            {"x": 100, "y": 0, "lado": 600},  # comeca dentro, termina fora
            {"x": 0, "y": 0, "lado": 100},  # menor que o minimo
            {"x": 0, "y": 0, "lado": 0},
            {"x": "a", "y": 0, "lado": 600},
            {"x": 0, "y": 0},  # sem lado
        ],
    )
    def test_recorte_invalido_e_recusado(self, api, tmp_path, recorte):
        """Um recorte fora da borda faria o Pillow devolver area preta em vez
        de erro, e a capa sairia com uma faixa vazia."""
        r = self._tenta(api, tmp_path, recorte)
        assert r["ok"] is False
        assert list(api._ambiente.acervo.glob("2. *")) == []
