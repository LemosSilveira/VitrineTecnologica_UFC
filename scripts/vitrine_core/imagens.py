# -*- coding: utf-8 -*-
"""Geracao das imagens publicadas.

Tudo que vai ao ar e **reencodado** em WebP a partir dos pixels decodificados.
Isso nao e so compressao: reencodar elimina EXIF (inclusive GPS), perfis de
cor e qualquer conteudo poliglota escondido depois do fim da imagem -- uma
imagem que tambem e um ZIP valido nao sobrevive ao round-trip (PRD 5.5).
"""
from __future__ import annotations

import io
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from .io_seguro import write_if_changed

__all__ = [
    "WEBP_CAPA_Q",
    "WEBP_FICHA_LG_Q",
    "WEBP_FICHA_SM_Q",
    "CAPA_LARGURAS",
    "FICHA_ZOOM",
    "FICHA_SM_LARGURA",
    "TAMANHO_MAX",
    "LADO_MIN",
    "LADO_RECOMENDADO",
    "MAX_PIXELS",
    "ImagemInvalida",
    "InfoImagem",
    "Recorte",
    "valida_capa",
    "valida_capa_dados",
    "capa_png_bytes",
    "capa_para_acervo",
    "webp_bytes",
    "gera_capas",
    "gera_ficha",
]

WEBP_CAPA_Q = 82
WEBP_FICHA_LG_Q = 85
WEBP_FICHA_SM_Q = 80
CAPA_LARGURAS = (400, 800)
FICHA_ZOOM = 2.0  # 810x1012.5pt -> 1620x2025 px
FICHA_SM_LARGURA = 600

TAMANHO_MAX = 15 * 1024 * 1024
LADO_MIN = 400
LADO_RECOMENDADO = 800

# Teto de pixels decodificados. 40 milhoes cobre com folga uma foto de 40 MP
# e barra a bomba de descompressao: um PNG de poucos KB pode declarar
# 50.000x50.000, que Pillow tentaria alocar como 7,5 GB de bitmap.
MAX_PIXELS = 40_000_000

# Assinaturas aceitas. A extensao do arquivo e ignorada de proposito -- o que
# vale e o conteudo.
_ASSINATURAS = (
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"\xff\xd8\xff", "JPEG"),
)


class ImagemInvalida(Exception):
    """Imagem recusada. A mensagem ja esta escrita para quem nao e tecnico."""


@dataclass
class InfoImagem:
    largura: int
    altura: int
    formato: str
    quadrada: bool
    avisos: list[str] = field(default_factory=list)


@dataclass
class Recorte:
    """Janela 1:1 sobre a imagem, em pixels da imagem original."""

    x: int
    y: int
    lado: int

    def valida(self, largura: int, altura: int) -> None:
        """As coordenadas vem da interface, entao nao se confia nelas.

        Sao validadas contra as dimensoes reais da imagem: um recorte que
        comece fora ou passe da borda faria o Pillow devolver area preta em
        vez de erro, e a capa publicada sairia com uma faixa vazia.
        """
        for nome, v in (("x", self.x), ("y", self.y), ("lado", self.lado)):
            if not isinstance(v, int) or isinstance(v, bool):
                raise ImagemInvalida(f"As coordenadas do recorte não são válidas (`{nome}`).")
        if self.lado < LADO_MIN:
            raise ImagemInvalida(
                f"O recorte tem {self.lado} px de lado, e o mínimo é {LADO_MIN} px."
            )
        if self.x < 0 or self.y < 0:
            raise ImagemInvalida("As coordenadas do recorte não podem ser negativas.")
        if self.x + self.lado > largura or self.y + self.lado > altura:
            raise ImagemInvalida(
                "O recorte passa da borda da imagem. Ajuste a moldura e tente de novo."
            )


def _valida_tamanho(n_bytes: int) -> None:
    if n_bytes <= 0:
        raise ImagemInvalida("O arquivo está vazio.")
    if n_bytes > TAMANHO_MAX:
        mb = n_bytes / 1024 / 1024
        raise ImagemInvalida(
            f"A imagem tem {mb:.1f} MB e o limite é "
            f"{TAMANHO_MAX // 1024 // 1024} MB. Salve uma versão menor."
        )


def _valida_assinatura(inicio: bytes) -> str:
    for magico, formato in _ASSINATURAS:
        if inicio.startswith(magico):
            return formato
    # WebP e "RIFF....WEBP"
    if inicio[:4] == b"RIFF" and inicio[8:12] == b"WEBP":
        return "WEBP"
    raise ImagemInvalida(
        "Este arquivo não é uma imagem PNG, JPEG ou WebP. Confira se escolheu "
        "o arquivo certo — a extensão do nome não basta."
    )


def _abre_validando(abrir) -> tuple[Image.Image, str]:
    """Abre a imagem com o teto de pixels e a bomba de descompressao ligados.

    Pillow faz duas passadas de proposito: `verify()` confere a estrutura mas
    deixa o arquivo inutilizavel, entao e preciso reabrir e `load()` para
    decodificar de verdade -- e e no `load()` que um arquivo truncado ou
    malicioso falha.
    """
    antes = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            try:
                with abrir() as provisoria:
                    provisoria.verify()
                im = abrir()
                im.load()
                return im, (im.format or "?")
            except ImagemInvalida:
                raise
            except Image.DecompressionBombError as e:
                raise ImagemInvalida(
                    "Esta imagem declara um tamanho absurdo em pixels e foi "
                    "recusada. Salve uma versão normal do arquivo."
                ) from e
            except Image.DecompressionBombWarning as e:
                raise ImagemInvalida(
                    "Esta imagem é grande demais em pixels. Salve uma versão "
                    "com no máximo 40 megapixels."
                ) from e
            except Exception as e:
                raise ImagemInvalida(
                    "Não conseguimos ler esta imagem. Confira se o arquivo "
                    "abre normalmente no visualizador do Windows."
                ) from e
    finally:
        Image.MAX_IMAGE_PIXELS = antes


def _confere_dimensoes(im: Image.Image) -> InfoImagem:
    larg, alt = im.size
    if larg < LADO_MIN or alt < LADO_MIN:
        raise ImagemInvalida(
            f"A imagem tem {larg}×{alt} px, e a capa precisa de pelo menos "
            f"{LADO_MIN}×{LADO_MIN} px."
        )
    avisos = []
    if larg < LADO_RECOMENDADO or alt < LADO_RECOMENDADO:
        avisos.append(
            f"a capa tem {larg}×{alt} px e pode ficar borrada em telas de alta "
            f"resolução; o recomendado é {LADO_RECOMENDADO}×{LADO_RECOMENDADO} px."
        )
    return InfoImagem(
        largura=larg,
        altura=alt,
        formato=im.format or "?",
        quadrada=larg == alt,
        avisos=avisos,
    )


def valida_capa(caminho: Path) -> InfoImagem:
    """Valida uma imagem de capa em disco, na ordem da secao 5.5."""
    caminho = Path(caminho)
    try:
        _valida_tamanho(caminho.stat().st_size)
    except OSError as e:
        raise ImagemInvalida("Não conseguimos abrir este arquivo.") from e

    with caminho.open("rb") as f:
        _valida_assinatura(f.read(16))

    im, _fmt = _abre_validando(lambda: Image.open(caminho))
    try:
        return _confere_dimensoes(im)
    finally:
        im.close()


def valida_capa_dados(dados: bytes) -> InfoImagem:
    """Mesma validacao a partir dos bytes -- o caminho do painel."""
    _valida_tamanho(len(dados))
    _valida_assinatura(dados[:16])
    im, _fmt = _abre_validando(lambda: Image.open(io.BytesIO(dados)))
    try:
        return _confere_dimensoes(im)
    finally:
        im.close()


def capa_png_bytes(
    origem: Path, recorte: Recorte | None = None
) -> tuple[bytes, InfoImagem]:
    """Valida, recorta e reencoda a capa em PNG, **em memoria**.

    Devolver bytes em vez de gravar e deliberado: quem chama pode preparar
    todos os arquivos antes de tocar o acervo, e assim uma validacao que falha
    no meio (um recorte fora da borda, por exemplo) nao deixa pasta pela
    metade no acervo.

    Reencodar nao e so compressao: elimina EXIF (inclusive GPS), perfis de cor
    e qualquer conteudo poliglota depois do fim da imagem -- um arquivo que
    tambem e um ZIP valido nao sobrevive ao round-trip pelos pixels.
    """
    info = valida_capa(origem)

    im, _fmt = _abre_validando(lambda: Image.open(origem))
    try:
        if recorte is not None:
            recorte.valida(info.largura, info.altura)
            im = im.crop(
                (recorte.x, recorte.y, recorte.x + recorte.lado, recorte.y + recorte.lado)
            )
        convertida = im.convert("RGB")
        buf = io.BytesIO()
        # sem `pnginfo`: nenhum metadado do original e copiado
        convertida.save(buf, format="PNG", optimize=True)
        info.largura, info.altura = convertida.size
        info.quadrada = convertida.size[0] == convertida.size[1]
        convertida.close()
    finally:
        im.close()
    return buf.getvalue(), info


def capa_para_acervo(
    origem: Path, destino: Path, recorte: Recorte | None = None
) -> InfoImagem:
    """Grava no acervo a capa reencodada em PNG, sem metadados."""
    dados, info = capa_png_bytes(origem, recorte)
    write_if_changed(destino, dados)
    return info


def webp_bytes(img: Image.Image, qualidade: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=qualidade, method=6)
    return buf.getvalue()


def gera_capas(origem: Path, destino: Path) -> tuple[dict[str, str], list[int], int]:
    """Gera capa-400/800.webp. Nao amplia imagens menores que o alvo."""
    with Image.open(origem) as im:
        im = im.convert("RGB")
        larg, alt = im.size
        saidas: dict[str, str] = {}
        bytes_saida = 0
        for alvo in CAPA_LARGURAS:
            if larg <= alvo:
                novo = im.copy()  # sem upscale
            else:
                h = max(1, round(alt * alvo / larg))
                novo = im.resize((alvo, h), Image.LANCZOS)
            nome = f"capa-{alvo}.webp"
            write_if_changed(destino / nome, webp_bytes(novo, WEBP_CAPA_Q))
            bytes_saida += (destino / nome).stat().st_size
            saidas[f"capa{alvo}"] = nome
            if alvo == CAPA_LARGURAS[-1]:
                dims = list(novo.size)
            novo.close()
    return saidas, dims, bytes_saida


def gera_ficha(pdf_path: Path, destino: Path) -> tuple[dict[str, str], int]:
    """Renderiza a pagina 1 do PDF em 2x -> ficha-1620.webp e ficha-600.webp."""
    import pymupdf

    doc = pymupdf.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(FICHA_ZOOM, FICHA_ZOOM), alpha=False)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()

    bytes_saida = 0
    saidas: dict[str, str] = {}

    nome_lg = f"ficha-{pix.width}.webp"
    write_if_changed(destino / nome_lg, webp_bytes(im, WEBP_FICHA_LG_Q))
    bytes_saida += (destino / nome_lg).stat().st_size
    saidas["ficha1620"] = nome_lg

    h = max(1, round(im.height * FICHA_SM_LARGURA / im.width))
    pequeno = im.resize((FICHA_SM_LARGURA, h), Image.LANCZOS)
    nome_sm = f"ficha-{FICHA_SM_LARGURA}.webp"
    write_if_changed(destino / nome_sm, webp_bytes(pequeno, WEBP_FICHA_SM_Q))
    bytes_saida += (destino / nome_sm).stat().st_size
    saidas["ficha600"] = nome_sm

    pequeno.close()
    im.close()
    return saidas, bytes_saida
