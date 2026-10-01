# -*- coding: utf-8 -*-
"""Painel local de administracao da Vitrine de Patentes UFC.

Aplicativo de janela unica que a equipe da UFC Inova abre com dois cliques
para cadastrar, editar e publicar patentes sem terminal.

Nao ha login, e por isso o painel nao fica acessivel pela rede: a fronteira
de seguranca e a conta do Windows de quem usa o computador. A comunicacao
entre a interface e o Python passa pela ponte interna do pywebview, nao por
HTTP -- nenhum site aberto no navegador da pessoa consegue alcancar o painel.

Modulos:
    config         config.json e onde cada coisa mora no computador
    auditoria      historico de acoes, em JSON Lines
    backup         copia antes de cada alteracao, e restauracao
    validacao      regras dos campos do formulario (PRD secao 8)
    armazenamento  quarentena, gravacao no acervo, lixeira
    previa         objeto no formato de PATENTES[i] para o js/render.js
    publicacao     pacote .zip por lista de permissoes
    api            a superficie exposta ao JavaScript (PRD 5.3)

A logica de dados (extracao das fichas, imagens, build) NAO mora aqui: vem de
`scripts/vitrine_core/`, o mesmo pacote que a linha de comando usa.
"""
from __future__ import annotations

__all__ = ["VERSAO"]

VERSAO = "1.0.0"
