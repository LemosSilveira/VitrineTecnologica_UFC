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
| `specs/csp.spec.js` | a Content-Security-Policy do `.htaccess`: sem `'unsafe-inline'`, sem violação em nenhuma página, nenhum script ou estilo inline nos HTML |
| `specs/sem-pdf.spec.js` | o site com uma patente **sem PDF**: prévia cai para a capa, o card do documento some, a coluna ocupa a largura toda, sem lightbox |
| `specs/visual.spec.js` | referências de pixel da home, do hero, dos cards, da prévia, de 3 detalhes e da 404 |

`specs/_ajuda.js` concentra os utilitários; não é um spec (o `testMatch` só
pega `*.spec.js`).

## Testes do `vitrine_core` (pytest)

```bash
pip install pytest
python -m pytest tests/core       # da raiz do repositório
```

| Arquivo | Cobre |
|---|---|
| `core/test_nomes.py` | normalização de texto, slug, e os regex de pasta/arquivo com as inconsistências reais das 60 pastas |
| `core/test_extracao.py` | fatiamento das seções, junção de parágrafo, diferenciais, TRL e resumo |
| `core/test_io_seguro.py` | escrita atômica (inclusive falha no meio), idempotência do `write_if_changed`, confinamento de caminho |
| `core/test_acervo.py` | ordenação e classificação das pastas, validação do `dados/categorias.json` |
| `core/test_patente_json.py` | o esquema da sobreposição: tipos, limites, campos desconhecidos, bidi e controle |
| `core/test_pdf_seguro.py` | limites, assinatura, senha, páginas, e a higienização (JavaScript, `/OpenAction`, `/AA`, `/Launch`, anexos, metadados) |
| `core/test_ler_ficha.py` | preenchimento automático e o **teste de ouro** nas 60 fichas reais |
| `core/test_build_integracao.py` | o build ponta a ponta num acervo sintético: oculta, merge, sem PDF, lixeira, gravação só sem erro, limpeza de assets |
| `core/test_build.py` | escape de JS, formato do `patentes.js` e **paridade com o build legado** |

O teste de ouro (`core/test_ler_ficha.py::TestDeOuro`) depende das 60 fichas
originais e é **pulado** em máquinas que não têm o acervo.

Os PDFs maliciosos de `core/test_pdf_seguro.py` são construídos em tempo de
execução, não guardados como fixtures: um arquivo com `/JavaScript` dentro do
repositório seria sinalizado por antivírus e por scanners de segurança, e a
vitrine não precisa carregar isso.

A classe `TestParidadeComOLegado` compara as funções puras com
`fixtures/build_legado.py`. Enquanto ela passar, a extração do pacote não
mudou comportamento; se um dia uma mudança for intencional, ela precisa
aparecer ali e ser justificada, não passar despercebida.

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

Linha de base da saída do build.

```bash
python tests/fixtures/snapshot-fase0/verificar_snapshot.py
python tests/fixtures/snapshot-fase0/verificar_snapshot.py --ignorar-pdf
```

Compara `js/data/patentes.js`, `scripts/build_report.md` e os 300 arquivos de
`assets/patentes/**` com o que foi congelado. Sai com código ≠ 0 em qualquer
divergência — que deve ser tratada como **não intencional** até que se prove o
contrário.

A pasta se chama `snapshot-fase0` porque nasceu na Fase 0, mas o conteúdo
acompanha a última mudança **deliberada** de saída. O `MANIFEST.md` registra
qual fase e por quê; o histórico do git guarda as versões anteriores. Para
regravar (só com motivo):

```bash
python tests/fixtures/snapshot-fase0/gerar_snapshot.py \
    --fase 3 --motivo "por que a saída mudou"
```

Até agora houve **uma** mudança deliberada: na Fase 2 o `ficha.pdf` passou a
ser higienizado em vez de copiado byte a byte, o que alterou os 60 hashes de
`ficha.pdf` e uma linha de peso no relatório. O `patentes.js` e os 240
arquivos WebP continuam idênticos aos da Fase 0.

`--ignorar-pdf` compara tudo menos os `ficha.pdf` — útil ao trocar a versão do
PyMuPDF, que pode gerar bytes diferentes para o mesmo conteúdo.

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
