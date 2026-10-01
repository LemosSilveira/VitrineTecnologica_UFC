/* ============================================================
   acessibilidade.spec.js — axe-core nas tres paginas, mais os
   pontos que o axe nao pega sozinho (teclado, foco, hierarquia).
   Criterio: zero violacoes serious/critical.
   ============================================================ */
"use strict";

const { test, expect } = require("@playwright/test");
const { lerDados, semViolacoesAxe } = require("./_ajuda");

test.describe("Acessibilidade", () => {
  test("home sem violacoes serious/critical", async ({ page }) => {
    await page.goto("/index.html");
    await expect(page.locator(".grade .card").first()).toBeVisible();
    await semViolacoesAxe(page);
  });

  test("home com a grade vazia", async ({ page }) => {
    await page.goto("/index.html");
    await page.getByRole("searchbox").fill("zzzznaoexiste");
    await expect(page.locator(".vazio")).toBeVisible();
    await semViolacoesAxe(page);
  });

  test("detalhe sem violacoes serious/critical", async ({ page }) => {
    await page.goto("/index.html");
    const { patentes } = await lerDados(page);
    await page.goto(`/patente.html?id=${patentes[0].id}`);
    await expect(page.locator("h1")).toBeVisible();
    await semViolacoesAxe(page);
  });

  test("detalhe com o lightbox aberto", async ({ page }) => {
    await page.goto("/index.html");
    const { patentes } = await lerDados(page);
    await page.goto(`/patente.html?id=${patentes[0].id}`);
    await page.locator(".doc__thumb").click();
    await expect(page.locator("[data-lightbox]")).toBeVisible();
    await semViolacoesAxe(page);
  });

  test("404 sem violacoes serious/critical", async ({ page }) => {
    await page.goto("/404.html");
    await expect(page.locator("h1")).toBeVisible();
    await semViolacoesAxe(page);
  });

  test("o link de pular chega ao conteudo", async ({ page }) => {
    await page.goto("/index.html");
    await page.keyboard.press("Tab");
    const pular = page.locator(".pular-link");
    await expect(pular).toBeFocused();
    await expect(pular).toBeVisible();
    await pular.press("Enter");
    await expect(page).toHaveURL(/#patentes$/);
  });

  test("ha exatamente um h1 por pagina", async ({ page }) => {
    await page.goto("/index.html");
    await expect(page.locator("h1")).toHaveCount(1);

    const { patentes } = await lerDados(page);
    await page.goto(`/patente.html?id=${patentes[0].id}`);
    await expect(page.locator("h1")).toHaveCount(1);

    await page.goto("/404.html");
    await expect(page.locator("h1")).toHaveCount(1);
  });

  test("toda imagem da grade tem alt descritivo", async ({ page }) => {
    await page.goto("/index.html");
    await expect(page.locator(".grade .card").first()).toBeVisible();

    const semAlt = await page.locator(".grade img").evaluateAll((els) =>
      els.filter((e) => !e.getAttribute("alt")).length
    );
    expect(semAlt).toBe(0);
  });

  test("links externos avisam que abrem em nova aba", async ({ page }) => {
    await page.goto("/index.html");
    const externos = page.locator('a[target="_blank"]');
    const n = await externos.count();
    expect(n).toBeGreaterThan(0);

    for (let i = 0; i < n; i++) {
      /* rel=noopener e obrigatorio em todo link que abre nova aba */
      await expect(externos.nth(i)).toHaveAttribute("rel", /noopener/);
    }
  });

  test("os controles de filtro tem nome acessivel", async ({ page }) => {
    await page.goto("/index.html");
    await expect(page.getByRole("searchbox")).toHaveAccessibleName(/Buscar patentes/);
    await expect(page.getByRole("radiogroup")).toHaveAccessibleName("Tipo de proteção");
    await expect(page.getByRole("combobox")).toHaveAccessibleName("Ordenar por");
    await expect(page.getByRole("group", { name: /área tecnológica/i })).toBeVisible();
  });
});
