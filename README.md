# Vitrine de Patentes UFC

Site estático que apresenta as **93 patentes** da Universidade Federal do Ceará
disponíveis para licenciamento, com identidade da **UFC Inova**.

HTML + CSS + JavaScript puro, sem framework e sem dependência externa em runtime.
O conteúdo vem de um script Python que lê as pastas originais das fichas técnicas.

---

## Como rodar localmente

Não há passo de build para o site em si — basta servir a pasta.

```bash
# opção 1: servidor dos testes (serve a 404.html em rotas desconhecidas)
node tests/server.js            # http://127.0.0.1:4173

# opção 2: Python
python -m http.server 4173

# opção 3: extensão Live Server do VS Code (clique com o botão direito no index.html)
```

> O site também abre direto pelo `file://`, porque os dados são um `.js` que
> define `window.PATENTES` (não há `fetch()` nem ES Modules). A única
> diferença é que a 404 não é acionada pelo servidor.

---

## Como atualizar os dados (rodar o build)

O array de patentes **nunca** é editado à mão: ele é gerado a partir de uma ou
mais pastas de origem com as fichas. `--src` pode repetir para combinar vários
lotes num mesmo build:

```bash
pip install pymupdf pillow

python scripts/build_patentes.py \
  --src "C:\Users\Usuario\Documents\50 Patentes Observatório-20260924T152758Z-1-001\50 Patentes Observatório" \
  --src "C:\Users\Usuario\Documents\comparação de patentes\patente 3" \
  --out .
```

O script:

1. lê cada subpasta de patente — com prefixo de ID (`N. BR XX AAAA NNNNNN D`)
   ou sem ele (`BR XX AAAA NNNNNN D`, usado em lotes novos; ver registro de
   IDs abaixo);
2. extrai o texto da ficha com PyMuPDF e separa as seções
   (*O que é? · Problema que resolve · Exemplo de uso · Diferenciais
   competitivos · Benefício principal · TRL*);
3. gera as imagens otimizadas em WebP e copia o PDF original;
4. escreve `js/data/patentes.js`, `dados/ids_patentes.json` e
   `scripts/build_report.md` — **só se o build terminar sem erros**. Com
   erro, nada desses três arquivos é tocado; o relatório sai em
   `scripts/build_report_FALHOU.md` para diagnóstico.

**As pastas de origem são somente leitura** — o script nunca renomeia, move
ou apaga nada nelas. E o build é **idempotente**: rodar duas vezes não altera
nenhum byte (arquivos só são reescritos quando o conteúdo muda).

O script termina com código ≠ 0 se houver **erro** (não se houver só avisos).
Confira sempre o relatório depois de rodar.

### Registro permanente de IDs (`dados/ids_patentes.json`)

O ID de cada patente define a URL (`patente.html?id=N`) e por isso **nunca
pode mudar** depois de publicado. Esse arquivo mapeia `numero INPI -> ID` e é
a fonte da verdade:

- pasta **com prefixo** (`19. BR ...`): o ID é o do prefixo. Se o número já
  estiver no registro com outro ID, o build falha.
- pasta **sem prefixo** (lote novo): o ID vem do registro; se o número ainda
  não está lá, recebe `maior ID do registro + 1`. Com várias pastas novas no
  mesmo build, a atribuição segue a ordem do número BR (espécie, ano,
  sequencial) — determinística, não depende da ordem de leitura do disco.
- o mesmo número BR em duas pastas diferentes (até de origens diferentes) é
  **erro**.

Nunca edite esse arquivo à mão, exceto para corrigir um erro de digitação —
e, nesse caso, só depois de confirmar que o ID antigo não foi publicado.

### Lista de exclusão (`dados/excluir.json`)

Opcional. Lista números BR que devem ficar de fora do site nesta rodada,
sem perder o ID reservado no registro — útil para segurar uma ficha com
problema de conteúdo até vir uma versão corrigida:

```json
{ "versao": 1, "numeros": ["BR 10 2016 030476-8"] }
```

A patente some de `window.PATENTES` e aparece no relatório como "excluído por
decisão", mas o ID continua reservado para ela (nunca é reaproveitado).

### Como inserir um lote novo de patentes

1. Confirme que cada subpasta do lote traz **um PDF** (ficha técnica) e
   **uma imagem** de capa — e nada mais que o build deva usar.
   `.docx`/`.xlsx` e outros arquivos extras são ignorados automaticamente e
   aparecem no relatório.
2. As subpastas podem ou não ter o prefixo numérico; sem prefixo, o ID é
   atribuído automaticamente pelo registro (ver acima).
3. Rode o build apontando `--src` para a pasta antiga **e** para a pasta do
   lote novo (pode repetir `--src` para quantas pastas precisar).
4. Confira o relatório: 0 erros, os avisos esperados, e a seção "IDs
   atribuídos neste build" com os números do lote novo.
5. A **categoria** de cada patente precisa estar no mapa `CATEGORIA_MAP` do
   script. Categoria desconhecida faz o build falhar com mensagem clara em
   vez de inventar uma área nova — se for legítima, adicione-a ao mapa.

### O que o build resolve sozinho

As pastas originais têm várias inconsistências, todas tratadas no script:

| Situação | Exemplo | Tratamento |
|---|---|---|
| PDF terminando em `pdf.pdf` | ids 9, 10, 11, 15–17 | remove o `pdf` sobrando do título |
| Imagem sem título no nome | `34.png`, ids 43–60 | a imagem é achada pela extensão |
| PDF sem título no nome | id 47 | título tirado do texto do PDF |
| Prefixo do arquivo ≠ pasta | `037.`, `048.`, `4.` | **o ID vem sempre da pasta** |
| Título em MAIÚSCULAS | id 52 | usa o título do PDF (caixa correta) |
| Título truncado no PDF | id 4 | usa o do arquivo, que é mais completo |
| Categoria sem traço antes do `BR` | id 48 | o traço é opcional no parser |
| Arquivo extra `.docx` | id 29 | ignorado e registrado no relatório |
| `_` no fim da pasta, espaço duplo | ids 13, 18, 21, 22, 30… | normalizados |
| Número com e sem hífen | vários | normalizado para `BR 10 2018 069181-3` |
| Pasta sem prefixo de ID | lote "patente 3" (ids 61-93) | ID vem do registro `dados/ids_patentes.json` |
| Dígito verificador grafado como letra "O" | id 62 | normalizado para `0` (pasta e nome do arquivo) |
| Título do PDF com palavra quebrada no meio pelo layout | id 87 | usa o título do nome do arquivo |

---

## Como publicar

O site é estático: basta subir a pasta inteira (sem `tests/` e `scripts/`, se
preferir). Confira dois pontos:

1. **`CONFIG.basePath`** em `js/config.js` — hoje é `"/"` (raiz de domínio).
   Se o site for para uma **subpasta** (ex.: GitHub Pages em
   `/vitrine-patentes/`), troque para `"/vitrine-patentes/"`. A 404 usa esse
   valor para reescrever os caminhos absolutos.
2. **A página 404**:
   - **Apache**: o `.htaccess` já traz `ErrorDocument 404 /404.html`
     (além de MIME types, cache e compressão).
   - **GitHub Pages / Netlify**: usam `/404.html` automaticamente.
   - **Nginx**: `error_page 404 /404.html;`
   - **Vercel**: serve `404.html` da raiz automaticamente, com status 404.

A 404 usa **caminhos absolutos** de propósito: ela pode ser servida em
qualquer profundidade de URL (`/patente/xyz/abc`), e caminhos relativos
quebrariam o CSS, as fontes e o logo.

### Vercel

Deploy direto do GitHub, sem passo de build:

1. Import do repositório em vercel.com (**Add New → Project**).
2. **Framework Preset**: Other · **Build Command**: vazio · **Output
   Directory**: `.` · **Install Command**: vazio.
3. Cabeçalhos de segurança e cache (CSP, HSTS, `X-Frame-Options` etc. —
   equivalentes ao `.htaccess`, que a Vercel ignora) ficam em `vercel.json`.
4. Arquivos internos (`scripts/`, `tests/`, `README.md`, `skills-lock.json`,
   `.htaccess`, `*.py`) são excluídos do deploy via `.vercelignore`.
5. Use o deploy pelo GitHub, não a CLI (`vercel deploy`): a pasta tem PDFs e
   imagens suficientes para passar do limite de 100 MB da CLI no plano
   Hobby.

---

## Testes

### Pipeline de dados (Python)

```bash
pip install pytest
python -m pytest scripts/tests/
```

Cobre `normaliza_numero_bruto`, a escolha de título (truncado / palavra
partida / MAIÚSCULAS), a atribuição de IDs pelo registro, a detecção de
número duplicado entre pastas e a regra de não gravar nada quando há erro.

### Site (Playwright)

```bash
cd tests
npm install
npx playwright install chromium firefox webkit

npm test                              # tudo
npx playwright test --project=chromium-desktop   # só um motor
npx playwright show-report
```

Cobre: renderização das 93 patentes, busca (com e sem acento, por número),
filtros por área e tipo, ordenação, estado na URL, prévia da ficha no hover
(posição, teclado, `Esc`), as 60 páginas de detalhe, lightbox, navegação
circular, redirecionamento para a 404, `prefers-reduced-motion`, ausência de
rolagem horizontal em 360/768/1440 e **axe-core sem violações
serious/critical**.

Roda em **Chromium, Firefox e WebKit**, nos viewports 1440×900 e 390×844.
Os screenshots de revisão ficam em `tests/screenshots/`.

Alguns testes são pulados por limitação de plataforma, sempre com o motivo no
código — por exemplo, o WebKit não percorre links com `Tab` enquanto o acesso
completo por teclado do sistema está desligado.

---

## Estrutura

```
├── index.html              Home: hero, busca/filtros, grade
├── patente.html            Detalhe: patente.html?id=19
├── 404.html                Erro (caminhos absolutos)
├── .htaccess               ErrorDocument, MIME, cache
├── css/
│   ├── tokens.css          Cores, tipografia, espaçamento, sombras, easing
│   ├── base.css            Reset, @font-face, tipografia, utilitários
│   ├── components.css      Header, rodapé, card, prévia, chips, TRL, lightbox
│   └── pages.css           Home, detalhe e 404
├── js/
│   ├── config.js           CONFIG global (URLs, e-mail, basePath)
│   ├── data/patentes.js    GERADO — window.PATENTES / window.CATEGORIAS
│   ├── ui.js               Header, reveal, contadores, ícones, utilidades
│   ├── home.js             Busca, filtros, grade, prévia no hover
│   ├── patente.js          Detalhe, TRL, lightbox, navegação
│   └── erro.js             404
├── assets/
│   ├── fonts/              UFCInova-Bold + Metropolis (5 pesos), woff2
│   ├── img/                logo, favicon, og-image
│   └── patentes/<slug>/    capa-400/800.webp, ficha-600/1620.webp, ficha.pdf
├── dados/
│   ├── ids_patentes.json   GERADO — registro permanente numero -> ID
│   └── excluir.json        Lista opcional de numeros fora do site
├── scripts/
│   ├── build_patentes.py   Pipeline de dados
│   ├── fonts_to_woff2.py   Conversão das fontes
│   ├── gerar_og.js         Gera a og-image a partir de og_template.html
│   ├── build_report.md     GERADO — relatório do build (só sem erros)
│   └── tests/              Testes unitários do pipeline (pytest)
└── tests/                  Playwright + axe
```

---

## Identidade

- **Cores** — fundo `#F4F4F5`, texto `#27272A`, marca `#5C069D`, com derivados
  do roxo e a escala zinc para os neutros. Nenhum outro matiz.
- **Tipografia** — títulos em **UFCInova** (um único peso, Bold) e texto em
  **Metropolis** (Regular, Medium, SemiBold, Bold e Regular Italic). Tudo
  local, em woff2, com `font-synthesis: none`.
- **Logo** — aplicado como máscara CSS, então herda `currentColor` (roxo no
  header, branco no rodapé e na 404) sem repetir 11 KB de SVG em cada página.
  Sempre com link para <https://ufcinova.sitios.sti.ufc.br>.
- **Motivo gráfico** — quadrados roxos (o "pingo" do *i* do logo), usados no
  mosaico do hero, nos marcadores de seção e na 404.

### Nota sobre acentuação

Nem a UFCInova nem a Metropolis trazem `º ª ² ³ ° ·`, `τ` ou subscritos
(`₂`). Esses caracteres caem na pilha de fallback (`system-ui`) e foram
conferidos visualmente — o caso mais visível é o título da patente 12,
*"Compósito cerâmico estável para micro-ondas (τf próximo de zero)"*.

---

## Pendências

| # | Item | Situação |
|---|---|---|
| 1 | Fontes reais da Metropolis | **Resolvido** — família oficial em `Documents/metropolis` |
| 2 | Nome do site e texto do hero | Provisórios do PRD, marcados com `<!-- PENDENTE -->` no `index.html` |
| 3 | E-mail de licenciamento | `CONFIG.contatoEmail` vazio → o botão "Tenho interesse" fica escondido |
| 4 | Texto da seção "Sobre" | Rascunho a validar com a Agência, marcado com `<!-- PENDENTE -->` |
| 5 | Hospedagem | Assumida a raiz de domínio (`basePath: "/"`) |
| 6 | `og-image.png` | Versão provisória gerada por `scripts/gerar_og.js` |
