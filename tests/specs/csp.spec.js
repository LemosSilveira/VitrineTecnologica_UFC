/* ============================================================
   csp.spec.js — a Content-Security-Policy do site.

   O `server.js` le a politica do proprio `.htaccess`, entao o que roda
   aqui e exatamente o que o Apache vai aplicar. Se alguem acrescentar um
   <script> ou um style="" inline, estes testes quebram -- que e o ponto:
   uma CSP com 'unsafe-inline' passa a impressao de proteger sem proteger.
   ============================================================ */
"use strict";

const fs = require("fs");
const path = require("path");
const { test, expect } = require("@playwright/test");
const { lerDados } = require("./_ajuda");

const HTACCESS = fs.readFileSync(
  path.resolve(__dirname, "..", "..", ".htaccess"),
  "utf8"
);

/** Coleta violacoes de CSP relatadas pela propria pagina. */
async function vigiaCsp(page) {
  const violacoes = [];
  await page.exposeFunction("__registraViolacaoCsp", (v) => violacoes.push(v));
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (e) => {
      window.__registraViolacaoCsp(
        `${e.violatedDirective}: ${e.blockedURI || e.sourceFile || "inline"}`
      );
    });
  });
  return violacoes;
}

test.describe("Content-Security-Policy", () => {
  test("o .htaccess define a politica sem 'unsafe-inline' nem 'unsafe-eval'", () => {
    const m = HTACCESS.match(
      /Header\s+set\s+Content-Security-Policy\s+"([^"]+)"/i
    );
    expect(m, "nenhuma CSP encontrada no .htaccess").not.toBeNull();
    const csp = m[1];

    expect(csp).not.toContain("unsafe-inline");
    expect(csp).not.toContain("unsafe-eval");
    for (const diretiva of [
      "default-src 'self'",
      "script-src 'self'",
      "style-src 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
    ]) {
      expect(csp).toContain(diretiva);
    }
  });

  test("o .htaccess bloqueia as pastas internas", () => {
    for (const pasta of ["admin", "scripts", "tests", "dados"]) {
      expect(HTACCESS).toContain(pasta);
    }
    expect(HTACCESS).toMatch(/RedirectMatch\s+404/);
  });

  test("o servidor de teste entrega a politica do .htaccess", async ({ page }) => {
    const resp = await page.goto("/index.html");
    const csp = resp.headers()["content-security-policy"];
    expect(csp, "o servidor de teste precisa espelhar o .htaccess").toBeTruthy();
    expect(csp).not.toContain("unsafe-inline");
  });

  for (const [nome, url] of [
    ["home", "/index.html"],
    ["detalhe", "/patente.html?id=1"],
    ["404", "/404.html"],
  ]) {
    test(`${nome}: nenhuma violacao de CSP`, async ({ page }) => {
      const violacoes = await vigiaCsp(page);
      await page.goto(url);
      await expect(page.locator("h1")).toBeVisible();
      /* dar tempo ao que roda depois da pintura (mosaico, previa, revela) */
      await page.waitForTimeout(600);
      expect(violacoes, violacoes.join("\n")).toEqual([]);
    });
  }

  test("o lightbox e a previa nao violam a politica", async ({ page }) => {
    const violacoes = await vigiaCsp(page);
    await page.goto("/index.html");
    await page.locator(".grade .card").first().hover();
    await page.goto("/patente.html?id=1");
    await page.locator(".doc__thumb").click();
    await expect(page.locator("[data-lightbox]")).toBeVisible();
    expect(violacoes, violacoes.join("\n")).toEqual([]);
  });

  test("a view transition da capa e aplicada por JS, nao por style inline", async ({
    page,
  }) => {
    await page.goto("/index.html");
    const img = page.locator(".grade .card").first().locator("img");
    const { patentes } = await lerDados(page);

    /* o HTML traz so o data-attribute... */
    await expect(img).toHaveAttribute("data-vt", `capa-${patentes[0].id}`);
    /* ...e o valor chega ao elemento pelo CSSOM */
    expect(
      await img.evaluate((el) => el.style.getPropertyValue("view-transition-name"))
    ).toBe(`capa-${patentes[0].id}`);
  });

  test("nenhum script nem estilo inline nos HTML publicados", () => {
    const raiz = path.resolve(__dirname, "..", "..");
    for (const arquivo of ["index.html", "patente.html", "404.html"]) {
      /* Comentarios fora: eles nao sao executados, e os comentarios destes
         arquivos citam <style> justamente para explicar por que ele saiu. */
      const html = fs
        .readFileSync(path.join(raiz, arquivo), "utf8")
        .replace(/<!--[\s\S]*?-->/g, "");

      /* <script> sem src = script inline, que a CSP bloquearia */
      const inline = [...html.matchAll(/<script(?![^>]*\ssrc=)[^>]*>/gi)];
      expect(inline.map((m) => m[0]), arquivo).toEqual([]);

      /* <style> e style="" tambem exigiriam 'unsafe-inline' */
      expect([...html.matchAll(/<style[\s>]/gi)].map((m) => m[0]), arquivo).toEqual([]);
      expect([...html.matchAll(/\sstyle\s*=\s*"/gi)].map((m) => m[0]), arquivo).toEqual([]);
    }
  });
});
