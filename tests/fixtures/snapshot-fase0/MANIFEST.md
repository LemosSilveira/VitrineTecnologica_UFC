# Snapshot de referencia — Fase 0

Gerado em 2026-09-29T13:44:44-03:00 por `gerar_snapshot.py`.

Linha de base da vitrine **antes** da refatoracao do build
(PRD secao 14, Fase 0). As Fases 1 e 2 so passam se
`verificar_snapshot.py` nao acusar diferenca.

| Item | Valor |
|---|---|
| `js/data/patentes.js` | `1835a3335c091a7bd264e0fb424366dc6a5d5003c0e6c61e53b250fefd679f55` |
| `scripts/build_report.md` | `661fcb44e1a2f0dd0e716a5c3b3e4e4d1b8b6ee7fbe29ed971b44133e2869eb1` |
| Arquivos em `assets/patentes/**` | 300 |
| Pastas de patente | 60 |

> A Fase 2 troca a copia byte a byte do PDF por uma versao
> higienizada (PRD 5.4). Os hashes de `ficha.pdf` mudam **uma vez**;
> `verificar_snapshot.py --ignorar-pdf` compara todo o resto.
