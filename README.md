# Vitrine de Patentes UFC

Site estático que apresenta as **60 patentes** da Universidade Federal do Ceará
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

O array de patentes **nunca** é editado à mão: ele é gerado a partir da pasta
original com as fichas.

```bash
pip install pymupdf pillow

python scripts/build_patentes.py \
  --src "C:\Users\Usuario\Documents\50 Patentes Observatório-20260924T152758Z-1-001\50 Patentes Observatório" \
  --out .
```

O script:

1. lê cada subpasta `N. BR XX AAAA NNNNNN D` (o número antes do ponto é o ID);
2. extrai o texto da ficha com PyMuPDF e separa as seções
   (*O que é? · Problema que resolve · Exemplo de uso · Diferenciais
   competitivos · Benefício principal · TRL*);
3. gera as imagens otimizadas em WebP e copia o PDF original;
4. escreve `js/data/patentes.js` e `scripts/build_report.md`.

**A pasta de origem é somente leitura** — o script nunca renomeia, move ou
apaga nada. E o build é **idempotente**: rodar duas vezes não altera nenhum
byte (arquivos só são reescritos quando o conteúdo muda).

O script termina com código ≠ 0 se houver **erro** (não se houver só avisos).
Confira sempre o `scripts/build_report.md` depois de rodar.

### Como adicionar uma patente nova

1. Crie uma subpasta na pasta de origem seguindo o padrão
   `61. BR 10 2026 001234 5`.
2. Coloque dentro **um PDF** (a ficha técnica) e **uma imagem** de capa.
   O nome do PDF deve seguir `N. Categoria - BR XX AAAA NNNNNN D - Título.pdf`.
3. Rode o build de novo. Nada mais precisa ser tocado: a grade, os filtros,
   os contadores do hero e a navegação anterior/próxima saem todos de
   `window.PATENTES`.

A **categoria** precisa estar no mapa `CATEGORIA_MAP` do script. Se aparecer
uma categoria desconhecida, o build **falha com mensagem clara** em vez de
inventar uma área nova — se a categoria for legítima, adicione-a ao mapa.

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

A 404 usa **caminhos absolutos** de propósito: ela pode ser servida em
qualquer profundidade de URL (`/patente/xyz/abc`), e caminhos relativos
quebrariam o CSS, as fontes e o logo.

---

## Testes

```bash
cd tests
npm install
npx playwright install chromium firefox webkit

npm test                              # tudo
npx playwright test --project=chromium-desktop   # só um motor
npx playwright show-report
```

Cobre: renderização das 60 patentes, busca (com e sem acento, por número),
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
├── scripts/
│   ├── build_patentes.py   Pipeline de dados
│   ├── fonts_to_woff2.py   Conversão das fontes
│   ├── gerar_og.js         Gera a og-image a partir de og_template.html
│   └── build_report.md     GERADO — relatório do build
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
