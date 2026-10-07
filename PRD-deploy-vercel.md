# PRD — Deploy da Vitrine de Patentes UFC na Vercel

**Repositório:** `LemosSilveira/VitrineTecnologica_UFC` (branch `main`)
**Tipo de mudança:** pontual — só configuração de hospedagem e limpeza. **Nenhuma alteração de layout, CSS, conteúdo ou lógica do site.**

---

## 1. Contexto

O site é estático (HTML + CSS + JS puro, sem build, sem `fetch`, sem dependências externas em runtime). Hoje ele está preparado para **Apache** (`.htaccess` com 404, cache, MIME e cabeçalhos de segurança). A Vercel **ignora o `.htaccess`**, então essas regras precisam ser reescritas em `vercel.json`.

Pontos encontrados na análise do repositório:

| # | Achado | Risco |
|---|---|---|
| A | Regras de segurança/cache só existem no `.htaccess` | Na Vercel o site sobe **sem** cabeçalhos de segurança |
| B | Arquivos internos iriam para o ar: `scripts/` (build em Python, relatório), `README.md`, `skills-lock.json`, `.htaccess` | Expõe caminhos locais (`C:\Users\Usuario\...`) e detalhes do processo |
| C | Arquivo solto `19,47,52` na raiz (lista de nomes e tamanhos dos arquivos originais) | Lixo + vazamento de informação interna |
| D | Não existe `.gitignore` | Risco de subir `node_modules/`, `.vercel/`, `.env` por engano |
| E | `og:image` usa caminho relativo (`assets/img/og-image.png`) | WhatsApp/LinkedIn/Facebook não mostram a prévia — precisam de URL absoluta |
| F | Pasta tem ~142 MB (60 PDFs + imagens) | O deploy pela **CLI** no plano Hobby tem limite de 100 MB → usar **deploy via GitHub** |

---

## 2. Objetivo

Publicar o site na Vercel com:

1. a mesma aparência e o mesmo funcionamento de hoje;
2. cabeçalhos de segurança equivalentes ou melhores que os do `.htaccess`;
3. apenas os arquivos públicos no ar;
4. página 404 personalizada funcionando com status HTTP 404.

**Fora do escopo:** mudar design, textos `PENDENTE`, domínio próprio da UFC, analytics, formulário de contato, painel admin.

---

## 3. Alterações

### 3.1 Criar `vercel.json` na raiz

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": null,
  "buildCommand": null,
  "outputDirectory": ".",
  "cleanUrls": false,
  "trailingSlash": false,
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()" },
        { "key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains" },
        { "key": "Cross-Origin-Opener-Policy", "value": "same-origin" }
      ]
    },
    {
      "source": "/(.*)\\.html",
      "headers": [{ "key": "Cache-Control", "value": "public, max-age=0, must-revalidate" }]
    },
    {
      "source": "/(css|js)/(.*)",
      "headers": [{ "key": "Cache-Control", "value": "public, max-age=604800" }]
    },
    {
      "source": "/assets/fonts/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=31536000, immutable" },
        { "key": "Access-Control-Allow-Origin", "value": "*" }
      ]
    },
    {
      "source": "/assets/(img|patentes)/(.*)",
      "headers": [{ "key": "Cache-Control", "value": "public, max-age=2592000" }]
    }
  ]
}
```

Notas para quem implementar:

- **CSP:** `style-src` precisa de `'unsafe-inline'` porque o `404.html` tem um `<style>` e o `ui.js` gera atributos `style="..."` no mosaico. Scripts **não** precisam de inline (todos são arquivos `.js` locais) — manter `script-src 'self'` sem `'unsafe-inline'`.
- **Cache:** as imagens e PDFs não têm hash no nome, então ficam com 30 dias (e não 1 ano, como no `.htaccess`) para que uma ficha atualizada apareça sem precisar renomear o arquivo. Fontes não mudam → 1 ano `immutable`.
- **404:** a Vercel serve o `404.html` da raiz automaticamente em rotas inexistentes, com status 404. Não precisa de regra. Como o `basePath` é `"/"` (raiz de domínio), os caminhos absolutos da 404 já funcionam.
- `cleanUrls` fica `false` de propósito: o site usa `patente.html?id=19` e os links internos apontam para `.html`.

### 3.2 Criar `.vercelignore` na raiz

Impede que arquivos internos sejam publicados (vale para o deploy via GitHub também):

```
# Ferramentas e documentação internas — não publicar
scripts/
tests/
README.md
skills-lock.json
.htaccess
PRD-*.md
*.py
*.log
node_modules/
.vscode/
.claude/
```

### 3.3 Criar `.gitignore` na raiz

```
node_modules/
tests/node_modules/
tests/test-results/
tests/playwright-report/
.vercel/
.env
.env.*
*.log
.DS_Store
Thumbs.db
```

### 3.4 Remover o arquivo `19,47,52`

É uma listagem dos arquivos originais com tamanhos, sem uso no site. Apagar do repositório (`git rm "19,47,52"`).

### 3.5 Deixar `og:image` com URL absoluta

Em `index.html` e `patente.html`, trocar:

```html
<meta property="og:image" content="assets/img/og-image.png" />
```

por (usando o domínio final da Vercel, ex.: `vitrine-patentes-ufc.vercel.app`):

```html
<meta property="og:image" content="https://DOMINIO-FINAL/assets/img/og-image.png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
```

Também adicionar `og:url` e `<link rel="canonical">` no `index.html` apontando para `https://DOMINIO-FINAL/`.
> Fazer este passo **depois** do primeiro deploy, quando o domínio estiver definido.

### 3.6 Atualizar o `README.md` (seção "Como publicar")

Acrescentar um item **Vercel**: deploy pelo GitHub, sem build, configurações em `vercel.json`, arquivos excluídos em `.vercelignore`. Manter as instruções de Apache/Nginx.

**Não alterar:** `.htaccess` (continua útil se um dia o site for para o servidor da UFC), `js/config.js`, CSS, HTML (fora o 3.5) e `js/data/patentes.js`.

---

## 4. Passo a passo de publicação

1. Fazer os commits das alterações 3.1 a 3.4 e dar `git push` na `main`.
2. Em vercel.com → **Add New → Project → Import Git Repository** → escolher `VitrineTecnologica_UFC`.
3. Configuração do projeto:
   - **Framework Preset:** Other
   - **Root Directory:** `./`
   - **Build Command:** vazio (override ligado, sem comando)
   - **Output Directory:** `.`
   - **Install Command:** vazio
4. **Deploy.** Usar o deploy via GitHub, e **não** a CLI (`vercel deploy`): a pasta tem ~142 MB e a CLI no plano Hobby aceita até 100 MB.
5. Em **Settings → Deployment Protection**, deixar os *Preview Deployments* protegidos (só a produção pública).
6. Com o domínio definido, aplicar o item 3.5 e fazer novo push.

---

## 5. Critérios de aceite

| # | Teste | Resultado esperado |
|---|---|---|
| 1 | Abrir `/` | Home igual à versão local, 60 patentes, filtros e busca funcionando |
| 2 | Abrir `/patente.html?id=19` | Detalhe da patente 19, lightbox e PDF abrindo |
| 3 | Abrir `/patente.html?id=abc` e `/patente.html?id=999` | Redireciona para a 404 personalizada |
| 4 | Abrir `/qualquer/coisa` | 404 personalizada, CSS/fonte/logo carregando, **status 404** |
| 5 | Abrir `/scripts/build_patentes.py`, `/README.md`, `/skills-lock.json`, `/.htaccess`, `/19,47,52` | Todos retornam **404** |
| 6 | `curl -I https://DOMINIO/` | Mostra `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Strict-Transport-Security` |
| 7 | Console do navegador (DevTools) na home, no detalhe e na 404 | **Nenhum** erro de CSP |
| 8 | securityheaders.com no domínio | Nota **A** ou superior |
| 9 | Colar o link no WhatsApp (após 3.5) | Aparece a prévia com a `og-image` |
| 10 | Testes Playwright locais (`npm test` em `tests/`) | Continuam passando (nada do site mudou) |

---

## 6. Riscos e observações

- **Plano Hobby da Vercel** é gratuito, mas os termos restringem a uso **não comercial**. Se o site passar a ser oficial da UFC Inova, avaliar com o setor se o plano Hobby é adequado ou se o ideal é hospedar no servidor da UFC (o `.htaccess` já está pronto para isso).
- **Barra de comentários da Vercel em previews:** a CSP pode bloquear o script `vercel.live` nos *Preview Deployments*. Não afeta a produção; se incomodar, desativar o "Vercel Toolbar" nas configurações do projeto.
- **Fichas em PDF são públicas por natureza** (é uma vitrine). Confirmar com a UFC Inova que todos os 60 PDFs podem ficar abertos na internet antes de divulgar o link.
