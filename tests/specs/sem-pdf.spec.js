/* ============================================================
   sem-pdf.spec.js — o site com uma patente sem PDF (PRD 4.4 / 6.4).

   Nenhuma das 60 patentes reais esta nesse caso hoje, entao os testes
   injetam uma patente ficticia em window.PATENTES antes dos scripts da
   pagina rodarem. E o unico jeito de cobrir o caminho dos nulos sem sujar
   o acervo -- e ele PRECISA estar coberto: a primeira patente cadastrada
   manualmente pelo painel vai cair exatamente aqui.
   ============================================================ */
"use strict";

const { test, expect } = require("@playwright/test");
const {
  vigiaConsole,
  semRolagemHorizontal,
  semViolacoesAxe,
  passaOMouseNoCard,
} = require("./_ajuda");

const ID = 9001;

/**
 * Injeta uma patente sem PDF (pdf, ficha600 e ficha1620 nulos) reutilizando
 * a capa de uma patente real, para que as imagens existam de verdade.
 *
 * A injecao acontece interceptando a resposta de `js/data/patentes.js` e
 * acrescentando codigo ao fim do arquivo. Nao da para usar
 * `addInitScript`: ele roda antes de `window.PATENTES` existir, e um
 * `DOMContentLoaded` rodaria DEPOIS de home.js e patente.js, que sao
 * `defer` e ja terao montado a pagina.
 */
async function comPatenteSemPdf(page, extra = {}) {
  await page.route("**/js/data/patentes.js", async (route) => {
    const resp = await route.fetch();
    const original = await resp.text();
    const acrescimo = `
;(function () {
  var modelo = window.PATENTES[0];
  var nova = Object.assign({}, modelo, {
    id: ${ID},
    slug: "${ID}-tecnologia-sem-ficha",
    numero: "BR 10 2026 099999-9",
    ano: 2026,
    titulo: "Tecnologia cadastrada sem ficha em PDF",
    resumo: "Resumo desta tecnologia, que entrou na vitrine sem o PDF da ficha.",
    secoes: {
      oQueE: "Uma tecnologia cadastrada manualmente, sem a ficha técnica em PDF.",
      problema: null,
      exemploDeUso: null,
      diferenciais: null,
      beneficio: null
    },
    imagens: Object.assign({}, modelo.imagens, { ficha600: null, ficha1620: null }),
    pdf: null
  });
  Object.assign(nova, ${JSON.stringify(extra)});
  window.PATENTES.push(nova);
})();
`;
    await route.fulfill({
      response: resp,
      body: original + acrescimo,
      headers: { ...resp.headers(), "content-length": undefined },
    });
  });
}

test.describe("Patente sem PDF", () => {
  test.describe("Home", () => {
    test("o card aparece na grade como os outros", async ({ page }) => {
      const problemas = vigiaConsole(page);
      await comPatenteSemPdf(page);
      await page.goto("/index.html");

      const card = page.locator(`.card[data-id="${ID}"]`);
      await expect(card).toBeVisible();
      await expect(card.locator(".card__titulo")).toHaveText(
        "Tecnologia cadastrada sem ficha em PDF"
      );
      expect(problemas, problemas.join("\n")).toEqual([]);
    });

    test("a busca encontra pelo titulo", async ({ page }) => {
      await comPatenteSemPdf(page);
      await page.goto("/index.html");
      await page.getByRole("searchbox").fill("sem ficha em PDF");
      await expect(page.locator(".grade .card")).toHaveCount(1);
      await expect(page.locator(".grade .card").first()).toHaveAttribute(
        "data-id",
        String(ID)
      );
    });

    test.describe("Previa no hover", () => {
      test.skip(({ viewport }) => viewport.width < 1024, "so no desktop");

      test("cai para a capa e mostra o resumo no lugar da ficha", async ({ page }) => {
        await comPatenteSemPdf(page);
        await page.goto("/index.html");
        await passaOMouseNoCard(page, `.card[data-id="${ID}"]`);

        const previa = page.locator(".previa");
        await expect(previa).toHaveClass(/is-visivel/);
        await expect(previa).toHaveClass(/previa--sem-ficha/);

        /* a imagem e a capa, nao a ficha */
        await expect(previa.locator(".previa__img")).toHaveAttribute(
          "src",
          /capa-800\.webp$/
        );
        await expect(previa.locator("[data-previa-resumo]")).toBeVisible();
        await expect(previa.locator("[data-previa-resumo]")).toContainText(
          "sem o PDF da ficha"
        );
        await expect(previa.locator("[data-previa-cta]")).toHaveText(
          /ver os detalhes/
        );
      });

      test("a previa continua dentro da viewport", async ({ page, viewport }) => {
        await comPatenteSemPdf(page);
        await page.goto("/index.html");
        await passaOMouseNoCard(page, `.card[data-id="${ID}"]`);
        await expect(page.locator(".previa")).toHaveClass(/is-visivel/);

        const cx = await page.locator(".previa").boundingBox();
        expect(cx.x).toBeGreaterThanOrEqual(0);
        expect(cx.y).toBeGreaterThanOrEqual(0);
        expect(cx.x + cx.width).toBeLessThanOrEqual(viewport.width + 1);
        expect(cx.y + cx.height).toBeLessThanOrEqual(viewport.height + 1);
      });

      test("uma patente COM ficha volta ao layout normal", async ({ page }) => {
        await comPatenteSemPdf(page);
        await page.goto("/index.html");

        /* Os dois cards sao vizinhos na grade de proposito: a patente
           ficticia entra no fim, logo depois da 60. Passar o mouse entre
           cards distantes obrigaria a uma rolagem longa, e a previa fecha em
           qualquer evento de scroll -- o que testaria o scroll, nao a troca
           de estado da previa. */
        await passaOMouseNoCard(page, `.card[data-id="${ID}"]`);
        await expect(page.locator(".previa")).toHaveClass(/previa--sem-ficha/);
        await expect(page.locator("[data-previa-resumo]")).toBeVisible();

        /* a mesma previa e reaproveitada entre os cards: a classe e o resumo
           precisam sair ao chegar numa patente que tem ficha */
        await page.locator('.card[data-id="60"]').hover();
        await expect(page.locator(".previa")).toHaveClass(/is-visivel/);
        await expect(page.locator(".previa")).not.toHaveClass(/previa--sem-ficha/);
        await expect(page.locator("[data-previa-resumo]")).toBeHidden();
        await expect(page.locator(".previa__img")).toHaveAttribute(
          "src",
          /ficha-600\.webp$/
        );
      });
    });
  });

  test.describe("Detalhe", () => {
    test('o card "Documento oficial" some', async ({ page }) => {
      const problemas = vigiaConsole(page);
      await comPatenteSemPdf(page);
      await page.goto(`/patente.html?id=${ID}`);

      await expect(page.locator("h1")).toHaveText(
        "Tecnologia cadastrada sem ficha em PDF"
      );
      await expect(page.locator(".doc")).toHaveCount(0);
      await expect(page.locator("[data-abre-lightbox]")).toHaveCount(0);
      await expect(page.locator('a[download]')).toHaveCount(0);
      expect(problemas, problemas.join("\n")).toEqual([]);
    });

    test("a coluna de texto passa a ocupar a largura toda", async ({ page }) => {
      await comPatenteSemPdf(page);
      await page.goto(`/patente.html?id=${ID}`);

      const corpo = page.locator(".patente-corpo");
      await expect(corpo).toHaveClass(/patente-corpo--sem-doc/);
      const colunas = await corpo.evaluate(
        (el) => getComputedStyle(el).gridTemplateColumns
      );
      expect(colunas.trim().split(/\s+/)).toHaveLength(1);
    });

    test("o lightbox nao e montado", async ({ page }) => {
      await comPatenteSemPdf(page);
      await page.goto(`/patente.html?id=${ID}`);
      await expect(page.locator("[data-lightbox]")).toHaveCount(0);
    });

    test("as secoes preenchidas continuam aparecendo", async ({ page }) => {
      await comPatenteSemPdf(page);
      await page.goto(`/patente.html?id=${ID}`);
      await expect(page.locator(".ficha-secao").first()).toContainText(
        "cadastrada manualmente"
      );
    });

    test("sem texto nenhum, cai para o resumo em vez de pagina vazia", async ({
      page,
    }) => {
      await comPatenteSemPdf(page, {
        secoes: {
          oQueE: null,
          problema: null,
          exemploDeUso: null,
          diferenciais: null,
          beneficio: null,
        },
      });
      await page.goto(`/patente.html?id=${ID}`);
      await expect(page.locator(".ficha-secao")).toHaveCount(1);
      await expect(page.locator(".ficha-secao h2")).toHaveText(
        "Sobre esta tecnologia"
      );
      await expect(page.locator(".ficha-imagem")).toHaveCount(0);
    });

    test("a navegacao anterior/proxima continua funcionando", async ({ page }) => {
      await comPatenteSemPdf(page);
      await page.goto(`/patente.html?id=${ID}`);
      await expect(page.locator('.nav-patentes a[rel="prev"]')).toHaveAttribute(
        "href",
        /patente\.html\?id=\d+/
      );
      await expect(page.locator('.nav-patentes a[rel="next"]')).toHaveAttribute(
        "href",
        /patente\.html\?id=\d+/
      );
    });

    test("sem rolagem horizontal", async ({ page }) => {
      await comPatenteSemPdf(page);
      await page.goto(`/patente.html?id=${ID}`);
      await expect(page.locator("h1")).toBeVisible();
      await semRolagemHorizontal(page);
    });

    test("sem violacoes serious/critical no axe", async ({ page }) => {
      await comPatenteSemPdf(page);
      await page.goto(`/patente.html?id=${ID}`);
      await expect(page.locator("h1")).toBeVisible();
      await semViolacoesAxe(page);
    });
  });
});
