# -*- coding: utf-8 -*-
"""Configuracao do painel e onde cada coisa mora no computador.

Nada do que o painel grava vai para dentro do repositorio da vitrine: a
configuracao, os backups e a auditoria ficam em `%APPDATA%`, e o que e
descartavel (quarentena, pacotes, trava) em `%LOCALAPPDATA%`. Assim
atualizar o programa nunca apaga o historico, e o repositorio nunca ganha um
arquivo que iria ao ar por engano.

As duas pastas do projeto -- site e acervo -- so entram aqui pelo seletor
nativo do Windows. A interface nao tem campo de texto para caminho, e este
modulo valida o que recebe como se viesse de fora (PRD 5.7).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from vitrine_core.io_seguro import escreve_atomico  # noqa: E402
from vitrine_core.nomes import PASTA_RE, normaliza_espacos  # noqa: E402

__all__ = [
    "VERSAO_CONFIG",
    "NOME_APP",
    "Config",
    "ErroDeConfig",
    "pasta_dados",
    "pasta_local",
    "pasta_backups",
    "pasta_quarentena",
    "pasta_pacotes",
    "caminho_config",
    "caminho_auditoria",
    "caminho_log",
    "caminho_trava",
    "valida_pasta_site",
    "valida_pasta_acervo",
    "valida_par_de_pastas",
    "carrega",
    "salva",
]

VERSAO_CONFIG = 1
NOME_APP = "PainelVitrine"

# Arquivos que provam que a pasta escolhida e a vitrine, e nao uma pasta
# parecida. Os tres juntos sao especificos o bastante para nao dar falso
# positivo em nenhuma pasta de documentos.
MARCAS_DO_SITE = (
    "index.html",
    "js/data/patentes.js",
    "scripts/build_patentes.py",
)


class ErroDeConfig(Exception):
    """Configuracao invalida. A mensagem e para a equipe, nao para o log."""


# --------------------------------------------------------------------------
# Onde as coisas ficam
# --------------------------------------------------------------------------

def _base(variavel: str, alternativa: str) -> Path:
    """%APPDATA% / %LOCALAPPDATA%, com alternativa para rodar fora do Windows.

    Os testes e um eventual uso em Linux caem na alternativa; o executavel
    sempre tera as variaveis.
    """
    bruto = os.environ.get(variavel)
    if bruto:
        return Path(bruto)
    return Path.home() / alternativa


def pasta_dados() -> Path:
    """`%APPDATA%\\PainelVitrine` -- o que NAO pode ser perdido."""
    return _base("APPDATA", ".config") / NOME_APP


def pasta_local() -> Path:
    """`%LOCALAPPDATA%\\PainelVitrine` -- o que pode ser apagado sem perda."""
    return _base("LOCALAPPDATA", ".cache") / NOME_APP


def pasta_backups() -> Path:
    return pasta_dados() / "backups"


def pasta_quarentena() -> Path:
    return pasta_local() / "quarentena"


def pasta_pacotes() -> Path:
    return pasta_local() / "pacotes"


def caminho_config() -> Path:
    return pasta_dados() / "config.json"


def caminho_auditoria() -> Path:
    return pasta_dados() / "auditoria.log"


def caminho_log() -> Path:
    """Log tecnico, com stack trace. Nunca vai para a interface."""
    return pasta_local() / "painel.log"


def caminho_trava() -> Path:
    return pasta_local() / "painel.lock"


# --------------------------------------------------------------------------
# Validacao das pastas do projeto
# --------------------------------------------------------------------------

def _resolve(caminho: object, rotulo: str) -> Path:
    if not isinstance(caminho, str) or not caminho.strip():
        raise ErroDeConfig(f"Nenhuma pasta foi escolhida para {rotulo}.")
    if len(caminho) > 4096:
        raise ErroDeConfig(f"O caminho de {rotulo} e longo demais.")
    try:
        p = Path(normaliza_espacos(caminho)).expanduser().resolve()
    except (OSError, ValueError) as e:
        raise ErroDeConfig(f"O caminho de {rotulo} nao e valido.") from e
    if not p.is_dir():
        raise ErroDeConfig(f"A pasta de {rotulo} nao existe: {p}")
    return p


def valida_pasta_site(caminho: object) -> Path:
    """A pasta precisa ser a vitrine, com os tres arquivos que a identificam."""
    p = _resolve(caminho, "o site")
    faltando = [m for m in MARCAS_DO_SITE if not (p / m).is_file()]
    if faltando:
        raise ErroDeConfig(
            "Esta pasta nao parece ser a vitrine. Escolha a pasta que contem "
            "o arquivo index.html. "
            f"(nao encontrei: {', '.join(faltando)})"
        )
    return p


def valida_pasta_acervo(caminho: object) -> Path:
    """A pasta precisa ter ao menos uma subpasta no padrao do acervo."""
    p = _resolve(caminho, "o acervo")
    try:
        tem = any(
            d.is_dir()
            and not d.name.startswith(("_", "."))
            and PASTA_RE.match(normaliza_espacos(d.name))
            for d in p.iterdir()
        )
    except OSError as e:
        raise ErroDeConfig(f"Nao conseguimos ler a pasta do acervo: {p}") from e
    if not tem:
        raise ErroDeConfig(
            "Esta pasta nao parece ser o acervo das fichas. Escolha a pasta "
            "que contem as subpastas no padrao `1. BR 10 2014 030019 8`."
        )
    return p


def valida_par_de_pastas(site: object, acervo: object) -> tuple[Path, Path]:
    """Valida as duas e garante que uma nao esta dentro da outra.

    Se o acervo estivesse dentro do site, os PDFs e as imagens originais --
    centenas de MB, com os metadados de quem os gerou -- entrariam na pasta
    publicada. Se o site estivesse dentro do acervo, o build varreria a
    propria saida.
    """
    # A igualdade e conferida ANTES das validacoes especificas: quem escolheu a
    # mesma pasta nos dois passos precisa ouvir isso, e nao "esta pasta nao
    # parece ser o acervo", que manda a pessoa procurar o problema errado.
    if isinstance(site, str) and isinstance(acervo, str) and site.strip() and acervo.strip():
        try:
            if Path(site).expanduser().resolve() == Path(acervo).expanduser().resolve():
                raise ErroDeConfig("O site e o acervo nao podem ser a mesma pasta.")
        except (OSError, ValueError):
            pass  # caminho invalido: as validacoes abaixo dao a mensagem certa

    s = valida_pasta_site(site)
    a = valida_pasta_acervo(acervo)
    if s in a.parents:
        raise ErroDeConfig(
            "O acervo nao pode ficar dentro da pasta do site: as fichas "
            "originais iriam para o ar junto com a vitrine."
        )
    if a in s.parents:
        raise ErroDeConfig("A pasta do site nao pode ficar dentro do acervo.")
    return s, a


# --------------------------------------------------------------------------
# config.json
# --------------------------------------------------------------------------

@dataclass
class Config:
    pastaSite: str = ""
    pastaAcervo: str = ""
    versao: int = VERSAO_CONFIG
    # Texto mostrado na tela Publicar, depois de gerar o pacote. Fica em
    # configuracao porque depende de como a UFC publica o site (PRD P5).
    proximoPasso: str = ""

    @property
    def site(self) -> Path:
        return Path(self.pastaSite)

    @property
    def acervo(self) -> Path:
        return Path(self.pastaAcervo)

    def completa(self) -> bool:
        """True se as duas pastas estao preenchidas E continuam validas.

        Conferir de novo a cada abertura e necessario: a pasta pode ter sido
        movida ou renomeada desde a ultima sessao.
        """
        if not self.pastaSite or not self.pastaAcervo:
            return False
        try:
            valida_par_de_pastas(self.pastaSite, self.pastaAcervo)
        except ErroDeConfig:
            return False
        return True


def carrega(caminho: Path | None = None) -> Config:
    """Le o config.json. Arquivo ausente ou corrompido devolve config vazia.

    Nao levanta excecao de proposito: sem configuracao valida o painel abre na
    tela de primeira execucao, que e o comportamento certo tanto na estreia
    quanto depois de um arquivo corrompido.
    """
    alvo = caminho or caminho_config()
    if not alvo.is_file():
        return Config()
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return Config()
    if not isinstance(dados, dict):
        return Config()

    conhecidos = {f for f in Config.__dataclass_fields__}
    return Config(**{k: v for k, v in dados.items() if k in conhecidos})


def salva(cfg: Config, caminho: Path | None = None) -> None:
    """Grava o config.json de forma atomica."""
    alvo = caminho or caminho_config()
    cfg.versao = VERSAO_CONFIG
    texto = json.dumps(asdict(cfg), ensure_ascii=False, indent=2) + "\n"
    escreve_atomico(alvo, texto.encode("utf-8"))
