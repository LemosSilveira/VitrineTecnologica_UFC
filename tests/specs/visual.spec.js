/* ============================================================
   visual.spec.js — comparacao visual antes/depois.

   Congela a aparencia da home e de 3 paginas de detalhe. E a porta de
   saida da Fase 2 do PRD (6.5): a extracao de htmlCard/htmlTrl/htmlSecao/
   htmlDiferenciais para js/render.js nao pode mudar um pixel.

   Tolerancia: 0,1% dos pixels (maxDiffPixelRatio no playwright.config.js).

   Para regravar as referencias de proposito:
       npm run visual:atualizar
   ============================================================ */
"use strict";

const { test, expect } = require("@playwright/test");

/* Uma referencia por viewport duplicaria o custo sem ganho: a extracao do
   render.js e independente de largura. Fica so no desktop. */
test.describe("Visual", () => {
  test.skip(
    ({ viewport }) => viewport.width < 1024,
    "referencias visuais so no desktop"
  );

  test.beforeEach(async ({ page }) => {
    /* Sem movimento: as revelacoes entram direto no estado final e o
       contador do hero nao anima, senao a captura pega um quadro do meio. */
    await page.emulateMedia({ reducedMotion: "reduce" });
  });

  /**
   * Espera fontes e imagens de `seletor`: sem isso a captura sai com texto
   * sem fonte ou com o shimmer da capa no lugar da imagem.
   *
   * As capas abaixo da dobra entram com `loading="lazy"` e nunca ficariam
   * `complete` numa captura de elemento — por isso viram `eager` antes.
   */
  async function pronta(page, seletor = "body") {
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(async (sel) => {
      const imgs = Array.from(document.querySelectorAll(`${sel} img`));
      imgs.forEach((i) => {
        if (i.loading === "lazy") i.loading = "eager";
      });
      await Promise.all(
        imgs
          .filter((i) => !i.complete)
          .map(
            (i) =>
              new Promise((ok) => {
                i.addEventListener("load", ok, { once: true });
                i.addEventListener("error", ok, { once: true });
              })
          )
      );
    }, seletor);
  }

  test("home", async ({ page }) => {
    await page.goto("/index.html");
    await expect(page.locator(".grade .card")).toHaveCount(60);

    /* A pagina inteira com as 60 capas da uma referencia de ~9 MB, pesada
       demais para versionar. Duas fileiras cobrem o RENDER.card igual, e o
       resto da pagina (hero, sobre, rodape) continua na captura.

       Esconde pelo CSSOM, nao com addStyleTag: a CSP do site nao permite
       <style> inline, e o proprio Playwright e bloqueado por ela. */
    await page.evaluate(() => {
      document.querySelectorAll(".grade .card").forEach((c, i) => {
        if (i >= 8) c.style.display = "none";
      });
    });
    await pronta(page);
    await expect(page).toHaveScreenshot("home.png", { fullPage: true });
  });

  test("home — hero", async ({ page }) => {
    await page.goto("/index.html");
    await pronta(page, ".hero");
    await expect(page.locator(".hero")).toHaveScreenshot("home-hero.png");
  });

  test("home — card", async ({ page }) => {
    await page.goto("/index.html");
    await pronta(page, ".grade .card:first-child");
    await expect(page.locator(".grade .card").first()).toHaveScreenshot("card.png");
  });

  test("home — card de modelo de utilidade", async ({ page }) => {
    await page.goto("/index.html");
    await page.locator('[data-tipo="MU"]').click();
    await expect(page.locator(".grade .card").first()).toBeVisible();
    await pronta(page, ".grade .card:first-child");
    await expect(page.locator(".grade .card").first()).toHaveScreenshot("card-mu.png");
  });

  test("home — previa no hover", async ({ page }) => {
    await page.goto("/index.html");
    await page.locator(".grade .card").first().hover();
    await expect(page.locator(".previa")).toHaveClass(/is-visivel/);
    await pronta(page, ".previa");
    await expect(page.locator(".previa")).toHaveScreenshot("previa.png");
  });

  /* Tres detalhes com formatos diferentes de ficha:
     1  — texto completo, com TRL e diferenciais
     12 — titulo com caracteres fora das fontes da marca (tau, subscritos)
     47 — titulo vindo do texto do PDF, nao do nome do arquivo             */
  for (const id of [1, 12, 47]) {
    test(`detalhe ${id}`, async ({ page }) => {
      await page.goto(`/patente.html?id=${id}`);
      await expect(page.locator("h1")).toBeVisible();
      await pronta(page);
      await expect(page).toHaveScreenshot(`detalhe-${id}.png`, { fullPage: true });
    });
  }

  test("404", async ({ page }) => {
    await page.goto("/404.html");
    await pronta(page);
    await expect(page).toHaveScreenshot("404.png", { fullPage: true });
  });
});
