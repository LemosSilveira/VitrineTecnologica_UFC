# Testes da Vitrine de Patentes

Rede de segurança do site estático. Existe para que a refatoração do build e a
extração do `js/render.js` (Fases 1 e 2 do `PRD-painel-local-vitrine.md`)
possam acontecer sem mudar nada para quem visita a vitrine.

```bash
cd tests
npm install
npx playwright install chromium

npm test                 # tudo, nos dois viewports
npm run test:desktop     # só 1440×900
npm run test:mobile      # só 390×844
npm run report           # abre o relatório HTML da última execução
npm run servir           # sobe a vitrine em http://127.0.0.1:4173
```

Roda **só em Chromium**. Nenhum spec depende do motor: voltar a incluir
Firefox e WebKit é acrescentar dois `projects` em `playwright.config.js` e
rodar `npx playwright install`.

O servidor sobe sozinho (`webServer` da config). Se já houver algo na 4173,
ele reaproveita.

## O que cada arquivo cobre

| Arquivo | Cobertura |
|---|---|
| `specs/home.spec.js` | as 60 patentes na grade, números do hero, busca (acento, caixa, número com e sem hífen), estado vazio, filtros por área e tipo, ordenação, estado na URL, prévia da ficha no hover (posição, teclado, `Esc`), `prefers-reduced-motion`, restauração da rolagem |
| `specs/patente.spec.js` | as 60 páginas de detalhe, seções da ficha, diferenciais, medidor de TRL, coluna do documento (PDF existe no disco), lightbox (abrir, zoom, foco de volta), navegação circular, relacionadas, migalhas, `?id=` inválido → 404 |
| `specs/erro.spec.js` | a 404 direta e por rota desconhecida, funcionamento em qualquer profundidade de URL, caminhos absolutos, `noindex` |
| `specs/acessibilidade.spec.js` | axe-core (WCAG 2.1 A/AA) na home, no detalhe, com o lightbox aberto e na 404 — **zero violações serious/critical** — mais link de pular, um `h1` por página, `alt` das capas, `rel=noopener` |
| `specs/visual.spec.js` | referências de pixel da home, do hero, do card, da prévia, de 3 detalhes e da 404 |

`specs/_ajuda.js` concentra os utilitários; não é um spec (o `testMatch` só
pega `*.spec.js`).

## Referências visuais

Ficam versionadas em `specs/visual.spec.js-snapshots/`. Tolerância de **0,1%**
dos pixels, definida em `playwright.config.js`.

São a porta de saída da Fase 2: mover `htmlCard`, `htmlTrl`, `htmlSecao` e
`htmlDiferenciais` para `js/render.js` não pode mudar um pixel.

```bash
npm run visual:atualizar   # regrava as referências — só quando a mudança for intencional
```

> As capturas são geradas no Chromium do Windows. Em outro sistema
> operacional o Playwright procura um arquivo com outro sufixo
> (`-linux.png`) e acusa referência ausente. Rode em Windows ou gere as
> referências do outro sistema com `--update-snapshots`.

## Snapshot do build (`fixtures/snapshot-fase0/`)

Linha de base da vitrine **antes** da refatoração do build.

```bash
python tests/fixtures/snapshot-fase0/verificar_snapshot.py
python tests/fixtures/snapshot-fase0/verificar_snapshot.py --ignorar-pdf
```

Compara `js/data/patentes.js`, `scripts/build_report.md` e os 300 arquivos de
`assets/patentes/**` com o que foi congelado na Fase 0. Sai com código ≠ 0 em
qualquer divergência.

`--ignorar-pdf` é para a Fase 2: a higienização do PDF (PRD 5.4) muda os bytes
de `ficha.pdf` **uma vez**, de propósito; todo o resto continua tendo de bater.

`fixtures/build_legado.py` é a cópia do `scripts/build_patentes.py` de antes da
refatoração, guardada para a comparação exigida em 6.1.

## Notas

- O servidor de teses (`server.js`) responde **404 com o corpo da `404.html`**
  em rotas desconhecidas, como o Apache faz via `ErrorDocument`. Sem isso não
  dá para testar a 404.
- A prévia da ficha no hover só existe em ponteiro fino e largura ≥ 1024px;
  os specs dela são pulados no viewport móvel (daí os 12 testes `skipped`).
- Ao focar um card fora da tela, a rolagem suave do `html` continua emitindo
  eventos de `scroll` depois dos 350ms de atraso da prévia, e o handler de
  scroll a fecha. Por isso o spec de teclado rola o card para dentro da tela
  antes de focar — que é o que acontece na prática ao tabular de um card para
  o vizinho.
