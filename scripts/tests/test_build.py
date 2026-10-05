#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes unitarios do pipeline de dados (PRD 6.1). Nao precisam do acervo real."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_patentes as bp  # noqa: E402


def _entrada(numero: str, prefixo_id: int | None = None, pasta_nome: str = "x", corrigido_o: bool = False) -> bp.EntradaPasta:
    partes = numero.replace("BR ", "").replace("-", " ").split()
    esp, ano, seq, dv = partes
    return bp.EntradaPasta(
        pasta=Path(pasta_nome),
        src_root=Path("src"),
        numero=numero,
        esp=esp,
        ano=ano,
        seq=seq,
        dv=dv,
        prefixo_id=prefixo_id,
        corrigido_o=corrigido_o,
    )


# --------------------------------------------------------------------------
# normaliza_numero_bruto (P2)
# --------------------------------------------------------------------------

def test_normaliza_numero_bruto_corrige_letra_o():
    assert bp.normaliza_numero_bruto("BR 10 2013 023074 O") == "BR 10 2013 023074 0"


def test_normaliza_numero_bruto_minuscula_tambem_corrige():
    assert bp.normaliza_numero_bruto("br 10 2013 023074 o") == "br 10 2013 023074 0"


def test_normaliza_numero_bruto_nao_altera_letras_fora_do_numero():
    s = "Observatorio - BR 10 2013 023074 O - Outro Titulo com Varios Os"
    out = bp.normaliza_numero_bruto(s)
    assert out == "Observatorio - BR 10 2013 023074 0 - Outro Titulo com Varios Os"


def test_normaliza_numero_bruto_sem_o_nao_muda_nada():
    s = "BR 10 2015 029772 6"
    assert bp.normaliza_numero_bruto(s) == s


# --------------------------------------------------------------------------
# Regra de titulo (P3)
# --------------------------------------------------------------------------

def test_titulo_palavra_partida_usa_o_do_arquivo():
    res = bp.Resultado()
    titulo = bp.escolhe_titulo(
        "Uso Analgésico do Derivado 13-Hidroxi-2a-Propanoiloxiestemodan o (SM-2)",
        "Uso Analgésico do Derivado 13-Hidroxi-2a-Propanoiloxiestemodano (SM-2)",
        87,
        res,
    )
    assert titulo == "Uso Analgésico do Derivado 13-Hidroxi-2a-Propanoiloxiestemodano (SM-2)"
    assert any("palavra partida" in a for a in res.avisos)


def test_titulo_maiusculas_do_arquivo_mantem_o_do_pdf():
    res = bp.Resultado()
    titulo = bp.escolhe_titulo(
        "Composição e uso de um produto",
        "COMPOSIÇÃO E USO DE UM PRODUTO",
        52,
        res,
    )
    assert titulo == "Composição e uso de um produto"
    assert not any("palavra partida" in a for a in res.avisos)


def test_titulo_truncado_usa_o_do_arquivo():
    res = bp.Resultado()
    titulo = bp.escolhe_titulo(
        "Dispositivo",
        "Dispositivo para Transporte de Animais Vivos",
        4,
        res,
    )
    assert titulo == "Dispositivo para Transporte de Animais Vivos"
    assert any("truncado" in a for a in res.avisos)


# --------------------------------------------------------------------------
# Registro de IDs (PRD 3.2)
# --------------------------------------------------------------------------

def test_atribui_ids_novo_recebe_max_mais_um():
    res = bp.Resultado()
    entradas = [
        _entrada("BR 10 2020 000001-1", prefixo_id=5),
        _entrada("BR 10 2020 000002-2", prefixo_id=None),
    ]
    registro = bp.atribui_ids(entradas, {"BR 10 2020 000001-1": 5}, res)
    assert registro["BR 10 2020 000002-2"] == 6
    assert not res.erros


def test_atribui_ids_ordem_deterministica_pelo_numero_br():
    res = bp.Resultado()
    entradas = [
        _entrada("BR 10 2020 000005-0", prefixo_id=None),
        _entrada("BR 10 2020 000002-0", prefixo_id=None),
    ]
    registro = bp.atribui_ids(entradas, {}, res)
    assert registro["BR 10 2020 000002-0"] == 1
    assert registro["BR 10 2020 000005-0"] == 2


def test_atribui_ids_prefixo_conflitante_com_registro_e_erro():
    res = bp.Resultado()
    entradas = [_entrada("BR 10 2020 000001-1", prefixo_id=9)]
    bp.atribui_ids(entradas, {"BR 10 2020 000001-1": 5}, res)
    assert res.erros


def test_filtra_duplicados_numero_repetido_e_erro():
    res = bp.Resultado()
    e1 = _entrada("BR 10 2020 000001-1", pasta_nome="a")
    e2 = _entrada("BR 10 2020 000001-1", pasta_nome="b")
    unicos = bp.filtra_duplicados([e1, e2], res)
    assert len(unicos) == 1
    assert res.erros


# --------------------------------------------------------------------------
# monta_entrada: pasta sem prefixo e com letra O (P1 + P2)
# --------------------------------------------------------------------------

def test_monta_entrada_aceita_pasta_sem_prefixo(tmp_path):
    pasta = tmp_path / "BR 10 2015 029772 6"
    pasta.mkdir()
    res = bp.Resultado()
    e = bp.monta_entrada(pasta, tmp_path, res)
    assert e is not None
    assert e.prefixo_id is None
    assert e.numero == "BR 10 2015 029772-6"
    assert not res.erros


def test_monta_entrada_corrige_letra_o_no_digito_verificador(tmp_path):
    pasta = tmp_path / "BR 10 2013 023074 O"
    pasta.mkdir()
    res = bp.Resultado()
    e = bp.monta_entrada(pasta, tmp_path, res)
    assert e is not None
    assert e.numero == "BR 10 2013 023074-0"
    assert e.corrigido_o is True


def test_monta_entrada_mantem_prefixo_quando_existe(tmp_path):
    pasta = tmp_path / "19. BR 10 2022 019303 7"
    pasta.mkdir()
    res = bp.Resultado()
    e = bp.monta_entrada(pasta, tmp_path, res)
    assert e is not None
    assert e.prefixo_id == 19


# --------------------------------------------------------------------------
# Build com erro nao grava dados (P4)
# --------------------------------------------------------------------------

def test_build_com_erro_nao_grava_patentes_js(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    (src / "pasta invalida sem padrao").mkdir()

    out = tmp_path / "out"
    (out / "js" / "data").mkdir(parents=True)
    sentinela = b"/* sentinela existente */\nwindow.PATENTES = [];\n"
    (out / "js" / "data" / "patentes.js").write_bytes(sentinela)

    monkeypatch.setattr(sys, "argv", ["build_patentes.py", "--src", str(src), "--out", str(out)])
    codigo = bp.main()

    assert codigo == 1
    assert (out / "js" / "data" / "patentes.js").read_bytes() == sentinela
    assert not (out / "dados" / "ids_patentes.json").exists()
    assert (out / "scripts" / "build_report_FALHOU.md").exists()
    assert not (out / "scripts" / "build_report.md").exists()


# --------------------------------------------------------------------------
# docx/xlsx ignorados (PRD 1)
# --------------------------------------------------------------------------

def test_arquivos_da_pasta_ignora_docx_e_xlsx(tmp_path):
    pasta = tmp_path / "patente"
    pasta.mkdir()
    (pasta / "ficha.pdf").write_bytes(b"%PDF-1.4")
    (pasta / "capa.png").write_bytes(b"\x89PNG\r\n")
    (pasta / "Texto-Imagem.docx").write_bytes(b"docx")
    (pasta / "BR123.xlsx").write_bytes(b"xlsx")

    pdfs, imgs, outros = bp.arquivos_da_pasta(pasta)

    assert [p.name for p in pdfs] == ["ficha.pdf"]
    assert [p.name for p in imgs] == ["capa.png"]
    assert sorted(p.name for p in outros) == ["BR123.xlsx", "Texto-Imagem.docx"]
