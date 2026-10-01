# -*- coding: utf-8 -*-
"""A superficie que o JavaScript da janela consegue chamar (PRD 5.3).

O pywebview expoe **todo metodo publico** da classe passada em `js_api`. Isso
faz desta classe a fronteira de seguranca do painel, e por isso ela tem
apenas os metodos da tabela 5.3 -- nem um a mais. Qualquer ajudante vira
funcao de outro modulo ou metodo com `_` na frente. `tests/seguranca` falha se
aparecer um metodo publico novo.

Duas regras valem em todos eles:

* **Nada que venha da interface e confiavel.** Tipo, tamanho, formato e
  permissao sao conferidos aqui, como se o argumento viesse de um atacante --
  porque pode vir: o JS da janela e alteravel pelo DevTools (T11).
* **Nenhum detalhe tecnico volta para a interface.** Excecao inesperada vira
  "Algo deu errado. Nada foi alterado." com um codigo; o stack trace vai para
  o log tecnico, que fica fora da janela.
"""
from __future__ import annotations

import hashlib
import logging
import logging.handlers
import os
import subprocess
import sys
import threading
import uuid
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from vitrine_core.acervo import (  # noqa: E402
    ErroDeConfiguracao,
    PatenteJsonInvalido,
    carrega_categorias,
    le_patente_json,
)
from vitrine_core.build import roda_build  # noqa: E402
from vitrine_core.extracao import ler_ficha as core_ler_ficha  # noqa: E402
from vitrine_core.extracao import ler_texto as core_ler_texto  # noqa: E402
from vitrine_core.imagens import ImagemInvalida, Recorte  # noqa: E402
from vitrine_core.nomes import limpa_texto  # noqa: E402

from . import armazenamento, auditoria, backup, config, previa, publicacao, validacao
from .armazenamento import ErroDeArmazenamento, Quarentena
from .backup import ErroDeBackup
from .config import ErroDeConfig
from .publicacao import ErroDePublicacao

__all__ = ["Api", "LINKS", "PASTAS_ABRIVEIS"]

# Nenhuma URL livre: a interface pede um link pela CHAVE, e a lista de
# destinos e esta. Com URL livre, um texto vindo de uma ficha poderia abrir
# qualquer coisa no navegador da pessoa (PRD 5.3).
LINKS = {
    "ufcinova": "https://ufcinova.sitios.sti.ufc.br",
    "ufc": "https://www.ufc.br",
}

PASTAS_ABRIVEIS = ("pacotes", "acervo", "site")

_TAMANHO_TEXTO_MAX = 20_000


def _log() -> logging.Logger:
    """Log tecnico, rotativo, fora da janela (PRD 5.8)."""
    lg = logging.getLogger("painel")
    if lg.handlers:
        return lg
    lg.setLevel(logging.INFO)
    try:
        caminho = config.caminho_log()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        h = logging.handlers.RotatingFileHandler(
            caminho, maxBytes=1024 * 1024, backupCount=5, encoding="utf-8"
        )
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        lg.addHandler(h)
    except OSError:  # pragma: no cover - sem disco, segue sem log
        lg.addHandler(logging.NullHandler())
    return lg


def _ok(dados=None) -> dict:
    return {"ok": True, "dados": dados}


def _erro(codigo: str, mensagem: str, campos: dict | None = None) -> dict:
    resposta = {"ok": False, "erro": {"codigo": codigo, "mensagem": mensagem}}
    if campos:
        resposta["erro"]["campos"] = campos
    return resposta


# Excecoes que JA trazem mensagem escrita para a equipe: podem ir para a
# interface como estao. Qualquer outra vira erro generico.
_ESPERADAS = (
    ErroDeConfig,
    ErroDeArmazenamento,
    ErroDeBackup,
    ErroDePublicacao,
    ErroDeConfiguracao,
    PatenteJsonInvalido,
    ImagemInvalida,
)

_CODIGOS = {
    ErroDeConfig: "E-CONF",
    ErroDeArmazenamento: "E-ARQ",
    ErroDeBackup: "E-BKP",
    ErroDePublicacao: "E-PUB",
    ErroDeConfiguracao: "E-CAT",
    PatenteJsonInvalido: "E-JSON",
    ImagemInvalida: "E-IMG",
}


def _protegido(fn):
    """Envolve um metodo publico: nenhuma excecao escapa para a interface."""

    def dentro(self, *a, **kw):
        try:
            return fn(self, *a, **kw)
        except _ESPERADAS as e:
            codigo = next(
                (c for tipo, c in _CODIGOS.items() if isinstance(e, tipo)), "E-GERAL"
            )
            _log().warning("%s: %s", fn.__name__, e)
            return _erro(codigo, str(e))
        except Exception:
            # Codigo curto para a pessoa citar ao pedir ajuda; o detalhe fica
            # no log tecnico, nunca na janela.
            ref = uuid.uuid4().hex[:6].upper()
            _log().exception("falha inesperada em %s (ref %s)", fn.__name__, ref)
            return _erro(
                f"E-{ref}",
                "Algo deu errado e nada foi alterado. Se continuar, avise "
                f"informando o código E-{ref}.",
            )

    dentro.__name__ = fn.__name__
    dentro.__doc__ = fn.__doc__
    return dentro


class _DialogosIndisponiveis:
    """Usado quando nao ha janela (testes, linha de comando)."""

    def escolher_pasta(self, titulo: str) -> str | None:
        raise ErroDeArmazenamento(
            "O seletor de pastas so funciona com a janela do painel aberta."
        )

    def escolher_arquivo(self, titulo: str, filtros) -> str | None:
        raise ErroDeArmazenamento(
            "O seletor de arquivos so funciona com a janela do painel aberta."
        )


class Api:
    """Instancia passada ao pywebview em `js_api`.

    Os dialogos nativos entram por injecao (`dialogos`) em vez de serem
    chamados direto: assim esta classe nao depende do pywebview e pode ser
    testada por inteiro, inclusive os caminhos de erro.
    """

    def __init__(self, dialogos=None, quarentena: Quarentena | None = None):
        self._dialogos = dialogos or _DialogosIndisponiveis()
        self._cfg = config.carrega()
        self._quarentena = quarentena or Quarentena()
        self._quarentena.limpa_sessoes_antigas()
        self._ultimo_build = None
        self._servidor_local = None

    # ======================================================================
    # Estado e configuracao
    # ======================================================================

    @_protegido
    def estado(self) -> dict:
        """Se ha configuracao valida, as contagens e a versao."""
        cfg = self._cfg
        pronto = cfg.completa()
        dados = {
            "configurado": pronto,
            "versao": self._versao(),
            "usuario": auditoria.quem(),
            "pastaSite": cfg.pastaSite,
            "pastaAcervo": cfg.pastaAcervo,
            "proximoPasso": cfg.proximoPasso,
            "naVitrine": 0,
            "ocultas": 0,
            "naLixeira": 0,
            "areas": 0,
            "listaAreas": [],
        }
        if pronto:
            resumo = self._resumo_do_acervo()
            dados.update(resumo)
            # a tela "Nova patente" precisa da lista para o select de area, e
            # nao tem id para chamar `obter()` (que ja devolve a lista, mas so
            # faz sentido para quem esta editando uma patente existente)
            dados["listaAreas"] = sorted(set(self._categorias().values()))
        return _ok(dados)

    @_protegido
    def configurar(self, pasta_site: object, pasta_acervo: object) -> dict:
        """Valida e guarda as duas pastas do projeto."""
        site, acervo = config.valida_par_de_pastas(pasta_site, pasta_acervo)
        self._cfg.pastaSite = str(site)
        self._cfg.pastaAcervo = str(acervo)
        config.salva(self._cfg)
        auditoria.registra("configurar", resumo="pastaSite, pastaAcervo")
        return self.estado()

    @_protegido
    def escolher_pasta(self, tipo: object) -> dict:
        """Abre o seletor nativo e devolve o caminho escolhido.

        A interface nao tem campo de texto para caminho: digitar um caminho
        nunca e uma opcao.
        """
        if tipo not in ("site", "acervo"):
            return _erro("E-ARG", "Tipo de pasta desconhecido.")
        titulo = (
            "Escolha a pasta da vitrine (a que tem o index.html)"
            if tipo == "site"
            else "Escolha a pasta do acervo (as fichas originais)"
        )
        escolhido = self._dialogos.escolher_pasta(titulo)
        if not escolhido:
            return _ok({"cancelado": True})
        # valida na hora: a pessoa recebe o retorno no passo, nao ao salvar
        pasta = (
            config.valida_pasta_site(escolhido)
            if tipo == "site"
            else config.valida_pasta_acervo(escolhido)
        )
        return _ok({"caminho": str(pasta), "cancelado": False})

    # ======================================================================
    # Listagem e leitura
    # ======================================================================

    @_protegido
    def listar(self) -> dict:
        """As patentes do acervo, com o status de cada uma."""
        self._exige_config()
        return _ok({"patentes": self._lista_patentes()})

    @_protegido
    def obter(self, id: object) -> dict:
        """Dados completos de uma patente, para edicao."""
        self._exige_config()
        pid = self._id_valido(id)
        pasta = armazenamento.pasta_da_patente(self._cfg.acervo, pid)
        if pasta is None:
            return _erro("E-404", f"Nao encontrei a patente {pid} no acervo.")

        from vitrine_core.acervo import arquivos_da_pasta
        from vitrine_core.nomes import PASTA_RE, normaliza_espacos

        m = PASTA_RE.match(normaliza_espacos(pasta.name))
        arqs = arquivos_da_pasta(pasta)
        sobre = le_patente_json(pasta, self._categorias())

        campos = dict(sobre.campos) if sobre else {}
        # o que a equipe ainda nao editou vem da ficha, para o formulario
        # abrir preenchido em vez de vazio
        if arqs.pdfs and not campos.get("titulo"):
            lido = core_ler_ficha(arqs.pdfs[0], self._categorias())
            campos.setdefault("titulo", lido["titulo"]["valor"])
            campos.setdefault("categoria", lido["categoria"]["valor"])
            campos.setdefault(
                "secoes",
                {k: v["valor"] for k, v in lido["secoes"].items()},
            )
            if lido["trl"]["valor"]:
                t = lido["trl"]["valor"]
                campos.setdefault(
                    "trl", {"min": t["min"], "max": t["max"], "estimado": t["estimado"]}
                )

        return _ok(
            {
                "id": pid,
                "numero": f"BR {m.group('esp')} {m.group('ano')} {m.group('seq')}-{m.group('dv')}",
                "oculta": bool(sobre.oculta) if sobre else False,
                "campos": campos,
                "temPdf": bool(arqs.pdfs),
                "temCapa": bool(arqs.imagens),
                "areas": sorted(set(self._categorias().values())),
            }
        )

    # ======================================================================
    # Arquivos
    # ======================================================================

    @_protegido
    def escolher_arquivo(self, tipo: object) -> dict:
        """Seletor nativo -> quarentena -> validacao -> token."""
        if tipo not in armazenamento.TIPOS_DE_ARQUIVO:
            return _erro("E-ARG", "Tipo de arquivo desconhecido.")
        filtros = (
            ("Ficha tecnica em PDF (*.pdf)", "*.pdf")
            if tipo == "pdf"
            else ("Imagem (*.png;*.jpg;*.jpeg;*.webp)", "*.png;*.jpg;*.jpeg;*.webp")
        )
        escolhido = self._dialogos.escolher_arquivo(
            "Escolha a ficha em PDF" if tipo == "pdf" else "Escolha a imagem de capa",
            filtros,
        )
        if not escolhido:
            return _ok({"cancelado": True})
        item = self._quarentena.recebe_do_disco(tipo, escolhido)
        return _ok(self._resumo_do_arquivo(item))

    @_protegido
    def receber_arquivo(self, tipo: object, nome: object, base64_: object = None) -> dict:
        """Arrastar/colar: o arquivo chega em base64.

        `nome` e recebido **so para mostrar na tela**. Ele nunca toca o sistema
        de arquivos: os nomes no acervo sao gerados pelo painel (PRD 5.7).
        """
        if tipo not in armazenamento.TIPOS_DE_ARQUIVO:
            return _erro("E-ARG", "Tipo de arquivo desconhecido.")
        item = self._quarentena.recebe_base64(tipo, base64_)
        resumo = self._resumo_do_arquivo(item)
        resumo["nomeOriginal"] = limpa_texto(nome)[:120]
        return _ok(resumo)

    @_protegido
    def ler_ficha(self, token_pdf: object) -> dict:
        """Extrai os campos da ficha em PDF, com a origem de cada um."""
        item = self._quarentena.obtem(token_pdf)
        if item.tipo != "pdf":
            return _erro("E-ARG", "Este arquivo nao e uma ficha em PDF.")
        campos = core_ler_ficha(item.caminho, self._categorias())
        campos["avisos"] = item.avisos
        return _ok(campos)

    @_protegido
    def ler_texto_ficha(self, texto: object) -> dict:
        """Mesma extracao a partir de um texto colado."""
        if not isinstance(texto, str):
            return _erro("E-ARG", "Nao recebemos o texto.")
        if len(texto) > _TAMANHO_TEXTO_MAX:
            return _erro(
                "E-ARG",
                f"O texto colado tem {len(texto)} caracteres e o limite e "
                f"{_TAMANHO_TEXTO_MAX}. Cole so o conteudo da ficha.",
            )
        return _ok(core_ler_texto(texto))

    # ======================================================================
    # Previa e gravacao
    # ======================================================================

    @_protegido
    def previa(
        self,
        dados: object,
        token_capa: object = None,
        token_pdf: object = None,
    ) -> dict:
        """Devolve o objeto no formato de PATENTES[i], para a previa real.

        As imagens vem como `data:` URL, geradas em memoria: nada e escrito no
        site antes de salvar.
        """
        self._exige_config()
        r = self._valida(dados, token_capa, token_pdf, id_editando=self._id_opcional(dados))
        item_capa = self._quarentena.obtem(token_capa) if token_capa else None
        item_pdf = self._quarentena.obtem(token_pdf) if token_pdf else None

        objeto = previa.monta(
            campos=r.dados,
            patente_id=self._id_opcional(dados) or armazenamento.proximo_id(self._cfg.acervo),
            capa=item_capa.caminho if item_capa else self._capa_atual(dados),
            pdf=item_pdf.caminho if item_pdf else self._pdf_atual(dados),
            recorte=self._recorte(dados),
        )
        return _ok(
            {
                "patente": objeto,
                "erros": r.erros,
                "avisos": r.avisos,
                "valido": r.ok,
            }
        )

    @_protegido
    def salvar(
        self,
        dados: object,
        token_capa: object = None,
        token_pdf: object = None,
        id: object = None,
    ) -> dict:
        """Valida, faz backup, grava no acervo e roda o build."""
        self._exige_config()
        pid_editando = self._id_valido(id) if id is not None else None

        r = self._valida(dados, token_capa, token_pdf, id_editando=pid_editando)
        if not r.ok:
            return _erro(
                "E-VALID",
                "Confira os campos destacados: alguns dados ainda precisam de "
                "ajuste.",
                r.erros,
            )

        nova = pid_editando is None
        pid = pid_editando or armazenamento.proximo_id(self._cfg.acervo)
        numero = r.dados.get("numero") or self._numero_da_patente(pid)

        pasta_atual = (
            armazenamento.pasta_da_patente(self._cfg.acervo, pid) if not nova else None
        )
        backup.cria(
            "salvar",
            patente_id=pid,
            pasta_patente=pasta_atual,
            patentes_js=self._cfg.site / "js" / "data" / "patentes.js",
        )

        item_capa = self._quarentena.obtem(token_capa) if token_capa else None
        item_pdf = self._quarentena.obtem(token_pdf) if token_pdf else None

        oculta = bool((dados or {}).get("oculta", False)) if isinstance(dados, dict) else False
        armazenamento.grava_patente(
            self._cfg.acervo,
            patente_id=pid,
            numero=numero,
            categoria=r.dados["categoria"],
            titulo=r.dados["titulo"],
            campos=self._campos_para_json(r.dados),
            oculta=oculta,
            usuario=auditoria.quem(),
            pdf=item_pdf.caminho if item_pdf else None,
            capa=item_capa.caminho if item_capa else None,
            recorte=self._recorte(dados),
        )

        relatorio = self._build()
        auditoria.registra(
            "salvar" if not nova else "criar",
            id=pid,
            numero=numero,
            resumo=", ".join(sorted(r.dados)),
            sha256=self._hashes(item_pdf, item_capa),
            resultado="ok" if not relatorio["erros"] else "erro",
        )
        for token in (token_capa, token_pdf):
            self._quarentena.descarta(token)

        return _ok({"id": pid, "novo": nova, "build": relatorio})

    @_protegido
    def alternar_oculta(self, id: object, oculta: object) -> dict:
        """Tira a patente da vitrine, ou devolve."""
        self._exige_config()
        pid = self._id_valido(id)
        if not isinstance(oculta, bool):
            return _erro("E-ARG", "O valor de visibilidade deveria ser sim ou nao.")

        pasta = armazenamento.pasta_da_patente(self._cfg.acervo, pid)
        backup.cria(
            "ocultar" if oculta else "mostrar",
            patente_id=pid,
            pasta_patente=pasta,
            patentes_js=self._cfg.site / "js" / "data" / "patentes.js",
        )
        armazenamento.alterna_oculta(self._cfg.acervo, pid, oculta, auditoria.quem())
        relatorio = self._build()
        auditoria.registra(
            "ocultar" if oculta else "mostrar",
            id=pid,
            resultado="ok" if not relatorio["erros"] else "erro",
        )
        return _ok({"id": pid, "oculta": oculta, "build": relatorio})

    @_protegido
    def excluir(self, id: object, confirmacao: object) -> dict:
        """Move a patente para a lixeira. Exige digitar o numero do pedido."""
        self._exige_config()
        pid = self._id_valido(id)
        esperado = self._numero_da_patente(pid)
        if validacao.normaliza_numero_do_formulario(confirmacao) != esperado:
            return _erro(
                "E-CONFIRMA",
                f"Para mover esta patente para a lixeira, digite o número do "
                f"pedido: {esperado}",
            )

        pasta = armazenamento.pasta_da_patente(self._cfg.acervo, pid)
        backup.cria(
            "excluir",
            patente_id=pid,
            pasta_patente=pasta,
            patentes_js=self._cfg.site / "js" / "data" / "patentes.js",
        )
        destino = armazenamento.move_para_lixeira(self._cfg.acervo, pid)
        relatorio = self._build()
        auditoria.registra(
            "excluir",
            id=pid,
            numero=esperado,
            resumo=f"movida para {destino.parent.name}",
            resultado="ok" if not relatorio["erros"] else "erro",
        )
        return _ok({"id": pid, "build": relatorio})

    @_protegido
    def rodar_build(self) -> dict:
        """Regera a vitrine e devolve o relatorio."""
        self._exige_config()
        relatorio = self._build()
        auditoria.registra(
            "rodar_build",
            resumo=f"{relatorio['patentes']} patentes",
            resultado="ok" if not relatorio["erros"] else "erro",
        )
        return _ok(relatorio)

    # ======================================================================
    # Historico e publicacao
    # ======================================================================

    @_protegido
    def historico(self, pagina: object = 1) -> dict:
        """Uma pagina do historico, com os backups disponiveis."""
        try:
            n = int(pagina)
        except (TypeError, ValueError):
            n = 1
        dados = auditoria.le(n)
        dados["backups"] = [
            {
                "id": b.id,
                "acao": b.acao,
                "patenteId": b.patente_id,
                "quando": b.quando,
                "usuario": b.usuario,
                "descricao": b.descricao(),
            }
            for b in backup.lista()
        ]
        return _ok(dados)

    @_protegido
    def restaurar(self, id_backup: object, confirmacao: object) -> dict:
        """Volta ao estado de um backup. Exige confirmacao por texto."""
        self._exige_config()
        if not isinstance(id_backup, str):
            return _erro("E-ARG", "Ponto do historico invalido.")
        if limpa_texto(confirmacao).upper() != "RESTAURAR":
            return _erro(
                "E-CONFIRMA",
                "Para restaurar este ponto, digite RESTAURAR para confirmar.",
            )

        # backup do estado ATUAL antes de sobrescrever: sem isso, restaurar por
        # engano nao teria volta
        backup.cria(
            "antes-de-restaurar",
            patentes_js=self._cfg.site / "js" / "data" / "patentes.js",
        )
        b = backup.restaura(id_backup, acervo=self._cfg.acervo, site=self._cfg.site)
        relatorio = self._build()
        auditoria.registra(
            "restaurar",
            id=b.patente_id,
            resumo=f"backup {b.id}",
            resultado="ok" if not relatorio["erros"] else "erro",
        )
        return _ok({"backup": b.id, "build": relatorio})

    @_protegido
    def gerar_pacote(self) -> dict:
        """Checagens + .zip so com os arquivos publicos + SHA-256."""
        self._exige_config()
        conferencia = publicacao.confere(self._cfg.site)
        if not conferencia.ok:
            return _ok(
                {
                    "gerado": False,
                    "checagens": [vars(c) for c in conferencia.checagens],
                }
            )
        p = publicacao.gera(self._cfg.site)
        auditoria.registra(
            "gerar_pacote",
            resumo=f"{p.patentes} patentes, {p.arquivos} arquivos",
            sha256={"pacote": p.sha256},
        )
        return _ok(
            {
                "gerado": True,
                "checagens": [vars(c) for c in conferencia.checagens],
                "nome": p.caminho.name,
                "sha256": p.sha256,
                "arquivos": p.arquivos,
                "patentes": p.patentes,
                "tamanho": p.tamanho_legivel,
                "proximoPasso": self._cfg.proximoPasso,
            }
        )

    # ======================================================================
    # Atalhos para fora da janela
    # ======================================================================

    @_protegido
    def abrir_pasta(self, tipo: object) -> dict:
        """Abre uma das tres pastas no Explorer. Nenhum outro destino."""
        if tipo not in PASTAS_ABRIVEIS:
            return _erro("E-ARG", "Esta pasta nao pode ser aberta pelo painel.")
        alvo = {
            "pacotes": config.pasta_pacotes(),
            "acervo": self._cfg.acervo if self._cfg.pastaAcervo else None,
            "site": self._cfg.site if self._cfg.pastaSite else None,
        }[tipo]
        if alvo is None:
            return _erro("E-CONF", "Esta pasta ainda nao foi configurada.")
        alvo.mkdir(parents=True, exist_ok=True)
        self._abre_no_sistema(alvo)
        return _ok({"caminho": str(alvo)})

    @_protegido
    def abrir_link(self, chave: object) -> dict:
        """Abre um link conhecido no navegador padrao. Nunca uma URL livre."""
        if chave == "site_local":
            return self.ver_site_local()
        url = LINKS.get(chave) if isinstance(chave, str) else None
        if not url:
            return _erro("E-ARG", "Este link nao esta disponivel.")
        webbrowser.open(url)
        return _ok({"url": url})

    @_protegido
    def ver_site_local(self) -> dict:
        """Sobe um servidor somente leitura da pasta do site e abre no navegador.

        Preso em 127.0.0.1, em porta sorteada pelo sistema. E como a equipe
        confere a vitrine inteira antes de publicar, sem precisar de servidor
        nenhum instalado.
        """
        self._exige_config()
        if self._servidor_local is None:
            self._servidor_local = _ServidorLocal(self._cfg.site)
            self._servidor_local.inicia()
        url = self._servidor_local.url
        webbrowser.open(url)
        return _ok({"url": url})

    # ======================================================================
    # Auxiliares -- fora da superficie exposta ao JavaScript
    # ======================================================================

    def _versao(self) -> str:
        from vitrine_core import VERSAO

        return VERSAO

    def _exige_config(self) -> None:
        if not self._cfg.completa():
            raise ErroDeConfig(
                "As pastas do site e do acervo ainda nao foram configuradas."
            )

    def _categorias(self) -> dict:
        return carrega_categorias()

    def _id_valido(self, bruto: object) -> int:
        if isinstance(bruto, bool) or not isinstance(bruto, (int, str)):
            raise ErroDeArmazenamento("Identificador de patente invalido.")
        try:
            pid = int(str(bruto).strip())
        except ValueError as e:
            raise ErroDeArmazenamento("Identificador de patente invalido.") from e
        if not 1 <= pid <= 1_000_000:
            raise ErroDeArmazenamento("Identificador de patente invalido.")
        return pid

    @staticmethod
    def _id_opcional(dados: object) -> int | None:
        if isinstance(dados, dict) and dados.get("id") is not None:
            try:
                return int(dados["id"])
            except (TypeError, ValueError):
                return None
        return None

    def _numero_da_patente(self, pid: int) -> str:
        from vitrine_core.nomes import PASTA_RE, normaliza_espacos

        pasta = armazenamento.pasta_da_patente(self._cfg.acervo, pid)
        if pasta is None:
            raise ErroDeArmazenamento(f"Nao encontrei a patente {pid} no acervo.")
        m = PASTA_RE.match(normaliza_espacos(pasta.name))
        return f"BR {m.group('esp')} {m.group('ano')} {m.group('seq')}-{m.group('dv')}"

    def _valida(self, dados, token_capa, token_pdf, id_editando):
        tem_capa = bool(token_capa) or self._capa_atual(dados) is not None
        tem_pdf = bool(token_pdf) or self._pdf_atual(dados) is not None
        return validacao.valida(
            dados,
            categorias=self._categorias(),
            numeros_existentes=armazenamento.numeros_usados(self._cfg.acervo),
            id_editando=id_editando,
            tem_capa=tem_capa,
            tem_pdf=tem_pdf,
        )

    def _arquivo_atual(self, dados, quais: set[str]):
        """Arquivo que a patente em edicao ja tem no acervo."""
        pid = self._id_opcional(dados)
        if pid is None:
            return None
        pasta = armazenamento.pasta_da_patente(self._cfg.acervo, pid)
        if pasta is None:
            return None
        from vitrine_core.acervo import arquivos_da_pasta

        arqs = arquivos_da_pasta(pasta)
        lista = arqs.pdfs if quais == {".pdf"} else arqs.imagens
        return lista[0] if lista else None

    def _capa_atual(self, dados):
        return self._arquivo_atual(dados, {".png", ".jpg", ".jpeg"})

    def _pdf_atual(self, dados):
        return self._arquivo_atual(dados, {".pdf"})

    @staticmethod
    def _recorte(dados: object) -> Recorte | None:
        if not isinstance(dados, dict):
            return None
        bruto = dados.get("recorte")
        if not isinstance(bruto, dict):
            return None
        try:
            return Recorte(
                x=int(bruto.get("x", 0)),
                y=int(bruto.get("y", 0)),
                lado=int(bruto.get("lado", 0)),
            )
        except (TypeError, ValueError) as e:
            raise ImagemInvalida("As coordenadas do recorte nao sao validas.") from e

    @staticmethod
    def _campos_para_json(validos: dict) -> dict:
        """So o que o esquema do patente.json aceita (PRD 4.3)."""
        permitidos = ("titulo", "categoria", "secoes", "trl")
        return {k: v for k, v in validos.items() if k in permitidos}

    @staticmethod
    def _resumo_do_arquivo(item) -> dict:
        dados = {
            "token": item.token,
            "tipo": item.tipo,
            "tamanho": item.tamanho,
            "avisos": item.avisos,
        }
        if item.tipo == "capa":
            dados.update(
                {
                    "largura": item.largura,
                    "altura": item.altura,
                    "quadrada": item.quadrada,
                    "precisaRecorte": not item.quadrada,
                }
            )
        return dados

    @staticmethod
    def _hashes(item_pdf, item_capa) -> dict:
        """SHA-256 do que entrou, para o historico (PRD 5.8)."""
        saida = {}
        for chave, item in (("pdf", item_pdf), ("capa", item_capa)):
            if item is None:
                continue
            h = hashlib.sha256(item.caminho.read_bytes()).hexdigest()
            saida[chave] = h
        return saida

    def _build(self) -> dict:
        res = roda_build(self._cfg.acervo, self._cfg.site)
        self._ultimo_build = res
        return {
            "patentes": len(res.patentes),
            "erros": list(res.erros),
            "avisos": list(res.avisos),
            "ignorados": list(res.ignorados),
            "ocultas": list(res.ocultas),
            "assetsRemovidos": list(res.assets_removidos),
            "vitrineAtualizada": res.js_mudou,
        }

    def _resumo_do_acervo(self) -> dict:
        patentes = self._lista_patentes()
        return {
            "naVitrine": sum(1 for p in patentes if not p["oculta"]),
            "ocultas": sum(1 for p in patentes if p["oculta"]),
            "naLixeira": len(armazenamento._pastas_da_lixeira(self._cfg.acervo)),
            "areas": len(set(self._categorias().values())),
        }

    def _lista_patentes(self) -> list[dict]:
        from vitrine_core.acervo import arquivos_da_pasta, lista_pastas
        from vitrine_core.nomes import PASTA_RE, normaliza_espacos

        saida = []
        for pasta in lista_pastas(self._cfg.acervo):
            m = PASTA_RE.match(normaliza_espacos(pasta.name))
            if not m:
                continue
            pid = int(m.group("id"))
            try:
                sobre = le_patente_json(pasta, self._categorias())
                problema = ""
            except PatenteJsonInvalido as e:
                sobre, problema = None, str(e)

            arqs = arquivos_da_pasta(pasta)
            campos = sobre.campos if sobre else {}
            saida.append(
                {
                    "id": pid,
                    "numero": f"BR {m.group('esp')} {m.group('ano')} "
                    f"{m.group('seq')}-{m.group('dv')}",
                    "titulo": campos.get("titulo") or pasta.name,
                    "categoria": campos.get("categoria") or "",
                    "oculta": bool(sobre.oculta) if sobre else False,
                    "editada": sobre is not None,
                    "temPdf": bool(arqs.pdfs),
                    "temCapa": bool(arqs.imagens),
                    "problema": problema,
                }
            )
        return saida

    @staticmethod
    def _abre_no_sistema(alvo: Path) -> None:
        if os.name == "nt":
            os.startfile(str(alvo))  # noqa: S606 - destino de lista fechada
        else:  # pragma: no cover - o painel e Windows
            subprocess.Popen(["xdg-open", str(alvo)])


class _ServidorLocal:
    """Servidor estatico somente leitura da pasta do site, preso em 127.0.0.1.

    Existe para a equipe conferir a vitrine inteira antes de publicar. Nao
    serve nada fora da pasta do site, nao aceita nada alem de GET e HEAD, e
    nao escuta em nenhum endereco de rede (T2).
    """

    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)
        self._httpd = None
        self._thread = None

    @property
    def url(self) -> str:
        porta = self._httpd.server_address[1] if self._httpd else 0
        return f"http://127.0.0.1:{porta}/index.html"

    def inicia(self) -> None:
        import functools
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

        class Somente_leitura(SimpleHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                self.send_error(405)

            do_PUT = do_DELETE = do_PATCH = do_POST

            def log_message(self, *a):  # silencia o log no console
                pass

        handler = functools.partial(Somente_leitura, directory=str(self.raiz))
        # porta 0: o sistema escolhe uma livre; "127.0.0.1" e nao "" ou
        # "0.0.0.0", para que nenhuma outra maquina da rede alcance
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def para(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
