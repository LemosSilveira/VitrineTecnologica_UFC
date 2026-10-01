# -*- coding: utf-8 -*-
"""Leitura do acervo -- as pastas originais das fichas.

O acervo e a **fonte da verdade** e e somente leitura para o build: nada
aqui renomeia, move ou apaga um original. Quem escreve no acervo e so o
painel.

Tambem vive aqui o carregamento de `dados/categorias.json`. O mapa de areas
tecnologicas era uma constante no codigo do build (achado A5 do PRD): com
ele em arquivo, o painel consegue acrescentar uma area sem que ninguem
precise editar Python.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .nomes import limpa_texto

__all__ = [
    "IMG_EXTS",
    "TIPOS",
    "LIMITES",
    "NOME_SOBREPOSICAO",
    "ErroDeConfiguracao",
    "PatenteJsonInvalido",
    "ArquivosDaPasta",
    "Sobreposicao",
    "lista_pastas",
    "arquivos_da_pasta",
    "caminho_categorias_padrao",
    "carrega_categorias",
    "le_patente_json",
]

IMG_EXTS = {".png", ".jpg", ".jpeg"}

NOME_SOBREPOSICAO = "patente.json"

# Limites dos campos (PRD secao 8). Ficam aqui porque o esquema do
# patente.json precisa deles; a validacao do formulario do painel (Fase 3)
# importa daqui em vez de repetir os numeros -- duas listas de limites
# divergiriam no primeiro ajuste.
LIMITES = {
    "titulo": (10, 160),
    "oQueE": (40, 900),
    "problema": (0, 900),
    "exemploDeUso": (0, 900),
    "beneficio": (0, 900),
    "diferencial": (3, 200),
    "diferenciais_max": 8,
    "trl_min": 1,
    "trl_max": 9,
}

# Especie no numero do INPI: BR 10 = invencao, BR 20 = modelo de utilidade.
TIPOS = {
    "10": {"sigla": "PI", "nome": "Patente de Invenção"},
    "20": {"sigla": "MU", "nome": "Modelo de Utilidade"},
}

_PREFIXO_NUMERICO = re.compile(r"^(\d+)")


class ErroDeConfiguracao(Exception):
    """Configuracao do projeto invalida (categorias.json ausente ou torto)."""


class PatenteJsonInvalido(Exception):
    """`patente.json` fora do esquema. A patente fica de fora da vitrine."""


@dataclass
class ArquivosDaPasta:
    """O que ha dentro de uma pasta de patente, ja classificado."""

    pdfs: list[Path]
    imagens: list[Path]
    outros: list[Path]


@dataclass
class Sobreposicao:
    """O que o `patente.json` diz sobre uma patente.

    `campos` traz **so** o que a equipe editou pelo painel. O que nao estiver
    aqui continua vindo do PDF ou do nome do arquivo -- e por isso que o
    merge e campo a campo e nao um `dict.update` do objeto inteiro.
    """

    oculta: bool = False
    campos: dict = field(default_factory=dict)


def lista_pastas(src: Path) -> list[Path]:
    """Subpastas do acervo, em ordem de ID.

    Pastas que comecam com `_` ou `.` ficam de fora. E assim que a lixeira
    (`_lixeira`) desaparece da vitrine sem que nada seja apagado de verdade:
    excluir uma patente no painel e mover a pasta para la (PRD 4.6).

    Pastas sem prefixo numerico vao para o fim, onde o build as reporta como
    erro de nome -- em vez de quebrarem a ordenacao.
    """

    def ordem(p: Path) -> int:
        m = _PREFIXO_NUMERICO.match(p.name)
        return int(m.group(1)) if m else 10**6

    return sorted(
        (
            d
            for d in src.iterdir()
            if d.is_dir() and not d.name.startswith(("_", "."))
        ),
        key=ordem,
    )


def arquivos_da_pasta(pasta: Path) -> ArquivosDaPasta:
    """Separa PDFs, imagens e o resto.

    Ordem estavel: o build precisa escolher sempre o mesmo arquivo quando a
    pasta tem mais de um PDF ou mais de uma imagem, senao a saida mudaria
    entre execucoes.
    """
    pdfs: list[Path] = []
    imagens: list[Path] = []
    outros: list[Path] = []
    for f in sorted(pasta.iterdir()):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext == ".pdf":
            pdfs.append(f)
        elif ext in IMG_EXTS:
            imagens.append(f)
        else:
            outros.append(f)
    return ArquivosDaPasta(pdfs=pdfs, imagens=imagens, outros=outros)


# --------------------------------------------------------------------------
# patente.json -- a sobreposicao editada pelo painel (PRD 4.3)
# --------------------------------------------------------------------------

_CHAVES_RAIZ = {"versao", "oculta", "campos", "atualizadoEm", "atualizadoPor"}
_CHAVES_CAMPOS = {"titulo", "categoria", "secoes", "trl"}
_CHAVES_SECOES = {"oQueE", "problema", "exemploDeUso", "diferenciais", "beneficio"}
_CHAVES_TRL = {"min", "max", "estimado"}

_SECOES_TEXTO = ("oQueE", "problema", "exemploDeUso", "beneficio")


def _recusa_chaves_desconhecidas(obj: dict, permitidas: set[str], onde: str) -> None:
    """Campo desconhecido e erro, nao algo a ignorar em silencio.

    Um `titluo` com erro de digitacao passaria despercebido para sempre: a
    equipe veria a correcao salva no arquivo e a vitrine continuaria com o
    titulo velho, sem ninguem entender por que.
    """
    sobrando = sorted(set(obj) - permitidas)
    if sobrando:
        raise PatenteJsonInvalido(
            f"{onde}: campo desconhecido {', '.join(repr(s) for s in sobrando)}. "
            f"Esperados: {', '.join(sorted(permitidas))}."
        )


def _texto(valor: object, campo: str, minimo: int, maximo: int) -> str:
    if not isinstance(valor, str):
        raise PatenteJsonInvalido(f"`{campo}` deveria ser texto, e veio {type(valor).__name__}.")
    limpo = limpa_texto(valor)
    if len(limpo) < minimo:
        raise PatenteJsonInvalido(
            f"`{campo}` tem {len(limpo)} caracteres e o minimo e {minimo}."
        )
    if len(limpo) > maximo:
        raise PatenteJsonInvalido(
            f"`{campo}` tem {len(limpo)} caracteres e o maximo e {maximo}."
        )
    return limpo


def _valida_trl(valor: object) -> dict:
    if not isinstance(valor, dict):
        raise PatenteJsonInvalido("`trl` deveria ser um objeto com min, max e estimado.")
    _recusa_chaves_desconhecidas(valor, _CHAVES_TRL, "trl")

    lo, hi = valor.get("min"), valor.get("max")
    for nome, v in (("trl.min", lo), ("trl.max", hi)):
        # bool e subclasse de int em Python: `True` passaria por um inteiro
        if not isinstance(v, int) or isinstance(v, bool):
            raise PatenteJsonInvalido(f"`{nome}` deveria ser um numero inteiro.")
        if not LIMITES["trl_min"] <= v <= LIMITES["trl_max"]:
            raise PatenteJsonInvalido(
                f"`{nome}` e {v}; o TRL vai de {LIMITES['trl_min']} a {LIMITES['trl_max']}."
            )
    if lo > hi:
        raise PatenteJsonInvalido(f"`trl.min` ({lo}) e maior que `trl.max` ({hi}).")

    estimado = valor.get("estimado", False)
    if not isinstance(estimado, bool):
        raise PatenteJsonInvalido("`trl.estimado` deveria ser true ou false.")

    # `texto` e sempre recalculado pelo build a partir de min/max/estimado,
    # nunca lido daqui (PRD 4.3).
    return {"min": lo, "max": hi, "estimado": estimado}


def _valida_secoes(valor: object) -> dict:
    if not isinstance(valor, dict):
        raise PatenteJsonInvalido("`secoes` deveria ser um objeto.")
    _recusa_chaves_desconhecidas(valor, _CHAVES_SECOES, "secoes")

    out: dict = {}
    for campo in _SECOES_TEXTO:
        if campo not in valor:
            continue
        if valor[campo] is None:
            out[campo] = None
            continue
        minimo, maximo = LIMITES[campo]
        out[campo] = _texto(valor[campo], f"secoes.{campo}", minimo, maximo)

    if "diferenciais" in valor:
        itens = valor["diferenciais"]
        if itens is None:
            out["diferenciais"] = None
        else:
            if not isinstance(itens, list):
                raise PatenteJsonInvalido("`secoes.diferenciais` deveria ser uma lista.")
            if len(itens) > LIMITES["diferenciais_max"]:
                raise PatenteJsonInvalido(
                    f"`secoes.diferenciais` tem {len(itens)} itens; o maximo e "
                    f"{LIMITES['diferenciais_max']}."
                )
            lo, hi = LIMITES["diferencial"]
            limpos = [
                _texto(it, f"secoes.diferenciais[{i}]", lo, hi)
                for i, it in enumerate(itens)
            ]
            out["diferenciais"] = limpos or None
    return out


def _valida_campos(valor: object, categorias: dict[str, str] | None) -> dict:
    if not isinstance(valor, dict):
        raise PatenteJsonInvalido("`campos` deveria ser um objeto.")
    _recusa_chaves_desconhecidas(valor, _CHAVES_CAMPOS, "campos")

    out: dict = {}
    if "titulo" in valor:
        lo, hi = LIMITES["titulo"]
        out["titulo"] = _texto(valor["titulo"], "campos.titulo", lo, hi)

    if "categoria" in valor:
        cat = limpa_texto(valor["categoria"])
        if not isinstance(valor["categoria"], str) or not cat:
            raise PatenteJsonInvalido("`campos.categoria` deveria ser texto nao vazio.")
        if categorias is not None and cat not in set(categorias.values()):
            raise PatenteJsonInvalido(
                f"area tecnologica `{cat}` nao existe em dados/categorias.json."
            )
        out["categoria"] = cat

    if "secoes" in valor:
        out["secoes"] = _valida_secoes(valor["secoes"])
    if "trl" in valor:
        out["trl"] = None if valor["trl"] is None else _valida_trl(valor["trl"])
    return out


def le_patente_json(
    pasta: Path, categorias: dict[str, str] | None = None
) -> Sobreposicao | None:
    """Le e valida o `patente.json` de uma pasta do acervo.

    Devolve `None` quando o arquivo nao existe -- o caso das 60 patentes
    atuais, que so ganham um quando alguem as edita pelo painel.

    Levanta `PatenteJsonInvalido` em vez de ignorar o arquivo torto: uma
    sobreposicao que nao pode ser aplicada precisa aparecer no relatorio,
    senao a equipe salva uma correcao e ela some sem aviso.
    """
    caminho = pasta / NOME_SOBREPOSICAO
    if not caminho.is_file():
        return None

    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise PatenteJsonInvalido(f"nao e um JSON valido: {e}") from e

    if not isinstance(dados, dict):
        raise PatenteJsonInvalido("o conteudo deveria ser um objeto JSON.")
    _recusa_chaves_desconhecidas(dados, _CHAVES_RAIZ, NOME_SOBREPOSICAO)

    # Exige inteiro, nao so igualdade: em Python `1.0 == 1` e `True == 1` sao
    # verdadeiros, e o resto do esquema e estrito quanto a tipo.
    versao = dados.get("versao")
    if not isinstance(versao, int) or isinstance(versao, bool) or versao != 1:
        raise PatenteJsonInvalido(f"versao {versao!r} desconhecida (esperada: 1).")

    oculta = dados.get("oculta", False)
    if not isinstance(oculta, bool):
        raise PatenteJsonInvalido("`oculta` deveria ser true ou false.")

    campos = _valida_campos(dados.get("campos", {}), categorias)
    return Sobreposicao(oculta=oculta, campos=campos)


def caminho_categorias_padrao() -> Path:
    """`dados/categorias.json` na raiz do repositorio.

    Derivado da posicao deste arquivo (`scripts/vitrine_core/acervo.py`), e
    nao do diretorio atual, para que o build funcione de qualquer pasta.
    """
    return Path(__file__).resolve().parents[2] / "dados" / "categorias.json"


def carrega_categorias(caminho: Path | None = None) -> dict[str, str]:
    """Le o mapa de areas tecnologicas.

    Devolve {chave normalizada: nome exibido}. Erra alto e claro em vez de
    seguir com um mapa vazio, porque um mapa vazio faria o build reprovar as
    60 patentes de uma vez com uma mensagem que nao explicaria a causa.
    """
    caminho = caminho or caminho_categorias_padrao()
    if not caminho.is_file():
        raise ErroDeConfiguracao(
            f"nao encontrei o mapa de areas em `{caminho}`. "
            "Ele acompanha o repositorio; restaure-o do git."
        )

    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ErroDeConfiguracao(f"`{caminho}` nao e um JSON valido: {e}") from e

    if not isinstance(dados, dict):
        raise ErroDeConfiguracao(f"`{caminho}`: o conteudo deveria ser um objeto JSON.")
    if dados.get("versao") != 1:
        raise ErroDeConfiguracao(
            f"`{caminho}`: versao {dados.get('versao')!r} desconhecida (esperada: 1)."
        )

    mapa = dados.get("mapa")
    if not isinstance(mapa, dict) or not mapa:
        raise ErroDeConfiguracao(
            f"`{caminho}`: o campo `mapa` deveria ser um objeto nao vazio."
        )
    for k, v in mapa.items():
        if not isinstance(k, str) or not isinstance(v, str) or not k or not v:
            raise ErroDeConfiguracao(
                f"`{caminho}`: a entrada {k!r} -> {v!r} deveria ser texto para texto."
            )

    return mapa
