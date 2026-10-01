/* ============================================================
   erro.spec.js — regressao da 404.

   O ponto delicado desta pagina e que os caminhos sao ABSOLUTOS: ela e
   servida em qualquer profundidade de URL, e caminhos relativos quebrariam
   o CSS, as fontes e o logo. Os testes cobrem exatamente isso.
   ============================================================ */
"use strict";

const { test, expect } = require("@playwright/test");
const { vigiaConsole, semRolagemHorizontal } = require("./_ajuda");

test.describe("404", () => {
  test("a pagina abre direto e monta o mosaico", async ({ page }) => {
    const problemas = vigiaConsole(page);
    await page.goto("/404.html");

    await expect(page).toHaveTitle(/Página não encontrada/);
    await expect(page.locator("h1")).toContainText("Esta página ainda não foi inventada");
    await expect(page.locator("[data-mosaico-erro] span").first()).toBeVisible();
    expect(problemas, problemas.join("\n")).toEqual([]);
  });

  test("uma rota desconhecida responde 404 com o corpo da 404.html", async ({
    page,
  }) => {
    const resp = await page.goto("/nao-existe");
    expect(resp.status()).toBe(404);
    await expect(page.locator("h1")).toContainText("Esta página ainda não foi inventada");
  });

  test("funciona em qualquer profundidade de URL", async ({ page }) => {
    /* O documento em si responde 404 (e o que se quer testar), entao aqui
       vigiamos as SUBrequisicoes: CSS, JS, fonte e logo tem de vir 200 mesmo
       tres niveis abaixo da raiz. */
    const quebrados = [];
    page.on("response", (r) => {
      if (r.request().resourceType() === "document") return;
      if (r.status() >= 400) quebrados.push(`${r.status()} ${r.url()}`);
    });

    const resp = await page.goto("/patente/xyz/abc");
    expect(resp.status()).toBe(404);

    /* o CSS precisa ter sido aplicado mesmo tres niveis abaixo da raiz */
    const fundo = await page
      .locator("body")
      .evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(fundo).not.toBe("rgba(0, 0, 0, 0)");

    /* e o logo, que vem de uma mascara CSS com caminho absoluto */
    const mascara = await page
      .locator(".logo-ufcinova")
      .evaluate((el) => getComputedStyle(el).maskImage || getComputedStyle(el).webkitMaskImage);
    expect(mascara).toContain("logo-ufcinova.svg");

    expect(quebrados, quebrados.join("\n")).toEqual([]);
  });

  test("todos os caminhos internos sao absolutos", async ({ page }) => {
    await page.goto("/404.html");
    const relativos = await page.evaluate(() => {
      const sel = "link[href], script[src], img[src], a[href]";
      return Array.from(document.querySelectorAll(sel))
        .map((el) => el.getAttribute("href") || el.getAttribute("src"))
        .filter(
          (v) =>
            v &&
            !v.startsWith("/") &&
            !/^(https?:|mailto:|#|data:)/.test(v)
        );
    });
    expect(relativos).toEqual([]);
  });

  test("o botao volta para a vitrine", async ({ page }) => {
    await page.goto("/nao-existe");
    await page.getByRole("link", { name: "Voltar para a vitrine" }).click();
    await expect(page).toHaveURL(/index\.html$/);
    await expect(page.locator(".grade .card").first()).toBeVisible();
  });

  test("nao e indexavel", async ({ page }) => {
    await page.goto("/404.html");
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
      "content",
      "noindex"
    );
  });

  test("sem rolagem horizontal", async ({ page }) => {
    await page.goto("/404.html");
    await expect(page.locator("h1")).toBeVisible();
    await semRolagemHorizontal(page);
  });
});
