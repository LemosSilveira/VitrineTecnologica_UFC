# -*- coding: utf-8 -*-
"""Quarentena de arquivos recebidos, gravacao no acervo e lixeira.

Tres responsabilidades, na ordem em que um arquivo as atravessa:

1. **Quarentena.** Todo arquivo que entra no painel e gravado primeiro em
   `%LOCALAPPDATA%\\PainelVitrine\\quarentena\\<uuid>\\`, com nome fixo, e so
   entao validado. O nome que veio de fora **nunca** e usado: e dele que
   viriam `..\\..\\Windows`, `CON.pdf` e caminhos de 300 caracteres (T5).
   A interface recebe de volta um token opaco e nunca ve um caminho de disco.

2. **Acervo.** Gravar a patente na pasta de origem, com nomes gerados pelo
   painel no padrao que o build ja reconhece.

3. **Lixeira.** Excluir e mover a pasta para `_lixeira`, que o build ignora.
   Nada e apagado de verdade.
"""
from __future__ import annotations

import base64
import binascii
import re
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from vitrine_core.acervo import (  # noqa: E402
    NOME_SOBREPOSICAO,
    PatenteJsonInvalido,
    arquivos_da_pasta,
    le_patente_json,
    lista_pastas,
)
from vitrine_core.imagens import (  # noqa: E402
    ImagemInvalida,
    Recorte,
    capa_png_bytes,
    valida_capa,
)
from vitrine_core.io_seguro import dentro_de, escreve_atomico  # noqa: E402
from vitrine_core.nomes import (  # noqa: E402
    PASTA_RE,
    NomeInvalido,
    nome_arquivo_patente,
    nome_pasta_patente,
    normaliza_espacos,
)
from vitrine_core.pdf_seguro import PdfInvalido, SEGUNDOS_MAX, TAMANHO_MAX, valida

from .config import pasta_quarentena

__all__ = [
    "NOME_LIXEIRA",
    "TIPOS_DE_ARQUIVO",
    "ErroDeArmazenamento",
    "Quarentena",
    "proximo_id",
    "numeros_usados",
    "pasta_da_patente",
    "grava_patente",
    "move_para_lixeira",
]

NOME_LIXEIRA = "_lixeira"
TIPOS_DE_ARQUIVO = ("pdf", "capa")

# Limite do base64 ANTES de decodificar. Base64 infla ~4/3, e o ceil cobre o
# padding: conferir aqui evita materializar 33 MB de texto na memoria so para
# descobrir que o arquivo passa do limite (PRD 5.4, passo 1).
_FATOR_BASE64 = 4 / 3
_MARGEM_BASE64 = 1024

_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")


class ErroDeArmazenamento(Exception):
    """Falha ao guardar ou mover arquivos. Mensagem pronta para a equipe."""


# --------------------------------------------------------------------------
# Quarentena
# --------------------------------------------------------------------------

@dataclass
class ArquivoEmQuarentena:
    token: str
    tipo: str
    caminho: Path
    tamanho: int
    avisos: list[str]
    # so para imagem
    largura: int = 0
    altura: int = 0
    quadrada: bool = True


class Quarentena:
    """Area de recepcao de arquivos, isolada por sessao.

    Os arquivos ficam fora do repositorio e fora do acervo. Ao abrir, o painel
    limpa o que sobrou de sessoes anteriores -- um arquivo recusado nao tem
    motivo para continuar no disco.
    """

    def __init__(self, raiz: Path | None = None):
        self.raiz = Path(raiz) if raiz else pasta_quarentena()
        self._itens: dict[str, ArquivoEmQuarentena] = {}

    # -- ciclo de vida ----------------------------------------------------

    def limpa_sessoes_antigas(self) -> int:
        """Apaga o conteudo da quarentena. Devolve quantas pastas sairam."""
        if not self.raiz.is_dir():
            return 0
        n = 0
        for p in list(self.raiz.iterdir()):
            if not dentro_de(self.raiz, p):  # pragma: no cover - cinto e suspensorio
                continue
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(
                missing_ok=True
            )
            n += 1
        self._itens.clear()
        return n

    # -- entrada ----------------------------------------------------------

    def recebe_bytes(self, tipo: str, dados: bytes) -> ArquivoEmQuarentena:
        """Grava os bytes na quarentena e valida conforme o tipo."""
        self._confere_tipo(tipo)
        if not isinstance(dados, (bytes, bytearray)) or not dados:
            raise ErroDeArmazenamento("O arquivo chegou vazio.")

        token = uuid.uuid4().hex
        pasta = self.raiz / token
        try:
            pasta.mkdir(parents=True)
        except OSError as e:
            raise ErroDeArmazenamento(
                "Nao conseguimos guardar o arquivo temporariamente. Confira se "
                "ha espaco em disco."
            ) from e

        # Nome FIXO: o nome que veio de fora nunca toca o sistema de arquivos.
        alvo = pasta / ("entrada.pdf" if tipo == "pdf" else "entrada.img")
        alvo.write_bytes(bytes(dados))

        try:
            item = self._valida(token, tipo, alvo)
        except (PdfInvalido, ImagemInvalida) as e:
            shutil.rmtree(pasta, ignore_errors=True)
            raise ErroDeArmazenamento(str(e)) from e
        except Exception:
            shutil.rmtree(pasta, ignore_errors=True)
            raise

        self._itens[token] = item
        return item

    def recebe_base64(self, tipo: str, texto: object) -> ArquivoEmQuarentena:
        """Caminho de arrastar/colar: o arquivo chega como base64.

        O limite de tamanho e conferido no COMPRIMENTO DO TEXTO, antes de
        decodificar.
        """
        self._confere_tipo(tipo)
        if not isinstance(texto, str) or not texto:
            raise ErroDeArmazenamento("O arquivo chegou vazio.")

        teto = int(TAMANHO_MAX * _FATOR_BASE64) + _MARGEM_BASE64
        if len(texto) > teto:
            raise ErroDeArmazenamento(
                f"O arquivo passa do limite de {TAMANHO_MAX // 1024 // 1024} MB."
            )

        # data: URL ("data:application/pdf;base64,....") tambem e aceita
        if texto.startswith("data:"):
            _, _, texto = texto.partition(",")
        try:
            dados = base64.b64decode(texto, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ErroDeArmazenamento("Nao conseguimos ler o arquivo enviado.") from e
        return self.recebe_bytes(tipo, dados)

    def recebe_do_disco(self, tipo: str, caminho: object) -> ArquivoEmQuarentena:
        """Caminho do seletor nativo: copia para a quarentena antes de validar.

        Copiar em vez de validar no lugar e deliberado: o arquivo original
        pode estar num pendrive que sai no meio do processo, ou ser trocado
        entre a validacao e a gravacao.
        """
        self._confere_tipo(tipo)
        if not isinstance(caminho, str) or not caminho.strip():
            raise ErroDeArmazenamento("Nenhum arquivo foi escolhido.")
        origem = Path(caminho)
        if not origem.is_file():
            raise ErroDeArmazenamento("O arquivo escolhido nao existe mais.")
        try:
            tamanho = origem.stat().st_size
        except OSError as e:
            raise ErroDeArmazenamento("Nao conseguimos abrir o arquivo escolhido.") from e
        if tamanho > TAMANHO_MAX:
            raise ErroDeArmazenamento(
                f"O arquivo tem {tamanho / 1024 / 1024:.1f} MB e o limite e "
                f"{TAMANHO_MAX // 1024 // 1024} MB."
            )
        return self.recebe_bytes(tipo, origem.read_bytes())

    # -- consulta ---------------------------------------------------------

    def obtem(self, token: object) -> ArquivoEmQuarentena:
        """Resolve um token. O token e a UNICA forma de referenciar arquivo."""
        if not isinstance(token, str) or not _TOKEN_RE.match(token):
            raise ErroDeArmazenamento("Este arquivo nao esta mais disponivel.")
        item = self._itens.get(token)
        if item is None or not item.caminho.is_file():
            raise ErroDeArmazenamento(
                "Este arquivo nao esta mais disponivel. Escolha o arquivo de novo."
            )
        return item

    def descarta(self, token: object) -> None:
        if not isinstance(token, str) or not _TOKEN_RE.match(token):
            return
        item = self._itens.pop(token, None)
        if item is not None:
            shutil.rmtree(item.caminho.parent, ignore_errors=True)

    # -- interno ----------------------------------------------------------

    @staticmethod
    def _confere_tipo(tipo: object) -> None:
        if tipo not in TIPOS_DE_ARQUIVO:
            raise ErroDeArmazenamento(f"Tipo de arquivo desconhecido: {tipo!r}")

    @staticmethod
    def _valida(token: str, tipo: str, alvo: Path) -> ArquivoEmQuarentena:
        if tipo == "pdf":
            info = valida(alvo, segundos=SEGUNDOS_MAX)
            return ArquivoEmQuarentena(
                token=token,
                tipo=tipo,
                caminho=alvo,
                tamanho=alvo.stat().st_size,
                avisos=list(info.avisos),
            )
        img = valida_capa(alvo)
        return ArquivoEmQuarentena(
            token=token,
            tipo=tipo,
            caminho=alvo,
            tamanho=alvo.stat().st_size,
            avisos=list(img.avisos),
            largura=img.largura,
            altura=img.altura,
            quadrada=img.quadrada,
        )


# --------------------------------------------------------------------------
# Acervo: consulta
# --------------------------------------------------------------------------

def _id_da_pasta(pasta: Path) -> int | None:
    m = PASTA_RE.match(normaliza_espacos(pasta.name))
    return int(m.group("id")) if m else None


def _pastas_da_lixeira(acervo: Path) -> list[Path]:
    lixeira = Path(acervo) / NOME_LIXEIRA
    if not lixeira.is_dir():
        return []
    return [d for d in lixeira.iterdir() if d.is_dir()]


def _numero_da_pasta(nome: str) -> str | None:
    m = PASTA_RE.match(normaliza_espacos(nome))
    if not m:
        return None
    return f"BR {m.group('esp')} {m.group('ano')} {m.group('seq')}-{m.group('dv')}"


def proximo_id(acervo: Path) -> int:
    """Maior ID ja usado + 1, **contando a lixeira**.

    IDs nunca sao reaproveitados: `patente.html?id=N` e uma URL que pode estar
    num e-mail, num slide ou indexada. Reaproveitar o 47 faria a URL antiga
    apontar para outra tecnologia (PRD 4.5).
    """
    maior = 0
    for pasta in lista_pastas(Path(acervo)):
        pid = _id_da_pasta(pasta)
        if pid:
            maior = max(maior, pid)
    for pasta in _pastas_da_lixeira(acervo):
        # na lixeira o nome ganha um sufixo de data: "12. BR ...__20260929-120000"
        m = re.match(r"^(\d+)", pasta.name)
        if m:
            maior = max(maior, int(m.group(1)))
    return maior + 1


def numeros_usados(acervo: Path) -> dict[str, int]:
    """Numero canonico -> id, incluindo a lixeira.

    A lixeira conta porque o numero do pedido e unico no INPI: duas pastas com
    o mesmo numero seriam a mesma patente cadastrada duas vezes.
    """
    usados: dict[str, int] = {}
    for pasta in lista_pastas(Path(acervo)):
        numero = _numero_da_pasta(pasta.name)
        pid = _id_da_pasta(pasta)
        if numero and pid:
            usados.setdefault(numero, pid)
    for pasta in _pastas_da_lixeira(acervo):
        base = pasta.name.split("__")[0]
        numero = _numero_da_pasta(base)
        m = re.match(r"^(\d+)", pasta.name)
        if numero and m:
            usados.setdefault(numero, int(m.group(1)))
    return usados


def pasta_da_patente(acervo: Path, patente_id: int) -> Path | None:
    for pasta in lista_pastas(Path(acervo)):
        if _id_da_pasta(pasta) == int(patente_id):
            return pasta
    return None


# --------------------------------------------------------------------------
# Acervo: gravacao
# --------------------------------------------------------------------------

def _grava_sobreposicao(pasta: Path, campos: dict, oculta: bool, usuario: str) -> None:
    conteudo = {
        "versao": 1,
        "oculta": bool(oculta),
        "campos": campos,
        "atualizadoEm": datetime.now().astimezone().isoformat(timespec="seconds"),
        "atualizadoPor": usuario,
    }
    import json

    escreve_atomico(
        pasta / NOME_SOBREPOSICAO,
        (json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def grava_patente(
    acervo: Path,
    *,
    patente_id: int,
    numero: str,
    categoria: str,
    titulo: str,
    campos: dict,
    oculta: bool = False,
    usuario: str = "?",
    pdf: Path | None = None,
    capa: Path | None = None,
    recorte: Recorte | None = None,
) -> Path:
    """Cria ou atualiza a pasta da patente no acervo.

    Grava **todos** os campos confirmados no `patente.json`, e nao so os que
    a pessoa mudou: assim a edicao humana prevalece sobre uma futura releitura
    do PDF, que poderia extrair o texto de outra forma depois de uma mudanca no
    parser (PRD 9.1, passo 7).

    Os arquivos antigos, quando trocados, nao sao apagados aqui -- quem chama
    ja criou o backup da pasta inteira.
    """
    acervo = Path(acervo)
    existente = pasta_da_patente(acervo, patente_id)
    nova = existente or (acervo / nome_pasta_patente(patente_id, numero))

    if not dentro_de(acervo, nova):  # pragma: no cover - cinto e suspensorio
        raise ErroDeArmazenamento("caminho de destino fora do acervo")

    # --- preparar TUDO que pode falhar, antes de tocar o acervo ---
    #
    # A ordem importa. Gravar primeiro e validar depois deixaria a pasta da
    # patente criada e vazia quando, por exemplo, o recorte da capa fosse
    # invalido -- e o build passaria a acusar "sem imagem de capa", travando a
    # vitrine inteira ate alguem apagar a pasta a mao. O `salvar` promete que
    # nada foi alterado, e isso vale tambem para o caminho de erro.
    try:
        a_gravar: list[tuple[str, bytes, set[str]]] = []
        if capa is not None:
            dados, _info = capa_png_bytes(Path(capa), recorte)
            a_gravar.append(
                (
                    nome_arquivo_patente(patente_id, categoria, numero, titulo, ".png", nova),
                    dados,
                    {".png", ".jpg", ".jpeg"},
                )
            )
        if pdf is not None:
            # o PDF vai para o acervo como veio: o original e a fonte da
            # verdade, e a higienizacao acontece na publicacao
            a_gravar.append(
                (
                    nome_arquivo_patente(patente_id, categoria, numero, titulo, ".pdf", nova),
                    Path(pdf).read_bytes(),
                    {".pdf"},
                )
            )
    except (NomeInvalido, ImagemInvalida) as e:
        raise ErroDeArmazenamento(str(e)) from e
    except OSError as e:
        raise ErroDeArmazenamento("Nao conseguimos ler os arquivos enviados.") from e

    # --- a partir daqui, escrever ---
    criamos_a_pasta = existente is None
    try:
        nova.mkdir(parents=True, exist_ok=True)
        for nome, dados, substitui in a_gravar:
            _remove_antigos(nova, substitui)
            escreve_atomico(nova / nome, dados)
        _grava_sobreposicao(nova, campos, oculta, usuario)
    except OSError as e:
        # a pasta que NOS criamos sai; uma que ja existia fica (o backup de
        # quem chamou e que responde por ela)
        if criamos_a_pasta:
            shutil.rmtree(nova, ignore_errors=True)
        raise ErroDeArmazenamento(
            "Nao conseguimos gravar os arquivos desta patente no acervo."
        ) from e
    return nova


def _remove_antigos(pasta: Path, extensoes: set[str]) -> None:
    """Tira da pasta os arquivos daquelas extensoes.

    Trocar a capa sem isso deixaria duas imagens na pasta, e o build escolhe a
    primeira em ordem alfabetica -- a antiga poderia continuar sendo publicada.
    """
    for f in sorted(pasta.iterdir()):
        if f.is_file() and f.suffix.lower() in extensoes:
            f.unlink()


def alterna_oculta(acervo: Path, patente_id: int, oculta: bool, usuario: str = "?") -> Path:
    """Liga ou desliga `oculta` mantendo o resto do patente.json."""
    pasta = pasta_da_patente(Path(acervo), patente_id)
    if pasta is None:
        raise ErroDeArmazenamento(f"Nao encontrei a patente {patente_id} no acervo.")
    try:
        atual = le_patente_json(pasta)
    except PatenteJsonInvalido as e:
        raise ErroDeArmazenamento(
            f"O patente.json desta patente esta invalido ({e}). Corrija antes "
            "de ocultar ou mostrar."
        ) from e
    campos = atual.campos if atual else {}
    _grava_sobreposicao(pasta, campos, bool(oculta), usuario)
    return pasta


def move_para_lixeira(acervo: Path, patente_id: int) -> Path:
    """Move a pasta da patente para `_lixeira`. Nada e apagado.

    O nome ganha a data, para que excluir duas vezes a mesma patente (depois de
    recadastra-la) nao sobrescreva o registro anterior.
    """
    acervo = Path(acervo)
    pasta = pasta_da_patente(acervo, patente_id)
    if pasta is None:
        raise ErroDeArmazenamento(f"Nao encontrei a patente {patente_id} no acervo.")

    lixeira = acervo / NOME_LIXEIRA
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = lixeira / f"{pasta.name}__{marca}"

    # Duas exclusoes no mesmo segundo cairiam no mesmo nome, e `shutil.move`
    # moveria a segunda pasta PARA DENTRO da primeira, em silencio. Acontece ao
    # recadastrar e excluir de novo em sequencia.
    n = 2
    while destino.exists():
        destino = lixeira / f"{pasta.name}__{marca}-{n}"
        n += 1

    if not dentro_de(acervo, destino):  # pragma: no cover
        raise ErroDeArmazenamento("caminho de destino fora do acervo")

    try:
        lixeira.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pasta), str(destino))
    except OSError as e:
        raise ErroDeArmazenamento(
            "Nao conseguimos mover esta patente para a lixeira. Confira se "
            "algum arquivo dela esta aberto."
        ) from e
    return destino
