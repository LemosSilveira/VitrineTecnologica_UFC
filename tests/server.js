/* ============================================================
   server.js — servidor estatico da vitrine para os testes.

   Diferenca em relacao ao `python -m http.server`: rotas desconhecidas
   respondem 404 com o corpo de /404.html, como faz o Apache via
   `ErrorDocument 404 /404.html`. Sem isso nao da para testar a 404.

   Uso:  node tests/server.js [porta]      (padrao: 4173)
   ============================================================ */
"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const RAIZ = path.resolve(__dirname, "..");
const PORTA = Number(process.argv[2] || process.env.PORTA || 4173);

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".pdf": "application/pdf",
  ".md": "text/markdown; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
};

/** Resolve a URL para um caminho dentro da raiz, ou null se escapar dela. */
function resolveDentroDaRaiz(pathname) {
  let rel;
  try {
    rel = decodeURIComponent(pathname);
  } catch {
    return null;
  }
  if (rel.endsWith("/")) rel += "index.html";
  const alvo = path.resolve(RAIZ, "." + rel);
  // path traversal: o alvo precisa continuar dentro da raiz
  if (alvo !== RAIZ && !alvo.startsWith(RAIZ + path.sep)) return null;
  return alvo;
}

function responde404(res) {
  const p404 = path.join(RAIZ, "404.html");
  fs.readFile(p404, (err, buf) => {
    if (err) {
      res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
      res.end("404");
      return;
    }
    res.writeHead(404, {
      "content-type": MIME[".html"],
      "x-content-type-options": "nosniff",
    });
    res.end(buf);
  });
}

const servidor = http.createServer((req, res) => {
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.writeHead(405, { allow: "GET, HEAD" });
    res.end();
    return;
  }

  const url = new URL(req.url, `http://${req.headers.host || "127.0.0.1"}`);
  const alvo = resolveDentroDaRaiz(url.pathname);
  if (!alvo) {
    responde404(res);
    return;
  }

  fs.stat(alvo, (err, st) => {
    if (err || !st.isFile()) {
      responde404(res);
      return;
    }
    const ext = path.extname(alvo).toLowerCase();
    res.writeHead(200, {
      "content-type": MIME[ext] || "application/octet-stream",
      "content-length": st.size,
      // espelha o .htaccess: nada de sniffing de tipo
      "x-content-type-options": "nosniff",
      // os testes precisam ver sempre o arquivo do disco
      "cache-control": "no-store",
    });
    if (req.method === "HEAD") {
      res.end();
      return;
    }
    fs.createReadStream(alvo).pipe(res);
  });
});

servidor.listen(PORTA, "127.0.0.1", () => {
  console.log(`Vitrine em http://127.0.0.1:${PORTA} (raiz: ${RAIZ})`);
});
