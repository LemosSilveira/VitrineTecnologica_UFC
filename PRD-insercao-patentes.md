# PRD — Inserção de 33 novas patentes na Vitrine (lote "patente 3")

> **Para o Claude Code:** leia este PRD e o `README.md` do projeto inteiros antes de começar. Siga as fases da seção 7 **na ordem** e não avance com teste falhando. Os itens marcados como **DECISÃO** já vêm com um padrão definido; só pergunte ao usuário se algo contradizer o padrão. Os itens marcados como **PERGUNTAR** exigem resposta do usuário antes do commit.

| Campo | Valor |
|---|---|
| Repositório | `C:\Users\Usuario\Desktop\gitClone_VT\VitrineTecnologica_UFC` (GitHub `LemosSilveira/VitrineTecnologica_UFC`, branch `main`, deploy automático na Vercel) |
| Acervo atual (60 patentes, IDs 1–60) | `C:\Users\Usuario\Documents\50 Patentes Observatório-20260924T152758Z-1-001\50 Patentes Observatório` |
| Lote novo (33 patentes, IDs 61–93) | `C:\Users\Usuario\Documents\comparação de patentes\patente 3` |
| Resultado esperado | A vitrine passa de **60 para 93 patentes**, geradas pelo mesmo pipeline (`scripts/build_patentes.py` → `js/data/patentes.js` + `assets/patentes/<slug>/`), versionadas no git |
| Versão do PRD | 1.0 — 05/10/2026 |

---

## 1. Objetivo e regra principal

Inserir as 33 patentes do lote novo **da mesma forma que as 60 primeiras**: os dados são **gerados pelo script de build** a partir das pastas de origem e gravados no código (`js/data/patentes.js` e `assets/patentes/`). **Nada é digitado à mão em `patentes.js`.**

De cada subpasta do lote novo, usar **somente**:
- **o PDF** (a ficha técnica);
- **a imagem** (`.png`/`.jpg`/`.jpeg`), que é a capa do card.

**Ignorar qualquer outro arquivo** (`.docx`, `.xlsx`, etc.). O lote tem 26 arquivos `.docx` ("…_Aprovação - Texto-Imagem.docx" e "BR … .docx"). Eles não podem ser lidos, copiados nem usados como fonte de texto; só aparecem na seção "Arquivos ignorados" do relatório.

**As pastas de origem são somente leitura.** O build nunca renomeia, move, apaga nem cria arquivos nelas, e isso vale para as duas pastas.

---

## 2. Diagnóstico (o pipeline atual já foi testado sobre o lote novo)

O `build_patentes.py` atual foi rodado sobre as 33 pastas, em uma cópia temporária. Resultados:

### 2.1 O que já funciona sem mudança
- **Todas as 33 fichas usam o mesmo template** das 60 anteriores. Título, as 5 seções e o TRL são extraídos **sem nenhum aviso**.
- **Todas as categorias já existem** no `CATEGORIA_MAP`: Engenharias, Ciências da Saúde, Químico→Química, Agropecuária, Alimentos, Biotecnologia, Energia e Meio Ambiente e Cosméticos. O total de áreas continua 10.
- **Todas as capas são quadradas**: 1254×1254 px (30 delas), 1024×1024 (1) e 2048×2048 (1). As duas em RGBA têm alfa 255 (sem transparência), e a conversão para RGB é segura.
- **Nenhum número já existe** na vitrine atual (sem duplicatas com os IDs 1–60).
- Peso: 154,5 MB de origem viram **~89 MB** de assets (a soma das `capa-400.webp` novas é ~1,0 MB).

### 2.2 O que impede a inserção hoje (corrigir na Fase 1)

| # | Problema | Evidência | Correção |
|---|---|---|---|
| P1 | **As pastas novas não têm o prefixo de ID** (`BR 10 2015 029772 6` em vez de `64. BR 10 2015 029772 6`). O `PASTA_RE` exige o prefixo, e o build recusa as 33. | `ERRO: nome de pasta fora do padrao esperado` | Aceitar pastas sem prefixo e atribuir o ID por um **registro de IDs** versionado (3.2). |
| P2 | **Letra "O" no lugar do zero** no dígito verificador: pasta `BR 10 2013 023074 O`, e o PDF também tem `023074 O`. O `ARQUIVO_RE` não casa, a categoria fica vazia e a patente é descartada. | `[62] categoria fora do mapa: (vazia)` | Normalizar `O`/`o` para `0` **só na posição de dígito** do número BR (pasta e nome do arquivo). O número publicado fica `BR 10 2013 023074-0`. |
| P3 | **Título quebrado no meio da palavra** no próprio PDF ("…Propanoiloxiestemodan" / "o (SM-2)"). O build junta com espaço e gera "…estemodan o (SM-2)". | ID 87 | Se o título do PDF e o do nome do arquivo forem **iguais ignorando só os espaços**, usar o do arquivo. Regra exata em 3.4. |
| P4 | **O build grava `patentes.js` mesmo quando há erro.** No teste com uma pasta inválida, ele escreveu um `patentes.js` com **0 patentes** e só depois saiu com código 1. Rodado no repositório com o `--src` errado, ele **apaga a vitrine**. | `patentes.js ....... atualizado` + `ERROS` | Só gravar `patentes.js` e `build_report.md` de produção se **erros == 0** (3.5). |
| P5 | **Cache de 7 dias no JS** (`vercel.json`: `/(css|js)/(.*)` → `max-age=604800`). Isso inclui `js/data/patentes.js`: quem já visitou o site pode ficar **até 7 dias sem ver as 33 novas**. | `vercel.json` atual | Regra específica para `js/data/` com revalidação (Fase 4). |

### 2.3 Problema de conteúdo nas fichas (**PERGUNTAR** ao usuário)

**Seis PDFs do lote têm texto copiado de outra ficha.** O título é diferente, mas as seções (O que é?, Problema, Exemplo de uso, Diferenciais e Benefício) são **idênticas, palavra por palavra**:

| Grupo | IDs | Títulos | Texto repetido ("O que é?") |
|---|---|---|---|
| A | 67, 68, 69, 87 | Produto Analgésico de um Derivado Semi-Sintético de Benzil-Isotiocianato · Produto Analgésico · Produto Analgésico do Composto MCD9… · Uso Analgésico do Derivado 13-Hidroxi-2a-Propanoiloxiestemodano (SM-2) | "Um produto analgésico desenvolvido a partir da biodiversidade brasileira, formulado para aliviar a dor com mais segurança e sustentabilidade." |
| B | 73, 92 | Produto para o tratamento de perda óssea · Emulgel à Base de Nitrocumarina para o Tratamento da Periodontite | "Um produto inovador para tratar perda óssea e perdas dentárias na periodontia, desenvolvido a partir da biodiversidade brasileira." |

Isso é um problema **das fichas**, não do código. Pode ser intencional (patentes da mesma família tecnológica) ou um erro de diagramação no Canva.

- **Padrão (DECISÃO):** inserir as 33 como estão, porque o PDF é a fonte oficial. Registrar o grupo no relatório (3.6) e **avisar o usuário no resumo final**.
- **PERGUNTAR antes do commit:** "6 fichas têm texto idêntico ao de outras (grupos A e B). Publicar assim, ou esperar fichas corrigidas da UFC Inova?" Se o usuário pedir para segurar, publicar as **outras 27** e deixar essas 6 de fora, usando a lista de exclusão (3.3).

### 2.4 Outros detalhes do lote (tratados automaticamente)
- O prefixo dos arquivos (`040.`, `023.`, `002.`…) é a numeração de um portfólio antigo. **Ignorar**: o ID vem do registro (3.2).
- Imagens com nome só de número (`40.png`, `23.png`…). A capa é encontrada **pela extensão**, como já acontece hoje.
- Espaço duplo ("Aplicador Inovador  de Anestesia") é normalizado pelo `normaliza_espacos`.
- Uma capa de 7,4 MB / 2048 px (ID 86) é reduzida para 800 px como as outras.
- Travessão no título ("Tea Desestressa – Bebida Funcional Natural"): manter, porque as fontes cobrem esse caractere.

---

## 3. Especificação das mudanças em `scripts/build_patentes.py`

### 3.1 Várias pastas de origem
- `--src` passa a aceitar **várias pastas** (`action="append"`), na ordem informada:
  ```
  python scripts/build_patentes.py ^
    --src "C:\Users\Usuario\Documents\50 Patentes Observatório-20260924T152758Z-1-001\50 Patentes Observatório" ^
    --src "C:\Users\Usuario\Documents\comparação de patentes\patente 3" ^
    --out .
  ```
- Rodar com só a pasta antiga continua funcionando exatamente como hoje.
- O mesmo número BR em duas pastas diferentes é **erro** ("número duplicado em <pasta1> e <pasta2>").

### 3.2 Registro de IDs: `dados/ids_patentes.json` (novo, versionado)
O ID define a URL (`patente.html?id=N`), então ele **nunca pode mudar** depois de publicado.

```json
{
  "versao": 1,
  "observacao": "ID permanente de cada patente (numero INPI normalizado -> id). Nunca reutilizar nem renumerar.",
  "ids": {
    "BR 10 2014 030019-8": 1,
    "...": "...",
    "BR 10 2013 001855-4": 61
  }
}
```
Regras:
1. **Pasta com prefixo** (`19. BR …`): o ID é o do prefixo, como hoje. Se o número já estiver no registro com **outro** ID, é **erro**.
2. **Pasta sem prefixo**: o ID vem do registro. Se o número não estiver lá, recebe um **ID novo = maior ID do registro + 1**. Quando houver várias pastas novas de uma vez, a atribuição segue a ordem do **número BR** (espécie, ano, sequencial), o que é determinístico.
3. Na primeira execução, o registro é **criado** com os 60 IDs atuais (lidos das pastas com prefixo) mais os 33 novos.
4. O registro só é gravado se o build terminar **sem erros** (mesma regra da 3.5).
5. **IDs esperados para este lote** (o teste da Fase 3 confere um por um): ver o Anexo A.

### 3.3 Lista de exclusão: `dados/excluir.json` (novo, opcional)
```json
{ "versao": 1, "numeros": [] }
```
Números listados aqui são pulados pelo build (aparecem no relatório como "excluído por decisão"), mas **mantêm o ID no registro**. Fica vazio, a menos que o usuário peça para segurar o grupo A ou B (2.3).

### 3.4 Normalizações novas
- **Número BR (P2):** antes de aplicar `PASTA_RE` e `ARQUIVO_RE`, trocar `O`/`o` por `0` **somente** quando aparecem no lugar de um dígito dentro do padrão `BR XX AAAA NNNNNN D`. Use uma função `normaliza_numero_bruto()` com teste unitário. Registrar um **aviso** "dígito com letra O corrigido para 0" no relatório.
- **Título (P3):** depois da lógica atual de escolha do título, aplicar:
  ```python
  if titulo_pdf and titulo_arquivo and titulo != titulo_arquivo \
     and titulo.replace(" ", "") == titulo_arquivo.replace(" ", ""):
      titulo = titulo_arquivo   # PDF quebrou uma palavra no meio da linha
      res.avisos.append(f"[{pid}] titulo do PDF com palavra partida; usando o do arquivo.")
  ```
  A comparação **diferencia maiúsculas** de propósito. Assim o caso da patente 52 (nome do arquivo em MAIÚSCULAS) continua usando o título do PDF.

### 3.5 Gravação só sem erros (P4)
- Se `res.erros` não estiver vazio: **não** gravar `js/data/patentes.js` nem `dados/ids_patentes.json`. Gravar o relatório como `scripts/build_report_FALHOU.md`, imprimir os erros e sair com código 1.
- Assets das patentes válidas podem ser gerados (são idempotentes), mas nenhuma pasta de `assets/patentes/` é apagada quando há erro.

### 3.6 Relatório (`scripts/build_report.md`)
Acrescentar:
- a lista das **pastas de origem** e a contagem por pasta;
- a seção **"Fichas com texto idêntico"**: agrupar as patentes cujo objeto `secoes` é igual (comparação exata) e listar os IDs e títulos. Isso não é erro, é aviso;
- a seção **"IDs atribuídos neste build"**: número → ID das patentes novas.

Os `.docx`/`.xlsx` continuam aparecendo em "Arquivos ignorados".

### 3.7 O que NÃO muda
- O formato de `window.PATENTES` e `window.CATEGORIAS`, a estrutura de `assets/patentes/<slug>/` (capa-400/800, ficha-600/1620, ficha.pdf) e o HTML, CSS e JS do site. O site já calcula contadores, filtros, navegação anterior/próxima e as relacionadas a partir de `window.PATENTES`, então as 93 aparecem sem tocar no front.

---

## 4. Regressão: as 60 atuais não podem mudar

Antes de qualquer alteração (Fase 0), salvar um **snapshot** em `%TEMP%\vitrine_snapshot\` (fora do repositório):
- `js/data/patentes.js`;
- o SHA-256 de todos os arquivos em `assets/patentes/**`.

Critérios, depois de rodar o build com as duas pastas:
1. Os objetos de **ID 1 a 60** em `window.PATENTES` são **idênticos** aos do snapshot (comparar com `JSON.stringify` objeto a objeto).
2. **Nenhum** arquivo de `assets/patentes/` das patentes 1–60 mudou de hash.
3. `git status` mostra como alterados **apenas**: `js/data/patentes.js`, `scripts/build_report.md`, `scripts/build_patentes.py`, os arquivos novos em `dados/`, as 33 pastas novas em `assets/patentes/`, `vercel.json` e `README.md`.

Se o item 1 ou 2 falhar (por exemplo, por versão diferente de PyMuPDF ou Pillow gerando bytes diferentes), **pare e mostre o diff ao usuário**. Não faça commit de mudanças nas 60 antigas sem aprovação explícita.

---

## 5. Cache na Vercel (P5)

No `vercel.json`, trocar a regra única de CSS/JS por regras que não pegam `js/data/`:
```json
{ "source": "/css/:arquivo",      "headers": [{ "key": "Cache-Control", "value": "public, max-age=604800" }] },
{ "source": "/js/:arquivo",       "headers": [{ "key": "Cache-Control", "value": "public, max-age=604800" }] },
{ "source": "/js/data/:arquivo",  "headers": [{ "key": "Cache-Control", "value": "public, max-age=0, must-revalidate" }] }
```
`:arquivo` casa com **um** segmento de caminho, então `/js/:arquivo` não pega `/js/data/patentes.js`. Mantenha as outras regras como estão: as capas novas têm slugs novos e não sofrem com o cache de 30 dias.

Validação depois do deploy (Fase 6):
```
curl -sI https://vitrinetecnologicaufc.vercel.app/js/data/patentes.js | findstr /i cache-control
→ cache-control: public, max-age=0, must-revalidate
curl -sI https://vitrinetecnologicaufc.vercel.app/js/home.js | findstr /i cache-control
→ cache-control: public, max-age=604800
```

---

## 6. Testes (obrigatórios antes do commit)

### 6.1 Unitários do build (pytest, em `scripts/tests/test_build.py`, sem precisar do acervo real)
- `normaliza_numero_bruto("BR 10 2013 023074 O")` → `"BR 10 2013 023074 0"`, e não altera letras fora do número.
- Regra de título: "…estemodan o (SM-2)" vs "…estemodano (SM-2)" → usa o do arquivo; "COMPOSIÇÃO E USO…" (arquivo) vs "Composição e uso…" (PDF) → mantém o do PDF.
- Registro de IDs: novo número recebe max+1; ordem determinística por número BR; prefixo conflitando com o registro → erro; número duplicado entre pastas → erro.
- Build com erro **não grava** `patentes.js` (rodar com `--out` numa pasta temporária que já tenha um `patentes.js` e conferir que ele não mudou).
- Pasta contendo `.docx` e `.xlsx` → ignorados e listados no relatório; nenhum é copiado para `assets/`.

### 6.2 Dados gerados
- `PATENTES.length === 93`, IDs de 1 a 93 sem buracos nem repetições; `CATEGORIAS` com 10 áreas cuja soma dá 93.
- Para os IDs 61–93: título, número, categoria, tipo e TRL batem com o Anexo A; todo caminho de `imagens.*` e `pdf` existe **com a grafia exata** (conferir maiúsculas/minúsculas, porque a Vercel roda em Linux).
- O relatório tem 0 erros. Avisos esperados: 1 de "letra O corrigida" (ID 62), 1 de "palavra partida no título" (ID 87) e a seção de texto idêntico com os grupos A e B.
- Regressão da seção 4 aprovada.

### 6.3 Site (navegador, servindo a pasta com `python -m http.server 4173`)
- Home: **93 cards**; contadores do hero: 93 patentes · 10 áreas · 89 PI · 4 MU; chips de área com os novos totais (por exemplo, Ciências da Saúde 17 e Engenharias 17).
- Busca: "periapical" → ID 93; "023074" → ID 62; "palma" → ID 66; sem acento: "fitoterapico" → ID 63.
- Filtros: "Ciências da Saúde" + "PI" e ordenação "Mais recentes" (as de 2025 aparecem primeiro).
- Prévia no hover dos cards 61, 87 e 93 (desktop ≥ 1024 px): a imagem da ficha carrega.
- Detalhe de **todas as patentes de 61 a 93**: H1 correto, capa e ficha carregam, "Baixar PDF" responde 200, e o lightbox abre e fecha.
- Navegação circular: em `?id=93`, "Próxima" leva à 1; em `?id=61`, "Anterior" leva à 60.
- Console sem erros e 404 funcionando (`/qualquer/coisa`).

---

## 7. Fases de implementação

| Fase | O que fazer | Porta de saída |
|---|---|---|
| **0. Preparação** | `git pull`; confirmar que as duas pastas de origem existem; snapshot (seção 4); `pip install pymupdf pillow pytest` e registrar as versões no relatório | Snapshot salvo |
| **1. Build** | Mudanças da seção 3 (várias `--src`, registro de IDs, exclusões, normalizações, gravação só sem erro, relatório) | Testes 6.1 passando |
| **2. Gerar** | Rodar o build com as duas pastas | 0 erros; avisos = os esperados (6.2) |
| **3. Conferir dados** | Validar o Anexo A e a regressão da seção 4 | 6.2 completo |
| **4. Cache** | Ajustar o `vercel.json` (seção 5) | JSON válido |
| **5. Site** | Testes 6.3 | Todos ok |
| **6. Publicar** | **PERGUNTAR** sobre os grupos A e B (2.3) → commit → push → validar o cache (seção 5) e abrir 3 patentes novas no endereço publicado | Site com 93 patentes no ar |
| **7. Documentar** | README: novo comando de build com dois `--src`, o registro de IDs, a lista de exclusão e "como inserir um lote novo" | — |

**Commits sugeridos** (separados, para facilitar a revisão e um eventual revert):
1. `build: aceita varias pastas de origem e registro permanente de IDs`
2. `build: normaliza digito O->0, corrige titulo partido e nao grava dados com erro`
3. `dados: insere 33 patentes do lote "patente 3" (IDs 61-93)`
4. `vercel: revalida js/data a cada visita`
5. `docs: como inserir um lote novo de patentes`

---

## 8. Critérios de aceite
1. A vitrine publicada mostra **93 patentes** (ou 87, se o usuário decidir segurar os grupos A e B), com os IDs do Anexo A.
2. As patentes 1–60 estão inalteradas (dados e assets).
3. Nenhum `.docx`/`.xlsx` do lote foi lido, copiado ou publicado.
4. As pastas de origem continuam intactas (mesma listagem e mesmos tamanhos de antes).
5. `patentes.js` é revalidado a cada visita na Vercel.
6. O build não grava mais dados quando há erro.
7. README atualizado.

---

## Anexo A — Mapeamento do lote (IDs atribuídos pela ordem do número BR)

| ID | Número (normalizado) | Área | Título | TRL |
|---|---|---|---|---|
| 61 | BR 10 2013 001855-4 | Engenharias | Estabilidade Térmica de Materiais Avançados | 4 |
| 62 | BR 10 2013 023074-0 ⚠ letra O no original | Ciências da Saúde | Aplicador Inovador de Anestesia Odontológica | 6 |
| 63 | BR 10 2014 031982-4 | Ciências da Saúde | Fitoterápico: Cicatrização de feridas | 9 |
| 64 | BR 10 2015 029772-6 | Engenharias | Sensor Óptico de Corrente | 7 |
| 65 | BR 10 2016 016795-7 | Química | Nanopartículas Lipídicas para Aplicação Teranóstica | 4 |
| 66 | BR 10 2016 023223-6 | Agropecuária | Fatiadora de Palma Forrageira | 7 |
| 67 | BR 10 2016 030476-8 | Ciências da Saúde | Produto Analgésico de um Derivado Semi-Sintético de Benzil-Isotiocianato ⚠ A | 4 |
| 68 | BR 10 2016 030480-6 | Ciências da Saúde | Produto Analgésico ⚠ A | 4 |
| 69 | BR 10 2016 030484-9 | Ciências da Saúde | Produto Analgésico do Composto MCD9, Benzil-Isotiocianato Glicosilado ⚠ A | 4 |
| 70 | BR 10 2017 007569-9 | Engenharias | Compósito de Niobato de Ítrio e Titanato de Cálcio | 4 |
| 71 | BR 10 2017 012086-4 | Engenharias | Compósito de Vanadato de Estrôncio e Óxido de Bismuto | 4 |
| 72 | BR 10 2018 000974-5 | Engenharias | Compósito Cerâmico de Titânico de lítio e Óxido de Alumínio | 4 |
| 73 | BR 10 2018 073535-7 | Ciências da Saúde | Produto para o tratamento de perda óssea ⚠ B | 4 |
| 74 | BR 10 2019 016050-0 | Alimentos | Bebida Vegetal Funcional | 9 |
| 75 | BR 10 2019 020946-1 | Biotecnologia | Processo Biocatalítico para Produção de Propafenona | 4 |
| 76 | BR 10 2020 015725-6 | Alimentos | Molho de Frutas Amarelas | 4 |
| 77 | BR 10 2020 021723-2 | Alimentos | VitalFlakes Amazônia Snack Natural e Energético | 4 |
| 78 | BR 10 2021 012762-7 | Ciências da Saúde | Biocurativo para Tratamento de Feridas | 4 |
| 79 | BR 10 2023 004857-9 | Ciências da Saúde | Nanoformulação para Tratamento da Leishmaniose | 4 |
| 80 | BR 10 2023 011275-7 | Alimentos | Tea Desestressa – Bebida Funcional Natural | 4 |
| 81 | BR 10 2023 011512-8 | Ciências da Saúde | Nanoemulsão com Efeitos Múltiplos | 4 |
| 82 | BR 10 2023 019624-1 | Química | Fórmula Natural e Seletiva para Tratar o Câncer de Próstata | 3 |
| 83 | BR 10 2023 019926-7 | Ciências da Saúde | Gel Bucal Inovador para Tratamento de Osteonecrose | 4 |
| 84 | BR 10 2023 021438-0 | Alimentos | Gel Energético de Carboidratos | 5 |
| 85 | BR 10 2023 023821-1 | Ciências da Saúde | Enxaguante Bucal e Curativo para Saúde Bucal e de Pele | 4 |
| 86 | BR 10 2023 023864-5 | Agropecuária | Método para Avaliação de Solos Coesos | 3 |
| 87 | BR 10 2024 007891-8 | Ciências da Saúde | Uso Analgésico do Derivado 13-Hidroxi-2a-Propanoiloxiestemodano (SM-2) ⚠ A, título partido no PDF | 4 |
| 88 | BR 10 2024 018749-0 | Agropecuária | Dispositivo para Transporte de Animais Vivos | 5 |
| 89 | BR 10 2024 019064-5 | Energia e Meio Ambiente | Caracterização Espectral de Solos Coesos | 3 |
| 90 | BR 10 2025 001276-6 | Cosméticos | Tecnologia Clareadora com Captopril | 3 |
| 91 | BR 10 2025 014098-5 | Engenharias | Dispositivos para Processamento Avançado | 4 |
| 92 | BR 10 2025 014453-0 | Biotecnologia | Emulgel à Base de Nitrocumarina para o Tratamento da Periodontite ⚠ B | 4 |
| 93 | BR 10 2025 014465-4 | Ciências da Saúde | Gel com Cinamaldeído para Tratamento de Lesão Periapical | 4 |

Os títulos são os extraídos do PDF no teste. Os da 62 e da 87 são os esperados **depois** das correções P2 e P3. Todas as 33 são **Patente de Invenção (BR 10)**, e nenhuma é Modelo de Utilidade.

**Totais esperados por área depois da inserção** (60 atuais + 33 novas):

| Área | Antes | Novas | Depois |
|---|---|---|---|
| Agropecuária | 16 | 3 | 19 |
| Alimentos | 15 | 5 | 20 |
| Biotecnologia | 4 | 2 | 6 |
| Ciências da Saúde | 4 | 13 | 17 |
| Cosméticos | 2 | 1 | 3 |
| Energia e Meio Ambiente | 1 | 1 | 2 |
| Engenharias | 11 | 6 | 17 |
| Indústria | 2 | 0 | 2 |
| Química | 3 | 2 | 5 |
| TIC | 2 | 0 | 2 |
| **Total** | **60** | **33** | **93** |
