# -*- coding: utf-8 -*-
"""Regras dos campos do formulario (PRD secao 8).

A validacao da interface serve para dar retorno imediato a quem digita. **Esta
aqui e a que vale.** Toda ela roda de novo no Python, em `previa` e em
`salvar`, porque o JS da janela pode ter sido alterado pelo DevTools ou
simplesmente estar desatualizado (T11).

Os limites vem de `vitrine_core.acervo.LIMITES`, os mesmos que validam o
`patente.json`: duas listas de limites divergiriam no primeiro ajuste, e a
equipe veria o formulario aceitar um texto que o build depois recusa.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from vitrine_core.acervo import LIMITES, TIPOS  # noqa: E402
from vitrine_core.nomes import NUMERO_RE, limpa_texto  # noqa: E402

__all__ = ["ANO_MIN", "Rascunho", "valida", "normaliza_numero_do_formulario"]

# 1990 e anterior a qualquer patente da UFC no acervo; +1 cobre o pedido
# depositado no fim do ano que entra no sistema com data do ano seguinte.
ANO_MIN = 1990

_SECOES_OPCIONAIS = ("problema", "exemploDeUso", "beneficio")


@dataclass
class Rascunho:
    """Resultado da validacao: o que salvar e o que mostrar em cada campo."""

    dados: dict = field(default_factory=dict)
    erros: dict = field(default_factory=dict)
    avisos: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.erros


def normaliza_numero_do_formulario(bruto: object) -> str | None:
    """`br1020250123456` ou `BR 10 2025 012345-6` -> forma canonica.

    A mascara da interface ajuda, mas nao garante: colar o numero de outro
    sistema traz qualquer formatacao.
    """
    m = NUMERO_RE.search(limpa_texto(bruto))
    if not m:
        return None
    return f"BR {m.group('esp')} {m.group('ano')} {m.group('seq')}-{m.group('dv')}"


def _texto(destino: dict, erros: dict, dados: dict, campo: str, rotulo: str,
           limites: tuple[int, int], obrigatorio: bool) -> str | None:
    bruto = dados.get(campo)
    valor = limpa_texto(bruto) if bruto is not None else ""
    minimo, maximo = limites

    if not valor:
        if obrigatorio:
            erros[campo] = f"{rotulo} é obrigatório."
            return None
        return None
    if len(valor) < max(minimo, 1):
        erros[campo] = (
            f"{rotulo} está muito curto: {len(valor)} caracteres, "
            f"e o mínimo é {minimo}."
        )
        return None
    if len(valor) > maximo:
        erros[campo] = (
            f"{rotulo} está muito longo: {len(valor)} caracteres, "
            f"e o máximo é {maximo}."
        )
        return None
    destino[campo] = valor
    return valor


def valida(
    dados: object,
    *,
    categorias: dict[str, str],
    numeros_existentes: dict[str, int] | None = None,
    id_editando: int | None = None,
    tem_capa: bool = False,
    tem_pdf: bool = False,
) -> Rascunho:
    """Valida o rascunho do formulario.

    `numeros_existentes` mapeia numero canonico -> id, **incluindo a lixeira**:
    reaproveitar um numero criaria duas patentes com o mesmo pedido no INPI.
    `id_editando` e o id da patente em edicao, para que o proprio numero dela
    nao conte como duplicado.
    """
    r = Rascunho()
    if not isinstance(dados, dict):
        r.erros["_"] = "Não recebemos os dados do formulário."
        return r

    campos: dict = {}
    nova = id_editando is None

    # ---- numero do pedido ----------------------------------------------
    # Em edicao o numero nao e editavel: vem sempre do nome da pasta.
    if nova:
        numero = normaliza_numero_do_formulario(dados.get("numero"))
        if not numero:
            r.erros["numero"] = (
                "Informe o número do pedido no formato BR 10 2025 012345-6."
            )
        else:
            ano = int(numero.split()[2])
            limite = date.today().year + 1
            if not ANO_MIN <= ano <= limite:
                r.erros["numero"] = (
                    f"O ano {ano} está fora do esperado (de {ANO_MIN} a {limite}). "
                    "Confira o número."
                )
            elif numeros_existentes and numero in numeros_existentes:
                outro = numeros_existentes[numero]
                r.erros["numero"] = (
                    f"Este número já está cadastrado na patente {outro} "
                    "(a lixeira também conta). Números não são reaproveitados."
                )
            else:
                campos["numero"] = numero
                campos["tipo"] = TIPOS[numero.split()[1]]
                campos["ano"] = ano

    # ---- area tecnologica -----------------------------------------------
    categoria = limpa_texto(dados.get("categoria"))
    if not categoria:
        r.erros["categoria"] = "Escolha a área tecnológica."
    elif categoria not in set(categorias.values()):
        r.erros["categoria"] = (
            f"A área “{categoria}” não existe na lista. Escolha uma da lista ou "
            "adicione a área nova em Configurar."
        )
    else:
        campos["categoria"] = categoria

    # ---- titulo ----------------------------------------------------------
    titulo = _texto(campos, r.erros, dados, "titulo", "O título", LIMITES["titulo"], True)
    if titulo and titulo.isupper():
        # nao e erro: a interface oferece "Converter para caixa de frase"
        r.avisos["titulo"] = (
            "O título está todo em MAIÚSCULAS. Na vitrine ele fica mais legível "
            "em caixa de frase."
        )

    # ---- secoes ----------------------------------------------------------
    secoes: dict = {}
    bruto_secoes = dados.get("secoes")
    if bruto_secoes is None:
        bruto_secoes = {}
    if not isinstance(bruto_secoes, dict):
        r.erros["secoes"] = "Não recebemos os textos da ficha."
        bruto_secoes = {}

    erros_secoes: dict = {}
    _texto(secoes, erros_secoes, bruto_secoes, "oQueE", "O campo “O que é?”",
           LIMITES["oQueE"], True)
    for campo in _SECOES_OPCIONAIS:
        rotulo = {
            "problema": "O campo “Problema que resolve”",
            "exemploDeUso": "O campo “Exemplo de uso”",
            "beneficio": "O campo “Benefício principal”",
        }[campo]
        _texto(secoes, erros_secoes, bruto_secoes, campo, rotulo, LIMITES[campo], False)

    # ---- diferenciais ----------------------------------------------------
    itens = bruto_secoes.get("diferenciais")
    if itens is None:
        itens = []
    if not isinstance(itens, list):
        erros_secoes["diferenciais"] = "A lista de diferenciais não chegou como lista."
    elif len(itens) > LIMITES["diferenciais_max"]:
        erros_secoes["diferenciais"] = (
            f"São {len(itens)} diferenciais e o máximo é "
            f"{LIMITES['diferenciais_max']}. Junte os parecidos."
        )
    else:
        lo, hi = LIMITES["diferencial"]
        limpos = []
        for i, it in enumerate(itens):
            v = limpa_texto(it)
            if not v:
                continue  # linha em branco no editor: simplesmente ignorada
            if len(v) < lo:
                erros_secoes[f"diferenciais.{i}"] = (
                    f"O diferencial {i + 1} está muito curto (mínimo {lo} caracteres)."
                )
            elif len(v) > hi:
                erros_secoes[f"diferenciais.{i}"] = (
                    f"O diferencial {i + 1} está muito longo (máximo {hi} caracteres)."
                )
            else:
                limpos.append(v)
        if limpos:
            secoes["diferenciais"] = limpos

    for k, v in erros_secoes.items():
        r.erros[f"secoes.{k}"] = v
    if secoes:
        campos["secoes"] = secoes

    # ---- TRL -------------------------------------------------------------
    trl = dados.get("trl")
    if trl is not None:
        if not isinstance(trl, dict):
            r.erros["trl"] = "A maturidade tecnológica não chegou no formato esperado."
        else:
            lo, hi = trl.get("min"), trl.get("max")
            piso, teto = LIMITES["trl_min"], LIMITES["trl_max"]
            valores_ok = True
            for v in (lo, hi):
                if not isinstance(v, int) or isinstance(v, bool) or not piso <= v <= teto:
                    r.erros["trl"] = f"O TRL vai de {piso} a {teto}."
                    valores_ok = False
                    break
            if valores_ok and lo > hi:
                r.erros["trl"] = "O TRL mínimo não pode ser maior que o máximo."
            elif valores_ok:
                estimado = trl.get("estimado", False)
                if not isinstance(estimado, bool):
                    r.erros["trl"] = "O campo “estimado” deveria ser sim ou não."
                else:
                    campos["trl"] = {"min": lo, "max": hi, "estimado": estimado}

    # ---- arquivos --------------------------------------------------------
    if nova and not tem_capa:
        r.erros["capa"] = "Escolha a imagem de capa: ela é obrigatória."
    if not tem_pdf:
        r.avisos["pdf"] = (
            "Sem o PDF, a vitrine não terá o botão de download nem a imagem "
            "da ficha."
        )

    r.dados = campos
    return r
