# -*- coding: utf-8 -*-
"""Validacao e higienizacao de PDF.

Os PDFs maliciosos sao construidos aqui, com PyMuPDF, em vez de guardados
como fixtures binarias: dentro do repositorio um arquivo com `/JavaScript`
seria detectado por antivirus e por scanners de seguranca do GitHub, e o
repositorio da vitrine nao precisa carregar isso.
"""
from __future__ import annotations

import pymupdf
import pytest

from vitrine_core.pdf_seguro import (
    LADO_MAX_PT,
    PAGINAS_MAX,
    TAMANHO_MAX,
    InfoPdf,
    PdfInvalido,
    higieniza,
    higieniza_dados,
    tokens_perigosos,
    valida,
    valida_assinatura,
    valida_dados,
    valida_tamanho,
)


# --------------------------------------------------------------------------
# Fabricas de PDF para os testes
# --------------------------------------------------------------------------

def pdf_simples(paginas: int = 1, largura: float = 810, altura: float = 1012.5) -> bytes:
    doc = pymupdf.open()
    for i in range(paginas):
        p = doc.new_page(width=largura, height=altura)
        p.insert_text((72, 100), f"Pagina {i + 1}", fontsize=24)
    dados = doc.tobytes()
    doc.close()
    return dados


def pdf_com_javascript() -> bytes:
    """PDF com os dois vetores classicos de JavaScript.

    Escrito direto no catalogo com `xref_set_key` porque o PyMuPDF nao expoe
    API para *criar* JavaScript -- so para remover. E e exatamente esta forma
    que o `scrub()` da versao 1.28.2 deixa passar.
    """
    doc = pymupdf.open()
    doc.new_page(width=810, height=1012.5)
    cat = doc.pdf_catalog()
    # acao ao abrir o documento
    doc.xref_set_key(cat, "OpenAction", "<</S/JavaScript/JS(app.alert\\(1\\))>>")
    # arvore de nomes com scripts de documento
    doc.xref_set_key(
        cat, "Names", "<</JavaScript<</Names[(a)<</S/JavaScript/JS(x=1)>>]>>>>"
    )
    dados = doc.tobytes()
    doc.close()
    return dados


def pdf_com_acao_de_pagina() -> bytes:
    """Acao automatica na pagina (/AA), que dispara ao abri-la."""
    doc = pymupdf.open()
    pagina = doc.new_page(width=810, height=1012.5)
    doc.xref_set_key(
        pagina.xref, "AA", "<</O<</S/JavaScript/JS(app.alert\\(2\\))>>>>"
    )
    dados = doc.tobytes()
    doc.close()
    return dados


def pdf_com_launch() -> bytes:
    """Acao /Launch, que pede ao leitor para executar um programa."""
    doc = pymupdf.open()
    doc.new_page(width=810, height=1012.5)
    doc.xref_set_key(
        doc.pdf_catalog(),
        "OpenAction",
        "<</S/Launch/F(cmd.exe)>>",
    )
    dados = doc.tobytes()
    doc.close()
    return dados


def pdf_com_anexo() -> bytes:
    doc = pymupdf.open()
    doc.new_page(width=810, height=1012.5)
    doc.embfile_add("segredo.txt", b"conteudo anexado")
    dados = doc.tobytes()
    doc.close()
    return dados


def pdf_com_metadados() -> bytes:
    doc = pymupdf.open()
    doc.new_page(width=810, height=1012.5)
    doc.set_metadata(
        {
            "author": "Joao da Silva",
            "title": "Portfolio interno",
            "creator": "Canva",
            "producer": "Canva",
            "keywords": "id-interno-12345",
            "subject": "rascunho",
        }
    )
    dados = doc.tobytes()
    doc.close()
    return dados


@pytest.fixture
def grava(tmp_path):
    def _grava(dados: bytes, nome: str = "ficha.pdf"):
        p = tmp_path / nome
        p.write_bytes(dados)
        return p

    return _grava


# --------------------------------------------------------------------------
# Passo 1: tamanho
# --------------------------------------------------------------------------

class TestValidaTamanho:
    def test_tamanho_normal_passa(self):
        valida_tamanho(3 * 1024 * 1024)

    def test_no_limite_exato_passa(self):
        valida_tamanho(TAMANHO_MAX)

    def test_um_byte_acima_do_limite(self):
        with pytest.raises(PdfInvalido, match="25 MB"):
            valida_tamanho(TAMANHO_MAX + 1)

    def test_mensagem_traz_o_tamanho_do_arquivo(self):
        with pytest.raises(PdfInvalido, match="30.0 MB"):
            valida_tamanho(30 * 1024 * 1024)

    @pytest.mark.parametrize("n", [0, -1])
    def test_arquivo_vazio(self, n):
        with pytest.raises(PdfInvalido, match="vazio"):
            valida_tamanho(n)


# --------------------------------------------------------------------------
# Passo 2: assinatura
# --------------------------------------------------------------------------

class TestValidaAssinatura:
    def test_pdf_de_verdade(self):
        valida_assinatura(b"%PDF-1.7")

    @pytest.mark.parametrize(
        "inicio",
        [
            b"\x89PNG\r\n",  # PNG com extensao .pdf
            b"\xff\xd8\xff\xe0",  # JPEG
            b"PK\x03\x04",  # ZIP/docx
            b"<html>",
            b"",
            b"  %PDF-",  # a assinatura tem de estar NO INICIO
        ],
    )
    def test_recusa_o_que_nao_e_pdf(self, inicio):
        with pytest.raises(PdfInvalido, match="não é um PDF"):
            valida_assinatura(inicio)


# --------------------------------------------------------------------------
# Passos 3 a 6: o documento aberto
# --------------------------------------------------------------------------

class TestValida:
    def test_pdf_de_uma_pagina(self, grava):
        info = valida(grava(pdf_simples()))
        assert isinstance(info, InfoPdf)
        assert info.paginas == 1
        assert info.avisos == []
        assert round(info.largura_pt) == 810

    def test_extensao_e_ignorada(self, grava):
        """Um PDF valido passa mesmo com a extensao errada -- e o contrario
        (extensao .pdf em outro formato) e recusado. O que vale e o conteudo."""
        info = valida(grava(pdf_simples(), "ficha.txt"))
        assert info.paginas == 1

    def test_png_renomeado_para_pdf(self, grava):
        with pytest.raises(PdfInvalido, match="não é um PDF"):
            valida(grava(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200, "ficha.pdf"))

    def test_pdf_corrompido(self, grava):
        # comeca com %PDF- (passa o passo 2) mas o resto e lixo
        with pytest.raises(PdfInvalido, match="Não conseguimos ler"):
            valida(grava(b"%PDF-1.4\n" + b"\xff" * 5000))

    def test_pdf_com_senha(self, grava, tmp_path):
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
        with pytest.raises(PdfInvalido, match="senha"):
            valida(alvo)

    def test_duas_paginas_avisa_mas_passa(self, grava):
        info = valida(grava(pdf_simples(paginas=2)))
        assert info.paginas == 2
        assert any("2 paginas" in a for a in info.avisos)

    def test_no_limite_de_paginas_passa(self, grava):
        assert valida(grava(pdf_simples(paginas=PAGINAS_MAX))).paginas == PAGINAS_MAX

    def test_paginas_demais(self, grava):
        with pytest.raises(PdfInvalido, match="6 páginas"):
            valida(grava(pdf_simples(paginas=PAGINAS_MAX + 1)))

    def test_pagina_gigante(self, grava):
        """Uma pagina enorme nao e invalida para o PDF, mas renderizar em 2x
        alocaria gigabytes de pixmap -- por isso e recusada antes."""
        with pytest.raises(PdfInvalido, match="muito maior"):
            valida(grava(pdf_simples(largura=LADO_MAX_PT + 100, altura=1000)))

    def test_no_limite_de_tamanho_de_pagina_passa(self, grava):
        info = valida(grava(pdf_simples(largura=LADO_MAX_PT, altura=1000)))
        assert round(info.largura_pt) == LADO_MAX_PT

    def test_arquivo_grande_demais(self, grava):
        dados = pdf_simples() + b"\n%" + b"a" * (TAMANHO_MAX + 1)
        with pytest.raises(PdfInvalido, match="limite"):
            valida(grava(dados))

    def test_arquivo_inexistente(self, tmp_path):
        with pytest.raises(PdfInvalido):
            valida(tmp_path / "nao-existe.pdf")

    def test_valida_dados_faz_as_mesmas_checagens(self):
        assert valida_dados(pdf_simples()).paginas == 1
        with pytest.raises(PdfInvalido, match="não é um PDF"):
            valida_dados(b"\x89PNG\r\n")
        with pytest.raises(PdfInvalido, match="páginas"):
            valida_dados(pdf_simples(paginas=9))

    def test_limite_de_tempo_nao_atrapalha_um_pdf_normal(self, grava):
        assert valida(grava(pdf_simples()), segundos=15).paginas == 1

    def test_limite_de_tempo_repassa_o_erro_de_validacao(self, grava):
        """Um PDF recusado dentro da thread precisa erguer a mesma excecao
        na thread principal, nao um timeout genérico."""
        with pytest.raises(PdfInvalido, match="páginas"):
            valida(grava(pdf_simples(paginas=9)), segundos=15)


# --------------------------------------------------------------------------
# Higienizacao
# --------------------------------------------------------------------------

class TestHigieniza:
    def test_remove_javascript(self):
        """O scrub() do PyMuPDF 1.28.2 NAO remove um /OpenAction com acao de
        JavaScript no catalogo -- conferido na versao instalada. Se este teste
        voltar a falhar depois de um upgrade da biblioteca, e porque a remocao
        manual de `_remove_acoes` deixou de rodar, nao porque deixou de ser
        necessaria."""
        entrada = pdf_com_javascript()
        assert tokens_perigosos(entrada), "o PDF de teste deveria ter JS"
        assert tokens_perigosos(higieniza_dados(entrada)) == []

    def test_remove_acao_automatica_de_pagina(self):
        entrada = pdf_com_acao_de_pagina()
        assert tokens_perigosos(entrada)
        assert tokens_perigosos(higieniza_dados(entrada)) == []

    def test_remove_acao_launch(self):
        entrada = pdf_com_launch()
        assert "/Launch" in tokens_perigosos(entrada)
        assert tokens_perigosos(higieniza_dados(entrada)) == []

    def test_remove_anexo(self):
        entrada = pdf_com_anexo()
        assert b"conteudo anexado" in entrada
        saida = higieniza_dados(entrada)
        assert b"conteudo anexado" not in saida
        assert tokens_perigosos(saida) == []

    def test_remove_metadados(self):
        saida = higieniza_dados(pdf_com_metadados())
        doc = pymupdf.open(stream=saida, filetype="pdf")
        try:
            sobrou = {k: v for k, v in doc.metadata.items() if v and k != "format"}
        finally:
            doc.close()
        assert sobrou == {}

    def test_o_nome_do_autor_nao_sobra_nos_bytes(self):
        saida = higieniza_dados(pdf_com_metadados())
        assert b"Joao da Silva" not in saida
        assert b"id-interno-12345" not in saida

    def test_o_conteudo_visivel_continua_la(self):
        saida = higieniza_dados(pdf_simples())
        doc = pymupdf.open(stream=saida, filetype="pdf")
        try:
            assert "Pagina 1" in doc[0].get_text("text")
        finally:
            doc.close()

    def test_a_pagina_renderiza_igual(self):
        """A ficha em imagem e gerada do original; se a higienizacao mudasse
        o render, o PDF baixado e a imagem publicada divergiriam."""
        entrada = pdf_simples()
        a = pymupdf.open(stream=entrada, filetype="pdf")
        b = pymupdf.open(stream=higieniza_dados(entrada), filetype="pdf")
        try:
            m = pymupdf.Matrix(2, 2)
            assert (
                a[0].get_pixmap(matrix=m, alpha=False).samples
                == b[0].get_pixmap(matrix=m, alpha=False).samples
            )
        finally:
            a.close()
            b.close()

    def test_deterministico(self, grava):
        """Sem isso o build reescreveria os 60 ficha.pdf em toda execucao: o
        MuPDF sorteia um /ID novo a cada gravacao se no_new_id nao for usado."""
        p = grava(pdf_simples())
        assert higieniza(p) == higieniza(p)

    def test_higienizar_duas_vezes_e_estavel(self):
        uma = higieniza_dados(pdf_simples())
        assert higieniza_dados(uma) == higieniza_dados(uma)

    def test_continua_sendo_um_pdf_valido(self, grava, tmp_path):
        saida = tmp_path / "saida.pdf"
        saida.write_bytes(higieniza(grava(pdf_com_javascript())))
        assert valida(saida).paginas == 1


class TestTokensPerigosos:
    def test_lista_vazia_em_pdf_limpo(self):
        assert tokens_perigosos(pdf_simples()) == []

    @pytest.mark.parametrize(
        "dados",
        [
            b"<</S/JavaScript/JS(x)>>",
            b"/OpenAction 5 0 R",
            b"/Launch",
            b"/EmbeddedFile>>",
            b"/JS(app.alert(1))",
        ],
    )
    def test_acha_o_token(self, dados):
        assert tokens_perigosos(dados)

    @pytest.mark.parametrize(
        "dados",
        [
            b"/EmbeddedFiles<<>>",  # a chave da arvore de nomes, nao um anexo
            b"/JSomething",
            b"/JavaScriptX",
            b"/LaunchPad",
        ],
    )
    def test_nome_mais_longo_nao_e_o_token(self, dados):
        """Um nome em PDF termina num delimitador. `/EmbeddedFiles` (a chave da
        arvore de nomes, que sobra vazia depois da limpeza) nao pode contar
        como `/EmbeddedFile`, senao o build recusaria um PDF ja limpo."""
        assert tokens_perigosos(dados) == []
