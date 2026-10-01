# Snapshot de referencia — Fase 2

Gerado em 2026-09-30T12:23:02-03:00 por `gerar_snapshot.py`.

Linha de base da saida do build. Qualquer divergencia apontada por
`verificar_snapshot.py` e mudanca **nao** intencional, ate que se
prove o contrario.

**Motivo desta versao:** o ficha.pdf publicado passou a ser higienizado em vez de copia byte a byte (PRD 5.4, achado A4); o patentes.js e os 240 arquivos WebP continuam identicos aos da Fase 0

| Item | Valor |
|---|---|
| `js/data/patentes.js` | `1835a3335c091a7bd264e0fb424366dc6a5d5003c0e6c61e53b250fefd679f55` |
| `scripts/build_report.md` | `dbe5b6c864b3fec6b636004cbb52d34a521721a8c6f6dc38dab3dac70d0d37a5` |
| Arquivos em `assets/patentes/**` | 300 |
| Pastas de patente | 60 |

## Como regravar

Somente quando a mudanca de saida for **deliberada**, com o motivo
no commit:

```bash
python tests/fixtures/snapshot-fase0/gerar_snapshot.py \
    --fase 3 --motivo "por que a saida mudou"
```
