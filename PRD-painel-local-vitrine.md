# PRD — Painel Local de Administração da Vitrine de Patentes UFC

> **Para o Claude Code:** este PRD complementa o site que já existe em `C:\Users\Usuario\Desktop\vitrinePI_site`. **Leia o `README.md` do projeto e este documento inteiros antes de escrever código.** Siga as fases da seção 14 **na ordem**. Não avance de fase com teste falhando. Onde estiver escrito **PENDENTE**, pergunte ao usuário. Quando uma decisão de segurança da seção 5 conflitar com conveniência, **a segurança vence**: se não houver como atender as duas, pare e pergunte.

| Campo | Valor |
|---|---|
| Produto | Painel Local da Vitrine de Patentes (aplicativo desktop para Windows) |
| Usuários | Equipe da UFC Inova (não técnicos) |
| Repositório | `C:\Users\Usuario\Desktop\vitrinePI_site` (remote `github.com/LemosSilveira/VitrineTecnologica_UFC`, branch `main`) |
| Stack do painel | Python 3.12 + pywebview 5 (WebView2) + HTML/CSS/JS puro + PyInstaller |
| Versão do PRD | 1.0 (29/09/2026) |

---

## 1. Contexto e objetivo

### 1.1 Situação atual
- O site é **estático**: `index.html`, `patente.html` e `404.html`, com CSS em `css/tokens.css`, `base.css`, `components.css` e `pages.css`, e JS clássico em `js/ui.js`, `home.js` e `patente.js`.
- Os dados ficam em `js/data/patentes.js` (`window.PATENTES` e `window.CATEGORIAS`), **gerado** por `scripts/build_patentes.py` a partir da pasta de origem (o "acervo"):
  `C:\Users\Usuario\Documents\50 Patentes Observatório-20260924T152758Z-1-001\50 Patentes Observatório`
- Para adicionar uma patente hoje, alguém cria uma pasta no padrão `N. BR XX AAAA NNNNNN D`, coloca o PDF e a imagem com o nome no padrão certo e roda o build pelo terminal. Isso é inviável para a equipe não técnica.

### 1.2 Objetivo
Um **aplicativo que a equipe da UFC Inova abre com dois cliques** e que permite:
1. **cadastrar uma patente nova** de duas formas:
   - **automática:** a pessoa arrasta, cola (Ctrl+V) ou escolhe o PDF da ficha, e o formulário se preenche sozinho;
   - **manual:** a pessoa preenche o formulário;
2. **editar** uma patente existente, **ocultá-la** da vitrine ou **enviá-la para a lixeira**, sem apagar nada de verdade;
3. ver uma **prévia real** (card, prévia do hover e página de detalhe) antes de salvar;
4. **regerar a vitrine** (rodar o build) e ver o relatório de forma legível;
5. **gerar o pacote de publicação** (um `.zip` só com os arquivos públicos);
6. consultar o **histórico** de alterações e **restaurar** um backup.

### 1.3 Princípio de segurança do produto
**Não há login, e por isso o painel não fica acessível pela rede.** A fronteira de segurança é a conta do Windows de quem usa o computador. Por isso o painel:
- **não abre porta de rede para a API**: a comunicação entre a interface e o Python é feita pela ponte interna do pywebview, não por HTTP;
- **nunca é publicado**: o pacote de publicação é montado por uma lista de permissões, e a pasta do painel fica fora dela;
- **desconfia de todo arquivo e de todo texto recebido**, mesmo vindo da própria equipe.

### 1.4 Fora do escopo (v1)
- Acesso remoto, múltiplos usuários simultâneos ou login.
- Publicação automática no servidor ou `git push` (a v1 gera o `.zip`; ver 13.2).
- Gerar o PDF da ficha a partir do formulário (fica para a v2).
- macOS e Linux (o código não deve impedir, mas o executável e os testes são só para Windows).

---

## 2. Achados no código atual (resolver na Fase 0)

| # | Achado | Ação |
|---|---|---|
| A1 | O README descreve a pasta `tests/` (Playwright + axe), mas **ela não existe** no projeto. | Rodar `git log --all -- tests/` e restaurar se estiver no histórico. Se não estiver, recriar ao menos os testes de regressão da home, do detalhe e da 404 **antes** de refatorar (Fase 0). |
| A2 | **Não existe `.gitignore`.** | Criar (ver 11.3). |
| A3 | Arquivo solto `19,47,52` na raiz (listagem do acervo, provavelmente criada sem querer). Seria publicado. | Confirmar com o usuário e remover. |
| A4 | `ficha.pdf` é uma **cópia byte a byte** do PDF de origem (`write_if_changed(destino / "ficha.pdf", pdf_src.read_bytes())`). PDFs podem ter JavaScript, anexos, formulários e metadados (nome do autor, caminhos de pasta). | Publicar sempre uma versão **higienizada** do PDF (5.4). |
| A5 | `CATEGORIA_MAP` é fixo no código do build. | Passar para `dados/categorias.json`, editável pelo painel (6.3). |
| A6 | A lógica do build está toda num script de CLI e não pode ser importada pelo painel. | Refatorar em um pacote reutilizável, **mantendo a saída idêntica** (Fase 1). |
| A7 | `htmlCard` fica dentro de `home.js`, e `htmlTrl`, `htmlSecao` e `htmlDiferenciais` dentro de `patente.js`. | Extrair para `js/render.js`, compartilhado entre o site e a prévia do painel (6.5). |
| A8 | O `.htaccess` não tem Content-Security-Policy nem bloqueio de pastas internas. | Endurecer (6.6). |

---

## 3. Arquitetura

### 3.1 Visão geral
```
┌──────────────────────── PainelVitrine.exe (Windows) ─────────────────────────┐
│                                                                              │
│  Janela pywebview (WebView2)                 Python (processo do app)        │
│  ┌──────────────────────────────┐   ponte   ┌─────────────────────────────┐  │
│  │ admin/ui  (HTML/CSS/JS puro) │◄─js_api───►│ painel.api.Api              │  │
│  │  usa tokens/base/components  │  (sem HTTP)│  → validacao                │  │
│  │  + js/render.js do site      │            │  → armazenamento (acervo)   │  │
│  └──────────────────────────────┘            │  → vitrine_core (build)     │  │
│                                              │  → publicacao, auditoria    │  │
│                                              └─────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
           lê/escreve (só o painel escreve)          lê/escreve
   Acervo (pasta de origem)  ◄─────────────►  Site (vitrinePI_site)
   N. BR XX .../ ficha.pdf, capa, patente.json    js/data/patentes.js, assets/patentes/...
```

### 3.2 Por que pywebview, e não um servidor Flask no navegador
- **Sem porta de API:** as chamadas do JS para o Python passam pela ponte `window.pywebview.api`, dentro do processo. Nenhum site aberto no navegador da pessoa consegue enviar requisições para o painel (isso elimina CSRF e DNS rebinding).
- **Parece um aplicativo:** janela própria, ícone na barra de tarefas e nenhuma aba de navegador para fechar por engano.
- **Seletor de arquivos nativo do Windows**, com `window.create_file_dialog`.
- O pywebview usa um servidor HTTP interno **só para servir os arquivos estáticos da interface** (`admin/ui`), preso em `127.0.0.1`, somente leitura e sem nenhum dado. Isso é aceitável, e a seção 12.4 verifica.

### 3.3 Dependências (versões fixadas **com hash**)
`admin/requirements.txt`, instalado com `pip install --require-hashes -r admin/requirements.txt`:
- `pywebview` 5.x (backend EdgeChromium / WebView2)
- `pymupdf` (já usado no build)
- `pillow` (já usado no build)
- `pyinstaller` (só em `admin/requirements-dev.txt`)
- `pytest` (só em dev)

**Nenhuma outra dependência de runtime.** Nada de CDN na interface: tudo é local.

### 3.4 Estrutura de pastas (o que muda no repositório)
```
vitrinePI_site/
├── .gitignore                    # NOVO (11.3)
├── .htaccess                     # ALTERADO (6.6)
├── index.html / patente.html     # ALTERADOS: incluem js/render.js
├── js/
│   ├── render.js                 # NOVO: htmlCard, htmlTrl, htmlSecao, htmlDiferenciais (6.5)
│   ├── home.js / patente.js      # ALTERADOS: usam window.RENDER
│   └── ...
├── dados/
│   └── categorias.json           # NOVO: mapa de categorias (antes fixo no build)
├── scripts/
│   ├── build_patentes.py         # vira uma CLI fina: mesma interface de linha de comando
│   └── vitrine_core/             # NOVO pacote reutilizável
│       ├── __init__.py
│       ├── nomes.py              # regex de pasta/arquivo, slug, nomes seguros
│       ├── extracao.py           # titulo_do_pdf, secoes_do_pdf, parse_trl, ler_ficha()
│       ├── imagens.py            # capas, render da ficha, validação de imagem
│       ├── pdf_seguro.py         # validação e higienização de PDF (5.4)
│       ├── acervo.py             # leitura das pastas + patente.json (4.2)
│       ├── build.py              # build completo → patentes.js + relatório
│       └── io_seguro.py          # escrita atômica, write_if_changed, verificação de caminho
├── admin/                        # NOVO — NUNCA publicado
│   ├── painel/
│   │   ├── __main__.py           # ponto de entrada: python -m painel
│   │   ├── app.py                # cria a janela, instância única, checa WebView2
│   │   ├── api.py                # classe Api exposta ao JS (superfície mínima, 5.3)
│   │   ├── validacao.py          # regras dos campos (seção 8)
│   │   ├── armazenamento.py      # quarentena, gravação no acervo, lixeira
│   │   ├── backup.py             # backups e restauração
│   │   ├── auditoria.py          # log JSON Lines
│   │   ├── publicacao.py         # pacote .zip por lista de permissões
│   │   └── config.py             # %APPDATA%\PainelVitrine\config.json
│   ├── ui/
│   │   ├── index.html            # SPA simples com roteamento por hash (#/lista, #/nova…)
│   │   ├── painel.css            # SÓ os componentes novos (7.4); o resto vem do site
│   │   ├── painel.js             # roteamento, telas, estado
│   │   ├── api-cliente.js        # único ponto que chama window.pywebview.api
│   │   └── site/                 # CÓPIA gerada de css/*.css, js/ui.js, js/render.js, fontes e logo
│   ├── sincroniza_site.py        # copia os arquivos do site para admin/ui/site (dev e empacotamento)
│   ├── painel.spec               # configuração do PyInstaller
│   ├── build_exe.ps1             # gera dist/PainelVitrine/
│   ├── icone.ico                 # quadrado roxo (o "pingo" do i)
│   ├── requirements.txt / requirements-dev.txt
│   └── MANUAL.md                 # manual de uso para a equipe (linguagem simples)
└── tests/
    ├── (testes do site, restaurados ou recriados, A1)
    ├── core/                     # pytest: vitrine_core
    ├── painel/                   # pytest: API, validação, armazenamento, publicação
    ├── seguranca/                # pytest: arquivos maliciosos, caminhos, pacote
    ├── fixtures/                 # PDFs e imagens de teste (válidos e maliciosos)
    └── painel-ui/                # Playwright: interface com a API simulada (mock-api.js)
```

**Pastas fora do repositório (por computador):**
```
%APPDATA%\PainelVitrine\
├── config.json          # pastaSite, pastaAcervo, versão
├── auditoria.log        # histórico (JSON Lines)
└── backups\AAAA-MM-DD_HHMMSS_<acao>_<id>\
%LOCALAPPDATA%\PainelVitrine\
├── quarentena\<uuid>\   # arquivos recebidos, antes de validar e salvar
├── pacotes\             # .zip de publicação gerados
└── painel.lock          # trava de instância única
```

---

## 4. Modelo de dados

### 4.1 Fonte da verdade
**O acervo continua sendo a fonte da verdade.** Cada patente é uma pasta. O painel é o **único** que escreve no acervo, e o build **só lê** (regra que já está no README e continua valendo).

### 4.2 Conteúdo de uma pasta do acervo
```
61. BR 10 2025 012345 6/
├── 61. Engenharias - BR 10 2025 012345 6 - Título curto.pdf   # opcional (ver 4.4)
├── 61. Engenharias - BR 10 2025 012345 6 - Título curto.png   # obrigatório (capa)
└── patente.json                                              # opcional; criado pelo painel
```
- Para as **60 pastas atuais**, nada muda até alguém editar a patente pelo painel. A partir daí, ela ganha um `patente.json`.
- Nomes de arquivo gerados pelo painel seguem o padrão já reconhecido pelo `ARQUIVO_RE`, com o título **cortado em 80 caracteres** no nome do arquivo (limite de caminho do Windows). O título completo fica no `patente.json`.

### 4.3 `patente.json` (sobreposição, validada por esquema)
```json
{
  "versao": 1,
  "oculta": false,
  "campos": {
    "titulo": "Título corrigido pela equipe",
    "categoria": "Engenharias",
    "secoes": {
      "oQueE": "…",
      "problema": "…",
      "exemploDeUso": "…",
      "diferenciais": ["…", "…"],
      "beneficio": "…"
    },
    "trl": { "min": 5, "max": 6, "estimado": true }
  },
  "atualizadoEm": "2026-09-29T14:02:11-03:00",
  "atualizadoPor": "usuario.windows"
}
```
Regras do merge no build:
- A ordem de prioridade é **`patente.json` › texto do PDF › nome do arquivo**, campo a campo. Só os campos presentes em `campos` sobrepõem.
- `numero`, `ano`, `tipo` e `id` **sempre** vêm do nome da pasta, que é imutável depois de criada. Se o número tiver sido digitado errado, o caminho é: patente nova, antiga para a lixeira.
- `oculta: true` → a patente **não entra** em `patentes.js` nem em `assets/patentes/`. O build remove a pasta de assets dela se existir. Ocultar no cliente não basta: o dado não pode ir para o ar.
- `trl.texto` e `resumo` são sempre **recalculados** pelo build, nunca lidos do JSON.
- O JSON é validado por um esquema escrito à mão em `vitrine_core/acervo.py` (tipos, campos permitidos, tamanhos da seção 8). **Campos desconhecidos geram erro.** Um JSON inválido é **erro** no relatório, e a patente fica de fora.

### 4.4 Patente sem PDF (cadastro manual)
- Permitida quando o `patente.json` traz `titulo`, `categoria` e `secoes.oQueE`. O build registra um **aviso** (não erro), e no item gerado ficam `pdf: null`, `imagens.ficha600: null` e `imagens.ficha1620: null`.
- O site precisa lidar com esses nulos (6.4).

### 4.5 IDs
- ID novo = **maior ID já usado + 1**, contando também a lixeira. **IDs nunca são reaproveitados**, porque as URLs `patente.html?id=N` precisam continuar estáveis.

### 4.6 Lixeira
- "Excluir" no painel **move** a pasta para `<acervo>\_lixeira\<pasta>__AAAAMMDD-HHMMSS\`. O build ignora pastas que começam com `_` ou `.`.
- Esvaziar a lixeira não existe na v1. Isso é intencional.

### 4.7 Categorias (`dados/categorias.json`)
```json
{
  "versao": 1,
  "mapa": { "alimentos": "Alimentos", "quimico": "Química", "quimicos": "Química", "...": "..." }
}
```
Tem o mesmo conteúdo do `CATEGORIA_MAP` atual. O build lê daqui. O painel permite **adicionar** uma área (com confirmação e registro na auditoria), mas não renomear nem remover áreas na v1.

---

## 5. Segurança (requisitos obrigatórios)

### 5.1 Modelo de ameaças
| # | Ameaça | Mitigação |
|---|---|---|
| T1 | Um site aberto no navegador tenta falar com o painel (CSRF, DNS rebinding) | **Sem API HTTP**: só a ponte do pywebview. O servidor estático do pywebview só serve `admin/ui` (5.6). |
| T2 | Outra máquina da rede acessa o painel | Nenhum socket escutando fora de `127.0.0.1`. Verificado com `netstat` no teste de fumaça (12.4). |
| T3 | Um conteúdo externo carregado dentro da janela chama `window.pywebview.api` | A janela **nunca navega para fora** da interface local: CSP restritiva, bloqueio de navegação e links externos abertos no navegador padrão, com lista de permissões (5.6). |
| T4 | Arquivo malicioso ou malformado (bomba de descompressão, poliglota, PDF com JavaScript, PDF criptografado, arquivo enorme) | Quarentena + validação pelo conteúdo + limites + **reencodar imagens** + **higienizar PDF** (5.4, 5.5). |
| T5 | Path traversal e nomes perigosos (`..\`, `CON`, caminho > 260 caracteres) | O nome do arquivo recebido **nunca** é usado. Nomes gerados pelo painel e confinamento de caminho (5.7). |
| T6 | XSS no site público a partir de texto digitado no painel | Texto guardado como texto puro. O build já escapa com `js_string`, e o site escapa com `UI.esc`: auditar **todos** os pontos de renderização. Adicionar CSP no site (6.6). |
| T7 | Perda ou corrupção de dados (queda de energia, duas instâncias, erro humano) | Escrita atômica, backup antes de cada alteração, instância única, lixeira em vez de exclusão, restauração pelo histórico (5.8). |
| T8 | Publicar por engano o painel, os scripts, o acervo, os backups ou o `.git` | Pacote por **lista de permissões** + `.gitignore` + regras no `.htaccess` + teste automatizado do conteúdo do zip (5.9). |
| T9 | Dependência comprometida (supply chain) | Versões fixadas com hash, nenhuma CDN e build do exe reprodutível (5.10). |
| T10 | Pessoa não autorizada usa o computador | Fora do alcance do software: a conta do Windows é a fronteira (com senha e bloqueio de tela). O painel registra o usuário do Windows em toda ação (5.8). **Documentar no MANUAL.md.** |
| T11 | O JS da interface é manipulado (DevTools) para mandar dados inválidos | **Toda** validação é refeita no Python. A validação da interface serve só para dar feedback. DevTools desligado no build de produção. |

### 5.2 Regra de ouro
> **O Python não confia em nada que venha da interface.** Cada método da `Api` valida tipo, tamanho, formato e permissão de todos os argumentos, como se eles viessem de um atacante.

### 5.3 Superfície da API (`painel/api.py`)
O pywebview expõe **todos os métodos públicos** da classe passada em `js_api`. Por isso:
- A classe `Api` tem **apenas** os métodos listados abaixo. Toda lógica auxiliar fica em outros módulos ou em métodos que começam com `_`.
- **Um teste falha se aparecer um método público novo que não esteja nesta lista** (12.2).
- Todo método devolve `{"ok": true, "dados": ...}` ou `{"ok": false, "erro": {"codigo": "...", "mensagem": "texto para humanos", "campos": {...}}}`. **Nunca** devolve stack trace ou caminho interno para a interface; o detalhe técnico vai para o log.

| Método | Entrada | O que faz |
|---|---|---|
| `estado()` | — | Configuração válida?, contagens, alterações não publicadas, versão |
| `configurar(pasta_site, pasta_acervo)` | caminhos vindos **só** do seletor nativo | Valida (5.7) e salva a config |
| `escolher_pasta(tipo)` | `"site"` \| `"acervo"` | Abre o seletor nativo e devolve o caminho escolhido |
| `listar()` | — | Patentes do acervo, com o status de cada uma |
| `obter(id)` | int | Dados completos para edição |
| `escolher_arquivo(tipo)` | `"pdf"` \| `"capa"` | Seletor nativo → quarentena → validação → `token_arquivo` |
| `receber_arquivo(tipo, nome, base64)` | arrastar/colar | Decodifica (limite **antes** de decodificar) → quarentena → validação → `token_arquivo` |
| `ler_ficha(token_pdf)` | token | Extrai os campos do PDF (preenchimento automático, 6.2) |
| `ler_texto_ficha(texto)` | str ≤ 20.000 | Extrai os campos de um texto colado (alternativa, 6.2) |
| `previa(dados, token_capa?, token_pdf?)` | rascunho | Devolve o objeto no formato de `PATENTES[i]`, com imagens em `data:` URL, para a prévia |
| `salvar(dados, token_capa?, token_pdf?, id?)` | rascunho validado | Backup → grava no acervo → roda o build → relatório |
| `alternar_oculta(id, oculta)` | int, bool | Atualiza o `patente.json` e roda o build |
| `excluir(id, confirmacao)` | int, str igual ao número BR | Move para a lixeira e roda o build |
| `rodar_build()` | — | Build completo e relatório |
| `historico(pagina)` | int | Linhas da auditoria |
| `restaurar(id_backup, confirmacao)` | str, str | Restaura um backup (com backup do estado atual antes) |
| `gerar_pacote()` | — | Checagens + `.zip` + SHA-256 |
| `abrir_pasta(tipo)` | `"pacotes"` \| `"acervo"` \| `"site"` | Abre no Explorer (só esses três destinos) |
| `abrir_link(chave)` | `"ufcinova"` \| `"site_local"` | Abre no navegador padrão (**só** chaves conhecidas, nunca URL livre) |
| `ver_site_local()` | — | Sobe um servidor estático **somente leitura** da pasta do site em `127.0.0.1:<porta aleatória>` e o abre no navegador (para conferir a vitrine inteira) |

`token_arquivo` é um UUID4 que aponta para um arquivo já validado na quarentena, válido só durante a sessão. A interface **nunca** trabalha com caminhos do disco.

### 5.4 PDF (`vitrine_core/pdf_seguro.py`)
Validações, **nesta ordem**, antes de qualquer outra coisa:
1. Tamanho ≤ **25 MB** (checado pelo tamanho do arquivo ou do base64 **antes** de decodificar).
2. Os primeiros bytes são `%PDF-`. A extensão é ignorada.
3. Abre com PyMuPDF dentro de `try`, com tempo máximo de **15 s** (processo ou thread com timeout). Arquivo corrompido → erro amigável.
4. `doc.needs_pass` ou `doc.is_encrypted` → recusar ("PDF protegido por senha").
5. Número de páginas entre 1 e **5**. Mais de uma página gera aviso ("Só a primeira página é usada").
6. Página 1 com dimensões razoáveis (lado ≤ 5000 pt), para evitar render gigante.

**Higienização** (vale **também para o build** das 60 patentes atuais, achado A4). O `ficha.pdf` publicado é gerado assim:
```python
doc.scrub(attached_files=True, clean_pages=True, embedded_files=True,
          hidden_text=False, javascript=True, metadata=True, redactions=False,
          remove_links=False, reset_fields=True, reset_responses=True,
          thumbnails=True, xml_metadata=True)
doc.save(saida, garbage=4, deflate=True, clean=True)
```
O PDF original no acervo continua intacto. **Conferir os nomes dos parâmetros na versão instalada do PyMuPDF.** O teste de segurança (12.2) verifica que o resultado não tem `/JavaScript`, `/JS`, `/OpenAction`, `/Launch`, `/EmbeddedFile` nem metadados de autor.

> A higienização muda os bytes do `ficha.pdf` das 60 patentes uma única vez. Isso é esperado, e o teste de regressão da Fase 1 compara tudo **menos** esse arquivo. A partir daí, o build continua idempotente.

### 5.5 Imagens (`vitrine_core/imagens.py`)
1. Tamanho ≤ **15 MB**.
2. Assinatura (magic bytes) de PNG, JPEG ou WebP. Qualquer outra coisa é recusada.
3. `Image.MAX_IMAGE_PIXELS = 40_000_000`, e `DecompressionBombWarning` vira erro.
4. `Image.open()` + `verify()`, depois reabre e `load()` para decodificar de verdade.
5. Dimensões: mínimo de **400×400** (erro); menos de **800×800** gera aviso ("a capa pode ficar borrada em telas de alta resolução").
6. Imagem não quadrada: a interface oferece um **recorte 1:1** (centralizado e ajustável). O recorte é aplicado **no Python**, a partir das coordenadas validadas (inteiros dentro dos limites).
7. A imagem publicada é **sempre reencodada** em WebP pelo pipeline atual. Isso elimina metadados EXIF/GPS e qualquer conteúdo poliglota. A imagem gravada no acervo também é reencodada para PNG, sem metadados.

### 5.6 Janela e interface
- `webview.create_window(..., js_api=Api(), min_size=(1100, 720), text_select=True)`.
- `webview.start(debug=False, private_mode=True, http_server=True)` na versão de produção. `debug=True` **só** com `--dev` na linha de comando, e **nunca** no exe.
- `webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = True` e `ALLOW_DOWNLOADS = False`. Conferir as chaves na versão instalada.
- **Guarda de navegação:** em `window.events.loaded`, se `window.get_current_url()` não for a origem local da interface, voltar imediatamente para a tela inicial e registrar na auditoria. A interface não tem nenhum `<a href>` externo: links externos chamam `api.abrir_link(chave)`.
- **CSP** na `<meta>` do `admin/ui/index.html`:
  ```
  default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:;
  font-src 'self'; connect-src 'none'; frame-src 'none'; object-src 'none';
  base-uri 'none'; form-action 'none'
  ```
  Sem `innerHTML` com dado não escapado: usar `textContent` ou o `U.esc()` existente. Nenhum `eval`, `new Function` nem `onclick=""` inline.
- O servidor estático interno do pywebview serve **somente** `admin/ui/`. O teste de fumaça verifica que `GET /../js/data/patentes.js` não devolve nada e que o servidor só escuta em `127.0.0.1`.

### 5.7 Caminhos e nomes (`vitrine_core/io_seguro.py`)
- `dentro_de(raiz, caminho)`: `Path(caminho).resolve()` precisa estar **dentro** de `Path(raiz).resolve()` (`is_relative_to`). É obrigatório em **toda** operação de escrita, movimentação e leitura de arquivo feita a pedido da interface.
- Pasta do site válida = contém `index.html`, `js/data/patentes.js` e `scripts/build_patentes.py`. Pasta do acervo válida = contém ao menos uma subpasta no padrão `PASTA_RE`. Site e acervo não podem ser a mesma pasta nem uma estar dentro da outra.
- Nomes de arquivo gerados só com `[A-Za-z0-9À-ÿ .,()_-]`, sem nomes reservados do Windows (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`), sem ponto nem espaço no fim, com o título truncado em 80 caracteres e o caminho absoluto final < 240 caracteres. Se passar disso, encurtar o título no nome (o título completo fica no JSON).
- Caracteres de controle e de direção bidi (`U+202A–202E`, `U+2066–2069`) são **removidos** de todo texto recebido.

### 5.8 Integridade, backup e auditoria
- **Escrita atômica:** gravar em `arquivo.tmp` na mesma pasta → `fsync` → `os.replace`. Vale para `patente.json`, `categorias.json`, `config.json` e `patentes.js`.
- **Backup antes de toda alteração** (salvar, ocultar, excluir, restaurar, nova área): cópia da pasta da patente afetada (ou do JSON) + `js/data/patentes.js` em `%APPDATA%\PainelVitrine\backups\...`. Guardar os **50** mais recentes (os mais antigos são removidos) e nunca apagar o último de cada patente.
- **Instância única:** trava em `%LOCALAPPDATA%\PainelVitrine\painel.lock` (`msvcrt.locking`). Se uma segunda instância abrir, ela mostra a mensagem "O painel já está aberto" e fecha.
- **Auditoria** (`auditoria.log`, JSON Lines, só acrescentado, nunca reescrito):
  ```json
  {"ts":"2026-09-29T14:02:11-03:00","usuario":"<getpass.getuser()>","maquina":"<hostname>","acao":"salvar","id":61,"numero":"BR 10 2025 012345-6","resumo":"titulo, secoes.oQueE","sha256":{"pdf":"…","capa":"…"},"resultado":"ok"}
  ```
  Nada de conteúdo completo nem caminhos pessoais além do necessário.
- **Build em caso de erro:** o `patentes.js` só é reescrito se o build terminar **sem erros**. Se houver erro, o painel mostra o relatório e mantém a vitrine anterior.
- **Tratamento de exceções:** toda exceção não prevista na `Api` é capturada, registrada no log técnico (`%LOCALAPPDATA%\PainelVitrine\painel.log`, rotativo, 5 × 1 MB) e devolvida como erro genérico: "Algo deu errado. Nada foi alterado. Código: E-XXXX".

### 5.9 Pacote de publicação (`painel/publicacao.py`)
- **Lista de permissões** (nada fora dela entra no zip):
  ```
  index.html  patente.html  404.html  .htaccess
  css/**.css
  js/*.js  js/data/patentes.js
  assets/fonts/*.woff2  assets/img/*.{svg,png}
  assets/patentes/<slugs presentes em patentes.js>/{capa-400.webp,capa-800.webp,ficha-600.webp,ficha-1620.webp,ficha.pdf}
  ```
- Antes de gerar, o painel checa: último build **sem erros**; `patentes.js` bate com o acervo (sem alterações pendentes); todo arquivo referenciado em `patentes.js` existe; nenhuma pasta órfã em `assets/patentes/`, ou seja, ocultas e excluídas foram removidas.
- Nome: `vitrine-patentes_AAAA-MM-DD_HHMM.zip` em `%LOCALAPPDATA%\PainelVitrine\pacotes\`. Mostrar o SHA-256 e a lista resumida (N patentes, tamanho total).
- **Teste automatizado:** o zip nunca contém `admin/`, `scripts/`, `tests/`, `dados/`, `.git`, `*.py`, `*.md`, nenhum `.json` (incluindo `patente.json`), nem arquivos do acervo ou de backup.

### 5.10 Cadeia de build do executável
- `requirements.txt` com `--hash` (gerar com `pip-compile --generate-hashes` ou `pip hash`).
- PyInstaller no modo **`--onedir`**, não `--onefile`: o onefile se extrai para uma pasta temporária a cada execução, é mais lento e gera mais falso positivo de antivírus.
- `build_exe.ps1` roda os testes, depois o PyInstaller, e gera `dist/PainelVitrine/` + `PainelVitrine_vX.Y.Z.zip` + `SHA256SUMS.txt`.
- **Assinatura de código:** se a UFC/STI tiver certificado de assinatura, assinar o `.exe` com `signtool` (PENDENTE). Sem assinatura, o Windows SmartScreen vai avisar na primeira execução; documentar no `MANUAL.md` e publicar o SHA-256 para conferência.
- Versão e metadados do exe (empresa "UFC Inova", produto "Painel da Vitrine de Patentes") via arquivo de versão do PyInstaller.

---

## 6. Mudanças no código atual do site e do build

### 6.1 Refatoração do build (Fase 1): **sem mudar a saída**
- Mover a lógica de `scripts/build_patentes.py` para `scripts/vitrine_core/`, separada pelos módulos da 3.4. O `build_patentes.py` continua existindo, com os **mesmos argumentos** (`--src`, `--out`) e a mesma saída no terminal.
- **Critério de aceite:** rodar o build antigo (guardado em `tests/fixtures/build_legado.py`) e o novo sobre o acervo real dá `patentes.js`, `build_report.md` e todos os `assets/patentes/**` **idênticos byte a byte**.

### 6.2 Novas capacidades do core (Fase 2)
1. **`ler_ficha(caminho_pdf) -> dict`**: reaproveita `titulo_do_pdf`, `secoes_do_pdf`, `limpa_paragrafo`, `limpa_diferenciais` e `parse_trl`, e acrescenta:
   - **número BR:** procurar `BR\s*(10|20)\s*\d{4}\s*\d{6}[\s-]*\d` no texto do PDF e, se não achar, no nome do arquivo;
   - **categoria:** pelo nome do arquivo (`ARQUIVO_RE`) e pelo mapa de categorias; se não achar, fica vazia;
   - devolve cada campo com a **origem**: `{"valor": ..., "origem": "pdf" | "nome_arquivo" | "nao_encontrado"}`.
2. **`ler_texto(texto) -> dict`**: o mesmo fatiamento de seções aplicado a um texto colado (para quem copiar o texto de um PDF sem ter o arquivo).
3. **Suporte a `patente.json`** (4.3), `oculta` (4.3), patente sem PDF (4.4), pastas `_`/`.` ignoradas (4.6) e categorias vindas de `dados/categorias.json` (4.7).
4. **PDF higienizado** no lugar da cópia byte a byte (5.4).
5. **`patentes.js` só é gravado se não houver erros** (hoje ele é gravado mesmo com erro, e só o código de saída muda).
6. Remoção de assets de patentes que saíram da vitrine (ocultas ou excluídas), sempre com `dentro_de(assets/patentes)`.

### 6.3 Categorias
`CATEGORIA_MAP` sai do código e vai para `dados/categorias.json` com o mesmo conteúdo. O teste de regressão garante o mesmo resultado.

### 6.4 Site: tratar os nulos de patente sem PDF
- **Prévia do hover (`home.js`):** se `imagens.ficha600` for `null`, a prévia mostra a **capa** (1:1) + o `resumo` + o chip de TRL, no mesmo painel, sem quebrar a posição.
- **Detalhe (`patente.js`):** se `pdf` for `null`, o card "Documento oficial" some e a coluna de conteúdo passa a ocupar toda a largura. O lightbox não é montado.
- Testes E2E cobrindo esses dois casos com uma patente fictícia injetada (12.3).

### 6.5 `js/render.js` (compartilhado)
- Extrair `htmlCard`, `htmlTrl`, `htmlSecao`, `htmlDiferenciais` e a constante `SIZES` para `js/render.js`, expondo `window.RENDER = { card, trl, secao, diferenciais }`. Depende só de `window.UI` (`esc` e `icone`).
- `index.html` e `patente.html` passam a carregar `js/render.js` depois de `ui.js`. `home.js` e `patente.js` usam `RENDER.*`.
- **Critério:** screenshots da home e de 3 páginas de detalhe iguais antes e depois (comparação visual do Playwright, tolerância 0,1%).
- **Por quê:** a prévia do painel usa exatamente o mesmo código do site. O que a equipe vê no painel é o que vai ao ar.

### 6.6 Endurecimento do `.htaccess`
Acrescentar:
```apache
<IfModule mod_headers.c>
  Header set Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
  Header set X-Frame-Options "DENY"
  Header set Permissions-Policy "camera=(), microphone=(), geolocation=()"
</IfModule>
# Defesa em profundidade: se alguém subir o repositório inteiro por engano
RedirectMatch 404 ^/(admin|scripts|tests|dados|\.git)(/|$)
RedirectMatch 404 \.(py|md|json|log|spec|ps1|bat)$
```
- `style-src 'unsafe-inline'` é necessário por causa do `style="view-transition-name: …"` que o card usa hoje. **Alternativa melhor:** trocar esse atributo por uma classe + `style.setProperty` via JS (que a CSP permite) e remover o `'unsafe-inline'`. Fazer isso se não quebrar as View Transitions.
- Auditar os HTML: **nenhum `<script>` inline** (mover para arquivo, se houver), para que `script-src 'self'` funcione.

---

## 7. Interface do painel (design)

### 7.1 Princípio visual
**Mesma identidade do site**, com densidade de ferramenta de trabalho. O painel **importa** os CSS do site (`tokens.css`, `base.css`, `components.css`, a partir de `admin/ui/site/`) e reutiliza `.botao`, `.botao--primario/secundario/terciario`, `.chip`, `.badge`, `.segmentado`, `.trl`, `.card`, `.previa`, `.eyebrow`, `.logo-ufcinova`, `.mosaico` e os tokens de cor, tipografia, espaçamento, raio, sombra e movimento. **Nenhuma cor nova, com uma exceção** (7.3). `painel.css` contém **só** componentes que o site não tem (7.4) e usa **exclusivamente** variáveis de `tokens.css`.

`admin/sincroniza_site.py` copia esses arquivos para `admin/ui/site/`. Um teste (12.2) falha se a cópia estiver diferente do original, para evitar divergência.

### 7.2 Estrutura da janela (≥ 1100×720)
```
┌──────────────────────────────────────────────────────────────────────────┐
│ [logo UFC Inova] │ Painel da Vitrine     ● Local — só neste computador   │  ← cabeçalho (igual ao do site, fundo branco)
├───────────────┬──────────────────────────────────────────────────────────┤
│ ■ Patentes    │                                                          │
│ + Nova        │                 área de conteúdo                         │
│ ⇪ Publicar    │                 (max-width 1200px)                       │
│ ⟲ Histórico   │                                                          │
│ ⚙ Configurar  │                                                          │
│               │                                                          │
│ ─────────     │                                                          │
│ 3 alterações  │                                                          │
│ não publicadas│                                                          │
└───────────────┴──────────────────────────────────────────────────────────┘
```
- Barra lateral de 232 px, fundo `--c-surface` e borda direita `--c-border`. O item ativo tem marcador quadrado roxo de 8 px (o motivo gráfico do site) + texto `--c-brand` + fundo `--c-brand-50`.
- O selo "Local — só neste computador" (`.badge`, fundo `--c-brand-100`) deixa claro, o tempo todo, que é uma ferramenta interna.
- No rodapé da barra lateral, o contador de **alterações não publicadas**, que leva à tela Publicar.

### 7.3 Cor de erro (exceção controlada)
Formulários precisam de um estado de erro inequívoco. Proposta: `--c-danger: #B42318` (contraste de 6,6:1 sobre `#FFFFFF` e 6,0:1 sobre `#F4F4F5`), usado **só no painel** e **só** em mensagens de validação, borda de campo inválido e botão de exclusão definitiva. Nunca como decoração. O erro também é indicado por **ícone e texto**, não só pela cor. **PENDENTE: o usuário aprovar**. Se não aprovar, usar `--c-text` + ícone + borda de 2 px `--c-brand` para o erro.

### 7.4 Componentes novos (em `painel.css`)
| Componente | Especificação |
|---|---|
| **Campo** (`.campo`, `input`, `textarea`, `select`) | Rótulo Metropolis SemiBold 14 px acima do campo; ajuda em `--c-text-muted` 13 px abaixo; campo com altura ≥ 44 px, `--r-sm`, borda de 1 px `--c-border-strong` e fundo `--c-surface`. Foco: borda `--c-brand` + anel de 3 px `--c-brand-a12`. Contador de caracteres à direita ("120/160") quando houver limite. Obrigatório marcado com "*" e com o texto "(obrigatório)" para leitores de tela. |
| **Campo preenchido automaticamente** | Fundo `--c-brand-50` + etiqueta "✦ do PDF" ou "✦ do nome do arquivo" (`.badge`, 11 px). **A etiqueta some quando a pessoa edita o campo.** Campo "não encontrado": borda tracejada `--c-border-strong` + ajuda "Não encontramos no PDF. Preencha manualmente." |
| **Zona de soltar** (`.dropzone`) | Área de 160 px de altura, borda tracejada de 2 px `--c-brand-a24`, fundo `--c-brand-50` e `--r-lg`, com ícone `file-text` de 32 px. Texto: "**Arraste a ficha em PDF aqui**, cole com **Ctrl+V** ou [escolha o arquivo]". Ao arrastar por cima: borda sólida `--c-brand` e fundo `--c-brand-100`. Durante a leitura: barra de progresso indeterminada + "Lendo a ficha…". Com o arquivo aceito: vira um cartão compacto (miniatura da página 1 + nome + tamanho + "Trocar" + "Remover"). |
| **Editor de diferenciais** | Lista de campos de uma linha, com botão "Remover" (ícone `x`) em cada um e "+ Adicionar diferencial" (`.botao--terciario`). Máximo de 8 itens. Reordenar com os botões ↑ ↓ (acessível por teclado; sem arrastar na v1). |
| **Seletor de TRL** | Reaproveita a barra `.trl` do site, com os 9 segmentos transformados em `<button>`: clicar define o início e shift+clique define o fim da faixa. Também tem dois `select` (mín./máx.) como alternativa acessível, além do checkbox "Estimado". |
| **Recorte da capa** | Modal (`<dialog>`, mesmo padrão do lightbox do site) com a imagem e uma moldura 1:1 arrastável e redimensionável, mais os botões "Centralizar" e "Aplicar". Só aparece se a imagem não for quadrada. |
| **Tabela de patentes** | Linhas de 64 px com miniatura de 48 px (`--r-sm`), ID, título (1 linha, com reticências), área (`.eyebrow`), `.badge` PI/MU e status. Cabeçalho *sticky*, busca (mesmo componente `.busca` do site) e filtros por status com `.chip`. Hover da linha: fundo `--c-brand-50`. Ações ao fim da linha: "Editar", "Ocultar/Mostrar" e menu "⋯" (Ver no site local, Mover para a lixeira). |
| **Status** | `Publicada` (fundo `--c-brand-100`, texto `--c-brand`) · `Oculta` (contorno `--c-border-strong`, texto `--c-text-muted`, ícone de olho riscado) · `Alterada — não publicada` (contorno tracejado `--c-brand`). Sempre com texto, nunca só com a cor. |
| **Aviso (toast)** | Canto inferior direito, fundo `--c-brand-900` e texto branco, `--r-md`, `--sh-3`; some depois de 5 s (erros ficam até serem fechados); `role="status"` (sucesso) ou `role="alert"` (erro). |
| **Resumo de erros do formulário** | No topo do formulário, ao tentar salvar: caixa com borda esquerda de 4 px `--c-danger` e a lista de links "Título: muito curto" que levam o foco ao campo. |
| **Etapas do build** | Lista vertical: Validando → Salvando no acervo → Otimizando imagens → Gerando a ficha → Atualizando a vitrine. Cada etapa tem ícone (pendente = quadrado em contorno; em andamento = quadrado roxo pulsando; ok = `check`; erro = `x`). |
| **Confirmação destrutiva** | `<dialog>` que exige digitar o número BR da patente para "Mover para a lixeira" e "Restaurar backup". Botão de confirmação desabilitado até o texto bater. |

### 7.5 Telas

**T0 — Primeira execução / configuração** (`#/configurar`)
- Aparece sozinha se não houver `config.json` válido. Mostra o mosaico de quadrados do site à direita e o texto "Vamos conectar o painel à vitrine" à esquerda.
- Passo 1: "Pasta do site", com o botão "Escolher pasta" (seletor nativo), a validação ao vivo (✓ "Encontramos a vitrine com 60 patentes") ou o erro claro.
- Passo 2: "Pasta do acervo (fichas originais)", com o mesmo padrão ("✓ 60 pastas de patentes encontradas").
- Botão "Salvar e continuar". Nenhum caminho é digitável: só o seletor nativo.

**T1 — Patentes** (`#/lista`, tela inicial)
- Topo: H1 "Patentes" (UFCInova), com números no estilo do hero do site (Na vitrine · Ocultas · Não publicadas) e o botão primário "+ Nova patente".
- Tabela (7.4) com busca sem distinguir acentos (reaproveitar `UI.normaliza`) e filtros de status.
- Vazio: "Nenhuma patente encontrada" + "Limpar filtros".

**T2 — Nova patente / Editar** (`#/nova`, `#/editar/:id`): a tela principal
Layout em 2 colunas (formulário com 7/12 e prévia com 5/12, a prévia *sticky*).

*Coluna do formulário:*
1. **Bloco "Comece pela ficha (recomendado)"**: a zona de soltar do PDF. Abaixo, o link discreto "Não tem o PDF? Preencha manualmente ↓" (rola até o formulário e recolhe o bloco) e "Colar o texto da ficha" (abre um `textarea` que chama `ler_texto_ficha`).
2. **Identificação:** número do pedido (máscara `BR __ ____ ______-_`; só editável em patente **nova**); tipo e ano (somente leitura, calculados do número, com a explicação "BR 10 = Patente de Invenção · BR 20 = Modelo de Utilidade"); área (`select` com as áreas de `categorias.json` + a opção "Adicionar nova área…", que pede confirmação).
3. **Conteúdo:** título (textarea de 2 linhas, contador); O que é?\* (textarea, contador); Problema que resolve; Exemplo de uso; Diferenciais competitivos (editor); Benefício principal.
4. **Maturidade:** seletor de TRL.
5. **Imagem de capa\*:** zona de soltar de imagem + recorte 1:1 + recomendação "Quadrada, ao menos 800×800 px". Se a capa atual já existe (edição), mostrar a miniatura com "Trocar".
6. **Visibilidade** (edição): alternador "Mostrar na vitrine".
7. Checkbox obrigatório **"Conferi as informações preenchidas automaticamente"** (aparece só se houve preenchimento automático e não some depois).

*Coluna da prévia* (atualiza com debounce de 300 ms):
- Abas (`.segmentado`): **Card** · **Prévia do hover** · **Página**.
  - Card: `RENDER.card()` real, com a largura de uma coluna da grade (296 px).
  - Prévia do hover: o componente `.previa` com a miniatura da página 1 do PDF (ou a capa + resumo, se não houver PDF, conforme 6.4).
  - Página: versão reduzida do topo do detalhe (título, meta, TRL, capa) + seções.
- Legenda "É assim que vai aparecer na vitrine."

*Barra de ações fixa no rodapé:* "Cancelar" (terciário; pede confirmação se houver alterações) · "Salvar e atualizar a vitrine" (primário). No salvar, as etapas do build (7.4) aparecem num `<dialog>`. Ao terminar sem erros: toast "Patente salva. A vitrine local foi atualizada." + botões "Ver no site local" e "Voltar para a lista". Com erros: o relatório legível, e **nada** muda na vitrine.

*Proteções:* aviso de alterações não salvas ao sair da tela (`beforeunload` + guarda no roteador). Rascunho em memória, sem gravar em disco até salvar.

**T3 — Publicar** (`#/publicar`)
- Checklist ao vivo (cada item com ✓ ou ✗ e explicação): build sem erros · N alterações desde o último pacote (com lista) · todos os arquivos presentes · nenhum arquivo interno no pacote.
- Botão primário "Gerar pacote de publicação" → progresso → cartão com o nome do arquivo, tamanho, SHA-256 (com botão de copiar) e "Abrir pasta".
- Instruções do próximo passo, vindas de `config.json` (PENDENTE: quem publica e como; por exemplo, "Envie o .zip para a STI pelo e-mail X" ou "Suba pelo FTP").

**T4 — Histórico** (`#/historico`)
- Linha do tempo de ações (data, usuário do Windows, ação, patente e resultado), paginada de 50 em 50, com filtro por patente.
- Em cada ação que gerou backup: "Restaurar este ponto" (confirmação destrutiva). A restauração faz backup do estado atual antes, restaura e roda o build.

**T5 — Configurar** (`#/configurar`)
- Pastas do site e do acervo (troca só pelo seletor nativo), áreas tecnológicas (lista + "Adicionar"), texto de "próximo passo" da publicação, versão do painel e "Abrir pasta de backups".

### 7.6 Movimento (mesmos tokens do site; respeita `prefers-reduced-motion`)
| Elemento | Animação |
|---|---|
| Troca de tela | fade + `translateY(8px)`, `--dur-2` `--ease-out` |
| Campos preenchidos automaticamente | o fundo pisca de `--c-brand-100` para `--c-brand-50`, em sequência (40 ms entre campos, máximo de 400 ms), mostrando **o que** foi preenchido |
| Zona de soltar ao arrastar | `scale(1.01)` + troca de borda, `--dur-1` |
| Etapas do build | o quadrado da etapa atual pulsa (`opacity` .4↔1, 900 ms) |
| Prévia | crossfade de `--dur-1` ao atualizar |
| Toast | entra com `translateY(12px)` + fade (`--dur-2`) e sai com fade (`--dur-1`) |

### 7.7 Acessibilidade
- Navegável só pelo teclado, com foco visível (o mesmo do site) e ordem lógica.
- Todos os campos com `<label for>`; erros ligados por `aria-describedby` e `aria-invalid="true"`.
- A zona de soltar é um `<button>` de verdade (Enter/Espaço abrem o seletor), com instrução em texto.
- Status do build em `aria-live="polite"`.
- Zero violações serious/critical no axe (12.3).

### 7.8 Textos da interface (tom)
Português claro, sem jargão técnico. Exemplos:
- ✗ "Erro de parsing no PDF" → ✓ "Não conseguimos ler esta ficha. Confira se o arquivo abre normalmente no seu leitor de PDF."
- ✗ "Build failed" → ✓ "A vitrine não foi atualizada porque encontramos 2 problemas. Nada foi alterado no site."
- ✗ "Invalid path" → ✓ "Esta pasta não parece ser a vitrine. Escolha a pasta que contém o arquivo index.html."

---

## 8. Regras de validação (Python é a fonte; a interface espelha)

| Campo | Regra |
|---|---|
| Número | `^BR\s?(10\|20)\s?(\d{4})\s?(\d{6})[\s-]?(\d)$` depois de normalizar espaços. O ano precisa estar entre 1990 e o ano atual + 1. **Único** no acervo, lixeira incluída. Normalizado para `BR 10 2025 012345-6`. |
| Tipo / ano | Derivados do número; nunca recebidos da interface. |
| Área | Precisa existir em `categorias.json`. |
| Título | 10 a 160 caracteres, sem quebra de linha e sem só maiúsculas (se estiver todo em maiúsculas, a interface oferece "Converter para caixa de frase"). |
| O que é? | Obrigatório, de 40 a 900 caracteres. |
| Problema / Exemplo / Benefício | Opcionais, até 900 caracteres cada. |
| Diferenciais | 0 a 8 itens, cada um com 3 a 200 caracteres. |
| TRL | Opcional. Se informado: `1 ≤ min ≤ max ≤ 9` (inteiros) e `estimado` booleano. |
| Capa | Obrigatória para patente nova (5.5). |
| PDF | Opcional (5.4). Sem PDF, a interface avisa: "Sem o PDF, a vitrine não terá o botão de download nem a imagem da ficha." |
| Todo texto | `str`, NFC, sem caracteres de controle e bidi (5.7), espaços normalizados, `strip()`. |

A interface valida no `blur` e no salvar. O Python valida **sempre** no `previa` e no `salvar`, e devolve `erro.campos` com as mensagens por campo.

---

## 9. Fluxos principais

### 9.1 Nova patente a partir do PDF (caminho feliz)
1. A pessoa clica em "+ Nova patente" e arrasta o PDF para a zona de soltar.
2. JS: lê o `File`, confere tamanho ≤ 25 MB e envia com `api.receber_arquivo("pdf", nome, base64)`.
3. Python: limite → quarentena `…\quarentena\<uuid>\entrada.pdf` → validação (5.4) → `token`.
4. JS: `api.ler_ficha(token)` → campos + origem → preenche o formulário, marca com "✦ do PDF" e anima (7.6).
5. A pessoa confere, ajusta e adiciona a capa (recorte, se preciso). A prévia atualiza.
6. Ela marca "Conferi" e clica em "Salvar e atualizar a vitrine".
7. Python: valida tudo → backup → cria `<acervo>\61. BR 10 2025 012345 6\` com o PDF (original), a capa (PNG reencodada) e o `patente.json` com **todos** os campos confirmados. Assim a edição humana prevalece sobre futuras releituras do PDF. Depois roda o build → auditoria → resultado.
8. Toast de sucesso; a patente 61 aparece na lista com o status "Alterada — não publicada".

### 9.2 Colar (Ctrl+V)
- No evento `paste` da tela T2: se `clipboardData.files` tiver um PDF ou uma imagem, segue o mesmo fluxo de 9.1 (PDF → ficha; imagem → capa). Se tiver só texto e o foco não estiver num campo, a interface oferece "Usar este texto para preencher a ficha?" → `ler_texto_ficha`.

### 9.3 Cadastro manual
- "Preencher manualmente" → o formulário vazio fica visível → mesma validação → `salvar` sem `token_pdf` → patente sem PDF (4.4).

### 9.4 Editar
- `obter(id)` → formulário preenchido (o número fica travado) → ao salvar, grava/atualiza o `patente.json` (e a capa/PDF, se forem trocados; os arquivos antigos vão para o backup, não são apagados sem cópia).

### 9.5 Ocultar / mostrar
- Alternador na tabela ou na edição → `alternar_oculta` → `patente.json.oculta` → build → a patente sai (ou volta) de `patentes.js` e `assets/patentes/`.

### 9.6 Mover para a lixeira
- Menu "⋯" → confirmação destrutiva (digitar o número) → `excluir` → a pasta vai para `_lixeira` → build.

---

## 10. Executável

### 10.1 Experiência da pessoa
1. Recebe a pasta `PainelVitrine` (ou um zip) e copia para `C:\Program Files\PainelVitrine` ou para os Documentos.
2. Dá dois cliques em **`PainelVitrine.exe`**. (Opcional: `Criar atalho na área de trabalho.bat`, que cria um atalho `.lnk` via PowerShell.)
3. A janela abre com o logo. Na primeira vez aparece a tela T0.
4. Fechar a janela encerra tudo (servidor estático interno, servidor do "site local", trava).

### 10.2 Requisitos e verificações na inicialização
- Windows 10 ou 11, 64 bits.
- **Microsoft Edge WebView2 Runtime**: checar a presença no registro (`HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` ou o equivalente em HKCU). Se estiver ausente, mostrar uma caixa de mensagem nativa ("Para abrir o painel, instale o componente WebView2 da Microsoft") com o link oficial, e encerrar.
- Instância única (5.8).
- Limpar a quarentena de sessões anteriores.
- Rodar `sincroniza_site` **não** é tarefa do exe: a cópia de `admin/ui/site` é feita no empacotamento. No modo `--dev`, é rodada ao iniciar.

### 10.3 Empacotamento (`admin/build_exe.ps1`)
1. `python -m pytest tests/core tests/painel tests/seguranca` (se falhar, para).
2. `python admin/sincroniza_site.py`.
3. `pyinstaller admin/painel.spec --noconfirm --clean` com: `--onedir`, `--windowed` (sem console), `--icon admin/icone.ico`, arquivo de versão e `datas` = `admin/ui/**` + `dados/categorias.json` (modelo inicial) + `scripts/vitrine_core` como pacote.
4. Gera `SHA256SUMS.txt` e `PainelVitrine_vX.Y.Z.zip`.
5. (Opcional) `signtool sign` se houver certificado (PENDENTE).

### 10.4 Atualização do painel
- Uma versão nova substitui a pasta do programa. A configuração, os backups e a auditoria ficam em `%APPDATA%` e são preservados.
- `config.json` tem um `versao` para migrações futuras.

---

## 11. Documentação e repositório

### 11.1 `admin/MANUAL.md` (para a equipe, 2 a 3 páginas, linguagem simples, com capturas de tela)
Como abrir; primeira configuração; cadastrar pelo PDF; cadastrar manualmente; editar, ocultar e excluir; conferir no site local; gerar o pacote e publicar; restaurar um erro; o que fazer se o Windows avisar sobre o programa (SmartScreen); **boas práticas de segurança** (conta do Windows com senha, bloquear a tela com Win+L ao sair, não copiar o painel para computadores compartilhados).

### 11.2 `README.md` do projeto
Acrescentar as seções: "Painel local" (arquitetura resumida, rodar em dev com `python -m painel --dev`, gerar o exe e rodar os testes) e "Modelo de segurança" (resumo da seção 5).

### 11.3 `.gitignore`
```
# Python
__pycache__/
*.pyc
.venv/
# Painel / PyInstaller
build/
dist/
*.spec.bak
admin/ui/site/
# Pacotes e saídas locais
*.zip
SHA256SUMS.txt
# Testes
tests/node_modules/
tests/test-results/
tests/playwright-report/
# Sistema
Thumbs.db
desktop.ini
.DS_Store
._*
```
`admin/ui/site/` é gerado e fica fora do git. **Os `assets/patentes/` continuam versionados**, como hoje.

---

## 12. Testes (obrigatórios; nada é concluído com teste falhando)

### 12.1 Regressão do site e do build (Fases 0–2)
- [ ] Testes do site restaurados ou recriados (A1) e passando **antes** de qualquer mudança.
- [ ] Build refatorado com saída **idêntica byte a byte** ao legado (6.1).
- [ ] Depois da Fase 2: as 60 patentes geram o mesmo `patentes.js` do snapshot; os `ficha.pdf` estão higienizados e sem `/JS`, `/JavaScript`, `/OpenAction`, `/Launch`, `/EmbeddedFile` nem autor.
- [ ] `render.js`: home e 3 detalhes com screenshots iguais antes e depois (6.5).
- [ ] O site com uma patente sem PDF e com uma patente oculta se comporta como em 6.4 e 4.3.

### 12.2 pytest: core, painel e segurança
**Core**
- `ler_ficha` nas 60 fichas reais: título, seções e TRL **iguais** aos do `patentes.js` atual (teste de ouro).
- `ler_texto` com o texto copiado de 3 fichas.
- Merge do `patente.json`: prioridade campo a campo; campos desconhecidos → erro; `oculta` exclui a patente; `trl.texto` e `resumo` recalculados.
- `patentes.js` **não** é reescrito quando o build tem erro.
- Pastas `_lixeira` e `.algo` ignoradas; IDs nunca reaproveitados.

**Validação** (tabela 8): casos válidos e inválidos de cada campo, incluindo número duplicado, ano fora da faixa, título em maiúsculas, 9 diferenciais, TRL 7–3, texto com `U+202E` e com `\x00`.

**Segurança (`tests/seguranca/`)**
- PDF: > 25 MB; `.pdf` que é PNG; PNG com extensão `.pdf`; criptografado; corrompido; 6 páginas; página de 20.000 pt; **PDF com JavaScript/OpenAction/anexo** → a versão publicada não tem nada disso.
- Imagem: bomba de descompressão (50.000×50.000); arquivo poliglota (JPEG + ZIP no fim) → a saída reencodada não contém a assinatura do ZIP; EXIF com GPS → a saída sem EXIF; 300×300 → erro; 600×900 → exige recorte.
- Caminhos: `configurar()` com site = acervo, um dentro do outro ou pasta sem `index.html` → erro. Chamada direta de métodos da `Api` com `"..\\..\\Windows"`, `"C:\\"`, `"\\\\servidor\\x"`, `None`, `123`, strings de 10 MB → todos recusados, sem escrita fora das raízes (conferir o sistema de arquivos antes e depois).
- Títulos que gerariam `CON.pdf`, com 400 caracteres, terminados em ponto → nomes seguros, caminho < 240.
- `abrir_link("https://evil.com")` e `abrir_pasta("C:\\")` → recusados.
- **Superfície da API:** a lista de métodos públicos de `Api` é **exatamente** a da 5.3.
- **Pacote:** o zip gerado a partir de um repositório com `admin/`, `tests/`, `scripts/`, `.git/`, `dados/`, um `patente.json` e um `.py` solto na raiz **não** contém nenhum deles; contém tudo que `patentes.js` referencia; não contém a pasta de uma patente oculta.
- **Integridade:** simular uma exceção no meio do `salvar` → o acervo e o `patentes.js` ficam como antes, e o backup existe. Duas instâncias → a segunda recusa. `restaurar` faz backup antes.
- **Sincronização:** `admin/ui/site/*` idêntico aos arquivos do site.
- **Auditoria:** cada ação escreve exatamente uma linha JSON válida com usuário, ação, id e resultado.

### 12.3 Playwright: interface do painel (`tests/painel-ui/`)
Servir `admin/ui/` e injetar `mock-api.js`, que implementa `window.pywebview.api` com respostas controladas (incluindo erros). Chromium, viewport 1280×800 e 1440×900.
1. Primeira execução: T0 aparece; sem as duas pastas válidas, "Salvar" fica desabilitado.
2. Lista: renderiza, busca sem distinguir acentos, filtra por status, e os status aparecem com texto.
3. **Preenchimento pelo PDF:** soltar um arquivo na zona de soltar (`setInputFiles` / `dispatchEvent('drop')`) → os campos são preenchidos, recebem "✦ do PDF", e a etiqueta some ao editar; o campo "não encontrado" é sinalizado.
4. **Ctrl+V** com um arquivo PDF na área de transferência simulada → mesmo resultado.
5. Colar texto → oferta "Usar este texto…" → preenchimento.
6. Manual: salvar vazio → resumo de erros com links que focam os campos; `aria-invalid` presente.
7. Recorte da capa: aparece para imagem não quadrada e envia coordenadas inteiras.
8. Prévia: as abas Card, Hover e Página renderizam com `RENDER.*` e atualizam ao digitar o título.
9. Salvar: as etapas aparecem; o sucesso mostra o toast; o erro mostra o relatório, sem toast de sucesso.
10. Alterações não salvas: sair da tela pede confirmação.
11. Exclusão: o botão só é liberado quando o número digitado bate.
12. Publicar: o checklist bloqueia com build com erro e libera sem erro; o SHA-256 é exibido.
13. **CSP:** nenhuma violação no console; nenhum `<a href="http` na interface; nenhum script inline.
14. Teclado: completar uma patente nova só com o teclado.
15. axe: 0 violações serious/critical em T0, T1, T2, T3 e T4.
16. `prefers-reduced-motion`: sem animação de preenchimento nem pulsação.

### 12.4 Teste de fumaça do executável (manual, com checklist no PR)
- [ ] Abre com dois cliques num Windows limpo com WebView2; sem WebView2, mostra a mensagem e encerra.
- [ ] Uma segunda instância é recusada.
- [ ] `netstat -ano | findstr <PID>`: só `127.0.0.1` (nenhum `0.0.0.0` nem IP da rede).
- [ ] F12 e o menu de contexto "Inspecionar" **não** abrem o DevTools.
- [ ] O link da UFC Inova abre no navegador padrão, não na janela do painel.
- [ ] Cadastrar a patente 61 com um PDF de teste, editar, ocultar, mostrar, mover para a lixeira e restaurar pelo histórico.
- [ ] "Ver no site local" mostra a vitrine com a 61; a prévia do hover e o detalhe funcionam.
- [ ] Gerar o pacote, abrir o zip e conferir que não há nada interno.
- [ ] O antivírus do Windows (Defender) não bloqueia; anotar o SHA-256.
- [ ] Fechar a janela encerra todos os processos (Gerenciador de Tarefas).

---

## 13. Critérios de aceite e evolução

### 13.1 Definition of Done (v1)
1. A equipe consegue, sem terminal, cadastrar (pelo PDF ou manualmente), editar, ocultar, excluir (lixeira), conferir e gerar o pacote.
2. Preenchimento automático correto nas 60 fichas reais (teste de ouro) e sinalização do que foi preenchido.
3. Interface com a identidade do site (tokens, fontes, componentes e logo), aprovada pelo usuário.
4. Todos os requisitos da seção 5 implementados e cobertos pelos testes da 12.2 e 12.4.
5. O site público continua idêntico para o visitante (regressão da 12.1), mais o `.htaccess` endurecido.
6. `PainelVitrine.exe` gerado por `build_exe.ps1`, com SHA-256, `MANUAL.md` e README atualizados.
7. Achados A1–A8 resolvidos.

### 13.2 Evolução (não fazer agora)
- **v1.1:** botão "Publicar no GitHub" (commit + push do repositório), se a hospedagem for o GitHub Pages, com credencial guardada no Gerenciador de Credenciais do Windows, nunca em arquivo.
- **v2:** gerar o PDF da ficha no template da UFC Inova a partir do formulário.
- **v3 (se um dia houver acesso remoto):** backend com autenticação (passkey ou SSO da UFC), conforme o que já foi discutido. O `vitrine_core` e a interface do painel são reaproveitados.

---

## 14. Fases de implementação (ordem obrigatória)

| Fase | Entrega | Porta de saída |
|---|---|---|
| **0. Preparação** | `.gitignore`; decidir sobre o arquivo `19,47,52`; restaurar ou recriar `tests/` do site; **snapshot de referência** (cópia do `patentes.js`, do relatório e dos hashes de `assets/patentes/**`) | Testes do site passando |
| **1. Refatoração do core** | `scripts/vitrine_core/` + CLI fina + `categorias.json` | Saída byte a byte idêntica (6.1) |
| **2. Novas capacidades do core e do site** | `ler_ficha`, `ler_texto`, `patente.json`, `oculta`, sem PDF, lixeira, PDF higienizado, gravação só sem erro; `render.js`; nulos no site; `.htaccess` | 12.1 completo |
| **3. Backend do painel** | `api.py` (superfície da 5.3), validação, quarentena, armazenamento, backup, auditoria, publicação, config | 12.2 completo |
| **4. Casca da interface** | `index.html`, roteamento, barra lateral, cabeçalho, `painel.css` (componentes da 7.4), sincronização do site, CSP | Revisão visual pelo usuário (enviar screenshots) |
| **5. Nova/Editar** | Zona de soltar, colar, preenchimento automático, formulário, recorte, TRL, prévia com `RENDER` | Itens 3–10 da 12.3 |
| **6. Demais telas** | T0, T1, T3, T4, T5 | 12.3 completo |
| **7. Executável** | `app.py` (WebView2, instância única, guarda de navegação), `painel.spec`, `build_exe.ps1`, ícone e versão | 12.4 completo |
| **8. Documentação** | `MANUAL.md` com capturas, README | Revisão pelo usuário |

Em cada fase: commits pequenos, com a mensagem explicando o **porquê**, sem misturar refatoração com mudança de comportamento.

---

## 15. Pendências (perguntar ao usuário)

| # | Pergunta | Impacto |
|---|---|---|
| P1 | O arquivo `19,47,52` na raiz pode ser apagado? | Fase 0 |
| P2 | A pasta `tests/` existia em algum lugar (outro computador, outro branch)? | Fase 0 |
| P3 | A cor de erro `#B42318` no painel está aprovada? (7.3) | Fase 4 |
| P4 | Quantas pessoas e computadores vão usar o painel? O acervo fica numa pasta local ou compartilhada (rede/OneDrive)? Pasta compartilhada exige trava entre computadores; na v1, **um computador por vez**. | Fases 3 e 7 |
| P5 | Como o pacote chega ao servidor (STI, FTP, GitHub Pages)? Define o texto de "próximo passo" e a v1.1. | Fase 6 |
| P6 | A UFC ou a STI tem certificado de assinatura de código? | Fase 7 |
| P7 | Os computadores da UFC Inova têm o WebView2 (Windows 10/11 atualizados já têm) e permitem executar programas não instalados? | Fase 7 |
| P8 | Onde deve ficar a pasta do acervo no computador da equipe? Hoje ela está em `Documents\50 Patentes Observatório…` no computador do desenvolvedor. | T0 / MANUAL |
