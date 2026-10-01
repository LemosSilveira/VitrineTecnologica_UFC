/* ============================================================
   patente.spec.js — regressao da pagina de detalhe:
   conteudo, TRL, lightbox, navegacao circular e relacionadas.
   ============================================================ */
"use strict";

const { test, expect } = require("@playwright/test");
const { ESPERADO, lerDados, vigiaConsole, semRolagemHorizontal } = require("./_ajuda");

/** Carrega os dados uma vez, fora da pagina de detalhe. */
async function dados(page) {
  await page.goto("/index.html");
  return lerDados(page);
}

test.describe("Detalhe", () => {
  test("as 60 paginas abrem com titulo e capa, sem erro", async ({ page }) => {
    const problemas = vigiaConsole(page);
    const { patentes } = await dados(page);
    expect(patentes).toHaveLength(ESPERADO.patentes);

    for (const p of patentes) {
      await page.goto(`/patente.html?id=${p.id}`);
      await expect(page.locator("h1")).toHaveText(p.titulo);
      await expect(page).toHaveTitle(`${p.titulo} — Vitrine de Patentes UFC`);
      await expect(page.locator(".patente-topo__capa")).toHaveAttribute(
        "src",
        p.imagens.capa800
      );
    }

    expect(problemas, problemas.join("\n")).toEqual([]);
  });

  test("cabecalho traz area, tipo por extenso, numero e ano", async ({ page }) => {
    const { patentes } = await dados(page);
    const p = patentes[0];
    await page.goto(`/patente.html?id=${p.id}`);

    await expect(page.locator(".patente-topo .eyebrow")).toHaveText(p.categoria);
    await expect(page.locator(".badge--forte")).toHaveText(p.tipo.nome);
    await expect(page.locator(".patente-topo__meta")).toContainText(p.numero);
    await expect(page.locator(".patente-topo__meta")).toContainText(String(p.ano));
  });

  test("as secoes da ficha saem de secoes{} na ordem do PRD", async ({ page }) => {
    const { patentes } = await dados(page);
    const p = patentes.find(
      (x) => x.secoes && x.secoes.oQueE && x.secoes.problema && x.secoes.beneficio
    );
    await page.goto(`/patente.html?id=${p.id}`);

    const titulos = await page
      .locator(".patente-corpo .ficha-secao h2")
      .evaluateAll((els) => els.map((e) => e.textContent.trim()));

    expect(titulos[0]).toBe("O que é?");
    expect(titulos).toContain("Problema que resolve");
    expect(titulos).toContain("Benefício principal");
    await expect(page.locator(".ficha-secao").first()).toContainText(p.secoes.oQueE);
  });

  test("os diferenciais viram lista com um item por entrada", async ({ page }) => {
    const { patentes } = await dados(page);
    const p = patentes.find(
      (x) => x.secoes && x.secoes.diferenciais && x.secoes.diferenciais.length
    );
    await page.goto(`/patente.html?id=${p.id}`);

    const itens = page.locator(".diferenciais li");
    await expect(itens).toHaveCount(p.secoes.diferenciais.length);
    await expect(itens.first()).toContainText(p.secoes.diferenciais[0]);
  });

  test("o medidor de TRL acende so os segmentos da faixa", async ({ page }) => {
    const { patentes } = await dados(page);
    const p = patentes.find((x) => x.trl);
    await page.goto(`/patente.html?id=${p.id}`);

    await expect(page.locator(".trl__seg")).toHaveCount(9);
    await expect(page.locator(".trl__seg.is-ativo")).toHaveCount(
      p.trl.max - p.trl.min + 1
    );
    await expect(page.locator(".trl__rotulo")).toContainText(p.trl.texto);
    await expect(page.locator(".trl__barra")).toHaveAttribute(
      "aria-label",
      new RegExp(`Maturidade tecnol[oó]gica ${p.trl.texto.replace(/[-—–]/g, ".")}`)
    );
  });

  test("a coluna do documento liga a ficha e o PDF", async ({ page }) => {
    const { patentes } = await dados(page);
    const p = patentes[0];
    await page.goto(`/patente.html?id=${p.id}`);

    await expect(page.locator(".doc__thumb img")).toHaveAttribute(
      "src",
      p.imagens.ficha600
    );
    const baixar = page.locator(`.doc a[href="${p.pdf}"]`);
    await expect(baixar).toHaveAttribute(
      "download",
      `ficha-${p.numero.replace(/\s/g, "-")}.pdf`
    );
    /* o PDF precisa existir de verdade no disco */
    const resp = await page.request.head(`/${p.pdf}`);
    expect(resp.status()).toBe(200);
  });

  test('"Tenho interesse" fica escondido enquanto o e-mail estiver vazio', async ({
    page,
  }) => {
    const { patentes } = await dados(page);
    await page.goto(`/patente.html?id=${patentes[0].id}`);

    const email = await page.evaluate(() => window.CONFIG.contatoEmail);
    await expect(page.locator('.doc a[href^="mailto:"]')).toHaveCount(email ? 1 : 0);
  });

  test.describe("Lightbox", () => {
    test("abre pelo botao, troca para a ficha grande e fecha com Esc", async ({
      page,
    }) => {
      const { patentes } = await dados(page);
      const p = patentes[0];
      await page.goto(`/patente.html?id=${p.id}`);

      const dlg = page.locator("[data-lightbox]");
      await expect(dlg).toBeHidden();

      await page.locator(".doc__thumb").click();
      await expect(dlg).toBeVisible();
      await expect(dlg.locator(".lightbox__img")).toHaveAttribute(
        "src",
        p.imagens.ficha1620
      );

      await page.keyboard.press("Escape");
      await expect(dlg).toBeHidden();
    });

    test("o botao de zoom alterna o rotulo", async ({ page }) => {
      const { patentes } = await dados(page);
      await page.goto(`/patente.html?id=${patentes[0].id}`);
      await page.locator(".doc__thumb").click();

      const rotulo = page.locator("[data-zoom-rotulo]");
      await expect(rotulo).toHaveText("Ampliar");
      await page.locator("[data-zoom]").click();
      await expect(rotulo).toHaveText("Ajustar à tela");
      await page.locator("[data-zoom]").click();
      await expect(rotulo).toHaveText("Ampliar");
    });

    test("ao fechar, o foco volta para o botao que abriu", async ({ page }) => {
      const { patentes } = await dados(page);
      await page.goto(`/patente.html?id=${patentes[0].id}`);

      const botao = page.locator(".doc__acoes [data-abre-lightbox]");
      await botao.click();
      await expect(page.locator("[data-lightbox]")).toBeVisible();

      await page.locator("[data-fechar]").click();
      await expect(page.locator("[data-lightbox]")).toBeHidden();
      await expect(botao).toBeFocused();
    });
  });

  test.describe("Navegacao entre patentes", () => {
    test("anterior e proxima apontam para os vizinhos", async ({ page }) => {
      const { patentes } = await dados(page);
      const i = 10;
      await page.goto(`/patente.html?id=${patentes[i].id}`);

      await expect(page.locator('.nav-patentes a[rel="prev"]')).toHaveAttribute(
        "href",
        `patente.html?id=${patentes[i - 1].id}`
      );
      await expect(page.locator('.nav-patentes a[rel="next"]')).toHaveAttribute(
        "href",
        `patente.html?id=${patentes[i + 1].id}`
      );
    });

    test("a navegacao e circular nas pontas", async ({ page }) => {
      const { patentes } = await dados(page);
      const primeira = patentes[0];
      const ultima = patentes[patentes.length - 1];

      await page.goto(`/patente.html?id=${primeira.id}`);
      await expect(page.locator('.nav-patentes a[rel="prev"]')).toHaveAttribute(
        "href",
        `patente.html?id=${ultima.id}`
      );

      await page.goto(`/patente.html?id=${ultima.id}`);
      await expect(page.locator('.nav-patentes a[rel="next"]')).toHaveAttribute(
        "href",
        `patente.html?id=${primeira.id}`
      );
    });
  });

  test("as relacionadas sao da mesma area e no maximo 4", async ({ page }) => {
    const { patentes } = await dados(page);
    const p = patentes.find(
      (x) => patentes.filter((y) => y.categoria === x.categoria).length > 1
    );
    await page.goto(`/patente.html?id=${p.id}`);

    const sec = page.locator("[data-relacionadas]");
    await expect(sec).toBeVisible();
    await expect(sec.locator("h2")).toHaveText(`Outras patentes em ${p.categoria}`);

    const cards = sec.locator(".card");
    const n = await cards.count();
    expect(n).toBeGreaterThan(0);
    expect(n).toBeLessThanOrEqual(4);

    const ids = await cards.evaluateAll((els) => els.map((e) => Number(e.dataset.id)));
    const porId = new Map(patentes.map((x) => [x.id, x]));
    for (const id of ids) {
      expect(id).not.toBe(p.id);
      expect(porId.get(id).categoria).toBe(p.categoria);
    }
  });

  test("as migalhas voltam para a home ja filtrada pela area", async ({ page }) => {
    const { patentes } = await dados(page);
    const p = patentes[0];
    await page.goto(`/patente.html?id=${p.id}`);

    const areaLink = page.locator(".migalhas a").nth(1);
    await expect(areaLink).toHaveText(p.categoria);
    await expect(areaLink).toHaveAttribute("href", /index\.html\?area=.+#patentes/);
    await expect(page.locator('.migalhas [aria-current="page"]')).toHaveText(p.numero);
  });

  test.describe("id invalido cai na 404", () => {
    for (const bruto of ["", "0", "999", "abc", "1x", "-1"]) {
      test(`id=${JSON.stringify(bruto)}`, async ({ page }) => {
        await page.goto(`/patente.html?id=${encodeURIComponent(bruto)}`);
        await expect(page).toHaveURL(/404\.html$/);
      });
    }

    test("sem query string nenhuma", async ({ page }) => {
      await page.goto("/patente.html");
      await expect(page).toHaveURL(/404\.html$/);
    });
  });

  test("sem rolagem horizontal", async ({ page }) => {
    const { patentes } = await dados(page);
    await page.goto(`/patente.html?id=${patentes[0].id}`);
    await expect(page.locator("h1")).toBeVisible();
    await semRolagemHorizontal(page);
  });
});
