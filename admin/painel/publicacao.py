# -*- coding: utf-8 -*-
"""Pacote de publicacao: um .zip com **somente** os arquivos publicos (PRD 5.9).

O pacote e montado por **lista de permissoes**, nunca por lista de exclusoes.
A diferenca importa: com uma lista de exclusoes, qualquer arquivo novo no
repositorio entra no pacote por padrao, e o painel, o acervo, os backups e o
`.git` estariam a um `git add` de distancia de ir para a web (T8). Com lista
de permissoes, um arquivo novo fica de fora ate alguem decidir o contrario.

Antes de montar, o painel confere que a vitrine esta consistente: build sem
erro, todos os arquivos referenciados presentes e nenhuma pasta orfa em
`assets/patentes/`. Publicar uma vitrine com imagem faltando da erro 404 na
cara do visitante.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from vitrine_core.io_seguro import dentro_de  # noqa: E402

from .config import pasta_pacotes

__all__ = [
    "ARQUIVOS_FIXOS",
    "PADROES_PERMITIDOS",
    "ARQUIVOS_DA_PATENTE",
    "Checagem",
    "Pacote",
    "ErroDePublicacao",
    "le_patentes_js",
    "confere",
    "gera",
]


class ErroDePublicacao(Exception):
    """O pacote nao pode ser gerado. Mensagem pronta para a equipe."""


# --------------------------------------------------------------------------
# A lista de permissoes
# --------------------------------------------------------------------------

# Arquivos da raiz, um por um. Nada de glob aqui: a raiz e onde aparecem os
# arquivos soltos criados por engano (foi o caso do `19,47,52`, achado A3).
ARQUIVOS_FIXOS = (
    "index.html",
    "patente.html",
    "404.html",
    ".htaccess",
)

PADROES_PERMITIDOS = (
    "css/*.css",
    "js/*.js",
    "js/data/patentes.js",
    "assets/fonts/*.woff2",
    "assets/img/*.svg",
    "assets/img/*.png",
)

# Dentro de assets/patentes/<slug>/ so estes cinco nomes entram. Um
# `original.pdf` ou um `rascunho.psd` que aparecesse ali fica de fora.
ARQUIVOS_DA_PATENTE = (
    "capa-400.webp",
    "capa-800.webp",
    "ficha-600.webp",
    "ficha-1620.webp",
    "ficha.pdf",
)


# --------------------------------------------------------------------------
# Leitura do patentes.js
# --------------------------------------------------------------------------

def le_patentes_js(site: Path) -> list[dict]:
    """Le `window.PATENTES` como dados.

    O arquivo e JavaScript, nao JSON: as chaves nao tem aspas e ha virgula
    sobrando no fim das listas. Converter e mais simples (e nao exige um motor
    de JS) do que manter um segundo formato so para o painel ler.
    """
    arq = Path(site) / "js" / "data" / "patentes.js"
    if not arq.is_file():
        raise ErroDePublicacao(
            "Nao encontrei o arquivo de dados da vitrine. Rode a atualizacao "
            "da vitrine antes de gerar o pacote."
        )
    texto = arq.read_text(encoding="utf-8")
    marca = "window.PATENTES = "
    try:
        inicio = texto.index(marca) + len(marca)
        fim = texto.index("\n];", inicio) + 2
    except ValueError as e:
        raise ErroDePublicacao(
            "O arquivo de dados da vitrine esta em formato inesperado. Rode a "
            "atualizacao da vitrine."
        ) from e

    corpo = texto[inicio:fim]
    corpo = re.sub(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):", r'\1"\2":', corpo, flags=re.M)
    corpo = re.sub(r",(\s*[\]}])", r"\1", corpo)
    try:
        dados = json.loads(corpo)
    except json.JSONDecodeError as e:
        raise ErroDePublicacao(
            "Nao conseguimos ler o arquivo de dados da vitrine."
        ) from e
    if not isinstance(dados, list):
        raise ErroDePublicacao("O arquivo de dados da vitrine esta inesperado.")
    return dados


# --------------------------------------------------------------------------
# Checagens
# --------------------------------------------------------------------------

@dataclass
class Checagem:
    """Um item do checklist da tela Publicar."""

    chave: str
    titulo: str
    ok: bool
    detalhe: str = ""


@dataclass
class Resultado:
    checagens: list[Checagem] = field(default_factory=list)
    arquivos: list[str] = field(default_factory=list)
    patentes: int = 0

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checagens)


def _relatorio_sem_erros(site: Path) -> Checagem:
    arq = Path(site) / "scripts" / "build_report.md"
    if not arq.is_file():
        return Checagem(
            "build", "A vitrine foi gerada", False,
            "Nao encontrei o relatorio do build. Rode a atualizacao da vitrine.",
        )
    texto = arq.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"\*\*Erros:\*\*\s*(\d+)", texto)
    if not m:
        return Checagem(
            "build", "A vitrine foi gerada sem erros", False,
            "Nao consegui ler a contagem de erros no relatorio.",
        )
    n = int(m.group(1))
    return Checagem(
        "build",
        "A vitrine foi gerada sem erros",
        n == 0,
        "" if n == 0 else f"O ultimo build terminou com {n} erro(s).",
    )


def _arquivos_referenciados(site: Path, patentes: list[dict]) -> tuple[set[str], list[str]]:
    """Caminhos que o patentes.js cita, e quais deles nao existem no disco."""
    citados: set[str] = set()
    for p in patentes:
        imagens = p.get("imagens") or {}
        for chave in ("capa400", "capa800", "ficha600", "ficha1620"):
            v = imagens.get(chave)
            if v:
                citados.add(v)
        if p.get("pdf"):
            citados.add(p["pdf"])

    faltando = [c for c in sorted(citados) if not (Path(site) / c).is_file()]
    return citados, faltando


def _pastas_orfas(site: Path, patentes: list[dict]) -> list[str]:
    """Pastas em assets/patentes/ que nao pertencem a nenhuma patente.

    Sobram quando uma patente e oculta, vai para a lixeira ou muda de titulo.
    Publicar com elas deixaria o PDF de uma patente oculta acessivel por URL
    direta -- exatamente o que ocultar deveria impedir.
    """
    base = Path(site) / "assets" / "patentes"
    if not base.is_dir():
        return []
    validos = {p.get("slug") for p in patentes}
    return sorted(d.name for d in base.iterdir() if d.is_dir() and d.name not in validos)


def confere(site: Path) -> Resultado:
    """Monta o checklist da tela Publicar e a lista de arquivos do pacote."""
    site = Path(site)
    res = Resultado()

    res.checagens.append(_relatorio_sem_erros(site))

    try:
        patentes = le_patentes_js(site)
    except ErroDePublicacao as e:
        res.checagens.append(Checagem("dados", "Os dados da vitrine estao legiveis", False, str(e)))
        return res

    res.patentes = len(patentes)
    res.checagens.append(
        Checagem("dados", f"{len(patentes)} patentes na vitrine", len(patentes) > 0,
                 "" if patentes else "A vitrine esta vazia.")
    )

    _citados, faltando = _arquivos_referenciados(site, patentes)
    res.checagens.append(
        Checagem(
            "arquivos",
            "Todos os arquivos da vitrine estao presentes",
            not faltando,
            "" if not faltando else
            f"{len(faltando)} arquivo(s) faltando, comecando por `{faltando[0]}`.",
        )
    )

    orfas = _pastas_orfas(site, patentes)
    res.checagens.append(
        Checagem(
            "orfas",
            "Nenhuma pasta de patente fora da vitrine",
            not orfas,
            "" if not orfas else
            f"{len(orfas)} pasta(s) sobrando em assets/patentes: {', '.join(orfas[:3])}."
            " Rode a atualizacao da vitrine.",
        )
    )

    res.arquivos = _monta_lista(site, patentes)
    return res


def _monta_lista(site: Path, patentes: list[dict]) -> list[str]:
    """Os caminhos relativos que entram no zip, em ordem estavel."""
    site = Path(site)
    escolhidos: list[str] = []

    for nome in ARQUIVOS_FIXOS:
        if (site / nome).is_file():
            escolhidos.append(nome)

    for padrao in PADROES_PERMITIDOS:
        for p in sorted(site.glob(padrao)):
            if p.is_file() and dentro_de(site, p):
                escolhidos.append(p.relative_to(site).as_posix())

    for p in patentes:
        slug = p.get("slug")
        if not slug:
            continue
        pasta = site / "assets" / "patentes" / slug
        if not dentro_de(site, pasta):  # pragma: no cover - cinto e suspensorio
            continue
        for nome in ARQUIVOS_DA_PATENTE:
            if (pasta / nome).is_file():
                escolhidos.append(f"assets/patentes/{slug}/{nome}")

    # sorted+dict.fromkeys: sem duplicata (js/*.js pega o data/ tambem?) e
    # ordem estavel, para que dois pacotes do mesmo estado saiam iguais
    return sorted(dict.fromkeys(escolhidos))


# --------------------------------------------------------------------------
# Geracao do pacote
# --------------------------------------------------------------------------

@dataclass
class Pacote:
    caminho: Path
    sha256: str
    arquivos: int
    patentes: int
    tamanho: int

    @property
    def tamanho_legivel(self) -> str:
        return f"{self.tamanho / 1024 / 1024:.1f} MB"


def gera(site: Path, destino: Path | None = None) -> Pacote:
    """Monta o .zip. Recusa se alguma checagem falhar."""
    site = Path(site)
    res = confere(site)
    if not res.ok:
        problemas = [c.detalhe or c.titulo for c in res.checagens if not c.ok]
        raise ErroDePublicacao(
            "O pacote nao foi gerado porque a vitrine tem pendencias: "
            + " ".join(problemas)
        )
    if not res.arquivos:
        raise ErroDePublicacao("Nao ha nada para publicar.")

    base = Path(destino) if destino else pasta_pacotes()
    base.mkdir(parents=True, exist_ok=True)
    nome = f"vitrine-patentes_{datetime.now().strftime('%Y-%m-%d_%H%M')}.zip"
    alvo = base / nome

    n = 2
    while alvo.exists():
        alvo = base / nome.replace(".zip", f"-{n}.zip")
        n += 1

    try:
        with zipfile.ZipFile(alvo, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for rel in res.arquivos:
                # data fixa nas entradas: dois pacotes do mesmo estado da
                # vitrine saem com o mesmo conteudo, e o SHA-256 vira algo
                # que a equipe pode comparar
                info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, (site / rel).read_bytes())
    except OSError as e:
        alvo.unlink(missing_ok=True)
        raise ErroDePublicacao(
            "Nao conseguimos gravar o pacote. Confira se ha espaco em disco."
        ) from e

    h = hashlib.sha256()
    with alvo.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)

    return Pacote(
        caminho=alvo,
        sha256=h.hexdigest(),
        arquivos=len(res.arquivos),
        patentes=res.patentes,
        tamanho=alvo.stat().st_size,
    )
