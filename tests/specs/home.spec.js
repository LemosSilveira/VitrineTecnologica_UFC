/* ============================================================
   home.spec.js — regressao da home: hero, grade, busca, filtros,
   ordenacao, estado na URL e previa no hover.
   ============================================================ */
"use strict";

const { test, expect } = require("@playwright/test");
const {
  ESPERADO,
  lerDados,
  vigiaConsole,
  semRolagemHorizontal,
  valorDoContador,
  esperaRolagemParar,
} = require("./_ajuda");

const cards = (page) => page.locator(".grade .card");

test.describe("Home", () => {
  test("renderiza as 60 patentes sem erro de console", async ({ page }) => {
    const problemas = vigiaConsole(page);
    await page.goto("/index.html");

    await expect(cards(page)).toHaveCount(ESPERADO.patentes);
    expect(problemas, problemas.join("\n")).toEqual([]);
  });

  test("os numeros do hero saem de window.PATENTES", async ({ page }) => {
    await page.goto("/index.html");
    const { patentes, categorias } = await lerDados(page);

    const pi = patentes.filter((p) => p.tipo.sigla === "PI").length;
    const mu = patentes.filter((p) => p.tipo.sigla === "MU").length;

    expect(patentes).toHaveLength(ESPERADO.patentes);
    expect(categorias).toHaveLength(ESPERADO.areas);
    expect(pi + mu).toBe(patentes.length);

    await expect(page.locator('[data-numero="total"]')).toHaveAttribute(
      "data-conta",
      String(patentes.length)
    );
    expect(await valorDoContador(page, "total")).toBe(patentes.length);
    expect(await valorDoContador(page, "areas")).toBe(categorias.length);
    expect(await valorDoContador(page, "pi")).toBe(pi);
    expect(await valorDoContador(page, "mu")).toBe(mu);
  });

  test("cada card traz capa, titulo, numero e link para o detalhe", async ({ page }) => {
    await page.goto("/index.html");
    const { patentes } = await lerDados(page);
    const primeira = patentes[0];

    const card = page.locator(`.card[data-id="${primeira.id}"]`);
    await expect(card.locator(".card__titulo")).toHaveText(primeira.titulo);
    await expect(card.locator(".card__numero")).toHaveText(primeira.numero);
    await expect(card.locator(".badge")).toHaveText(primeira.tipo.sigla);
    await expect(card.locator(".card__link")).toHaveAttribute(
      "href",
      `patente.html?id=${primeira.id}`
    );
    await expect(card.locator("img")).toHaveAttribute("src", primeira.imagens.capa400);
  });

  test("todas as capas da primeira dobra carregam de verdade", async ({ page }) => {
    await page.goto("/index.html");
    // as 4 primeiras entram com fetchpriority=high, sem lazy
    for (let i = 0; i < 4; i++) {
      const img = cards(page).nth(i).locator("img");
      await expect(img).toHaveJSProperty("complete", true);
      expect(await img.evaluate((el) => el.naturalWidth)).toBeGreaterThan(0);
    }
  });

  test.describe("Busca", () => {
    test("ignora acento e caixa", async ({ page }) => {
      await page.goto("/index.html");
      const busca = page.getByRole("searchbox");

      await busca.fill("camarao");
      /* Espera o debounce de 150ms: a patente 1 e "Camarão em Pó Natural" e
         tambem e o primeiro card da grade sem filtro, entao conferir o
         titulo passaria antes de o filtro rodar. */
      await expect(cards(page)).not.toHaveCount(ESPERADO.patentes);
      await expect(cards(page).first().locator(".card__titulo")).toContainText(
        /camar[aã]o/i
      );
      const semAcento = await cards(page).count();
      expect(semAcento).toBeGreaterThan(0);

      await busca.fill("CAMARÃO");
      await expect(cards(page)).toHaveCount(semAcento);
    });

    test("encontra pelo numero, com e sem hifen", async ({ page }) => {
      await page.goto("/index.html");
      const { patentes } = await lerDados(page);
      const alvo = patentes[0];
      const busca = page.getByRole("searchbox");

      await busca.fill(alvo.numero);
      await expect(cards(page)).toHaveCount(1);
      await expect(cards(page).first()).toHaveAttribute("data-id", String(alvo.id));

      await busca.fill(alvo.numero.replace(/[\s-]/g, ""));
      await expect(cards(page)).toHaveCount(1);
      await expect(cards(page).first()).toHaveAttribute("data-id", String(alvo.id));
    });

    test("termo sem resultado mostra o estado vazio e o botao de limpar", async ({
      page,
    }) => {
      await page.goto("/index.html");
      await page.getByRole("searchbox").fill("zzzznaoexiste");

      await expect(cards(page)).toHaveCount(0);
      await expect(page.locator(".vazio")).toContainText("Nenhuma patente encontrada");

      await page.locator(".vazio [data-limpar]").click();
      await expect(cards(page)).toHaveCount(ESPERADO.patentes);
    });

    test("Escape no campo limpa a busca", async ({ page }) => {
      await page.goto("/index.html");
      const busca = page.getByRole("searchbox");
      await busca.fill("camarao");
      await expect(cards(page)).not.toHaveCount(ESPERADO.patentes);

      await busca.press("Escape");
      await expect(busca).toHaveValue("");
      await expect(cards(page)).toHaveCount(ESPERADO.patentes);
    });

    test('a tecla "/" foca a busca', async ({ page }) => {
      await page.goto("/index.html");
      await page.locator("h1").click();
      await page.keyboard.press("/");
      await expect(page.getByRole("searchbox")).toBeFocused();
    });
  });

  test.describe("Filtros", () => {
    test("o chip de area filtra e bate com o total declarado", async ({ page }) => {
      await page.goto("/index.html");
      const { categorias } = await lerDados(page);
      const area = categorias[0];

      await page.locator(`.chip[data-area="${area.nome}"]`).click();
      await expect(cards(page)).toHaveCount(area.total);
      await expect(page.locator(`.chip[data-area="${area.nome}"]`)).toHaveAttribute(
        "aria-pressed",
        "true"
      );
    });

    test("o chip Todas traz o total geral", async ({ page }) => {
      await page.goto("/index.html");
      await expect(page.locator('.chip[data-area=""] .chip__total')).toHaveText(
        String(ESPERADO.patentes)
      );
    });

    test("ha um chip por area, mais o Todas", async ({ page }) => {
      await page.goto("/index.html");
      await expect(page.locator("[data-areas] .chip")).toHaveCount(ESPERADO.areas + 1);
    });

    test("o segmentado de tipo filtra PI e MU", async ({ page }) => {
      await page.goto("/index.html");
      const { patentes } = await lerDados(page);

      for (const sigla of ["PI", "MU"]) {
        await page.locator(`[data-tipo="${sigla}"]`).click();
        const n = patentes.filter((p) => p.tipo.sigla === sigla).length;
        await expect(cards(page)).toHaveCount(n);
        await expect(page.locator(`[data-tipo="${sigla}"]`)).toHaveAttribute(
          "aria-checked",
          "true"
        );
      }
    });

    test("as setas percorrem o radiogroup de tipo", async ({ page }) => {
      await page.goto("/index.html");
      await page.locator('[data-tipo=""]').focus();
      await page.keyboard.press("ArrowRight");
      await expect(page.locator('[data-tipo="PI"]')).toBeFocused();
      await expect(page.locator('[data-tipo="PI"]')).toHaveAttribute(
        "aria-checked",
        "true"
      );
    });

    test("area e tipo se combinam", async ({ page }) => {
      await page.goto("/index.html");
      const { patentes, categorias } = await lerDados(page);
      const area = categorias.find((c) =>
        patentes.some((p) => p.categoria === c.nome && p.tipo.sigla === "PI")
      );

      await page.locator(`.chip[data-area="${area.nome}"]`).click();
      await page.locator('[data-tipo="PI"]').click();

      const n = patentes.filter(
        (p) => p.categoria === area.nome && p.tipo.sigla === "PI"
      ).length;
      await expect(cards(page)).toHaveCount(n);
    });
  });

  test.describe("Ordenacao", () => {
    test("vitrine ordena por id crescente", async ({ page }) => {
      await page.goto("/index.html");
      const ids = await cards(page).evaluateAll((els) =>
        els.map((e) => Number(e.dataset.id))
      );
      expect(ids).toEqual([...ids].sort((a, b) => a - b));
    });

    test("recentes ordena por ano decrescente", async ({ page }) => {
      await page.goto("/index.html");
      await page.getByLabel("Ordenar por").selectOption("recentes");

      const { patentes } = await lerDados(page);
      const porId = new Map(patentes.map((p) => [p.id, p]));
      const anos = (
        await cards(page).evaluateAll((els) => els.map((e) => Number(e.dataset.id)))
      ).map((id) => porId.get(id).ano);

      expect(anos).toEqual([...anos].sort((a, b) => b - a));
    });

    test("titulo ordena A-Z ignorando acento", async ({ page }) => {
      await page.goto("/index.html");
      await page.getByLabel("Ordenar por").selectOption("titulo");

      const titulos = await cards(page)
        .locator(".card__titulo")
        .evaluateAll((els) => els.map((e) => e.textContent));
      const ordenados = [...titulos].sort((a, b) =>
        a.localeCompare(b, "pt-BR", { sensitivity: "base" })
      );
      expect(titulos).toEqual(ordenados);
    });
  });

  test.describe("Estado na URL", () => {
    test("busca, area, tipo e ordem vao para a query string", async ({ page }) => {
      await page.goto("/index.html");
      const { categorias } = await lerDados(page);

      await page.getByRole("searchbox").fill("camarao");
      await page.locator(`.chip[data-area="${categorias[0].nome}"]`).click();
      await page.locator('[data-tipo="PI"]').click();
      await page.getByLabel("Ordenar por").selectOption("titulo");

      await expect(page).toHaveURL(/q=camarao/);
      await expect(page).toHaveURL(/area=/);
      await expect(page).toHaveURL(/tipo=PI/);
      await expect(page).toHaveURL(/ordem=titulo/);
    });

    test("a URL restaura os filtros ao abrir", async ({ page }) => {
      await page.goto("/index.html");
      const { patentes, categorias } = await lerDados(page);
      const area = categorias[0];
      const slug = area.nome
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");

      await page.goto(`/index.html?area=${slug}&tipo=PI`);

      const n = patentes.filter(
        (p) => p.categoria === area.nome && p.tipo.sigla === "PI"
      ).length;
      await expect(cards(page)).toHaveCount(n);
      await expect(page.locator(`.chip[data-area="${area.nome}"]`)).toHaveAttribute(
        "aria-pressed",
        "true"
      );
      await expect(page.locator('[data-tipo="PI"]')).toHaveAttribute(
        "aria-checked",
        "true"
      );
    });

    test("ordem invalida na URL cai no padrao", async ({ page }) => {
      await page.goto("/index.html?ordem=inexistente");
      await expect(page.getByLabel("Ordenar por")).toHaveValue("vitrine");
      await expect(cards(page)).toHaveCount(ESPERADO.patentes);
    });
  });

  test.describe("Previa da ficha no hover", () => {
    /* A previa so existe em ponteiro fino e >= 1024px de largura. */
    test.skip(({ viewport }) => viewport.width < 1024, "so no desktop");

    test("abre no hover, mostra a ficha e o TRL", async ({ page }) => {
      await page.goto("/index.html");
      const { patentes } = await lerDados(page);
      const alvo = patentes[0];

      await page.locator(`.card[data-id="${alvo.id}"]`).hover();
      const previa = page.locator(".previa");
      await expect(previa).toHaveClass(/is-visivel/);
      await expect(previa.locator(".previa__img")).toHaveAttribute(
        "src",
        alvo.imagens.ficha600
      );
      if (alvo.trl) {
        await expect(previa.locator("[data-previa-trl]")).toContainText("TRL");
      }
    });

    test("fica dentro da viewport", async ({ page, viewport }) => {
      await page.goto("/index.html");
      await cards(page).first().hover();
      await expect(page.locator(".previa")).toHaveClass(/is-visivel/);

      const cx = await page.locator(".previa").boundingBox();
      expect(cx.x).toBeGreaterThanOrEqual(0);
      expect(cx.y).toBeGreaterThanOrEqual(0);
      expect(cx.x + cx.width).toBeLessThanOrEqual(viewport.width + 1);
      expect(cx.y + cx.height).toBeLessThanOrEqual(viewport.height + 1);
    });

    test("abre pelo foco do teclado e fecha com Esc", async ({ page }) => {
      await page.goto("/index.html");

      /* O card precisa estar na tela ANTES do foco: ver o comentario de
         esperaRolagemParar em _ajuda.js. */
      await cards(page).first().scrollIntoViewIfNeeded();
      await esperaRolagemParar(page);

      await cards(page).first().locator(".card__link").focus();

      const previa = page.locator(".previa");
      await expect(previa).toHaveClass(/is-visivel/);
      /* enquanto aberta, o link aponta para a previa como descricao */
      await expect(cards(page).first().locator(".card__link")).toHaveAttribute(
        "aria-describedby",
        "previa-ficha"
      );

      await page.keyboard.press("Escape");
      await expect(previa).not.toHaveClass(/is-visivel/);
    });

    test("nao abre com prefers-reduced-motion? (abre: o PRD so reduz o movimento)", async ({
      page,
    }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.goto("/index.html");
      await cards(page).first().hover();
      await expect(page.locator(".previa")).toHaveClass(/is-visivel/);
    });
  });

  test("prefers-reduced-motion: tudo ja entra visivel", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/index.html");

    await expect(cards(page)).toHaveCount(ESPERADO.patentes);
    const invisiveis = await page
      .locator("[data-revela]:not(.is-visivel)")
      .count();
    expect(invisiveis).toBe(0);
    /* contadores vao direto ao valor final, sem animar */
    await expect(page.locator('[data-numero="total"]')).toHaveText(
      String(ESPERADO.patentes)
    );
  });

  test("sem rolagem horizontal", async ({ page }) => {
    await page.goto("/index.html");
    await expect(cards(page)).toHaveCount(ESPERADO.patentes);
    await semRolagemHorizontal(page);
  });

  test("a rolagem volta ao lugar ao retornar do detalhe", async ({ page }) => {
    await page.goto("/index.html");
    await expect(cards(page)).toHaveCount(ESPERADO.patentes);

    await page.evaluate(() => window.scrollTo(0, 1200));
    await cards(page).nth(10).locator(".card__link").click();
    await expect(page).toHaveURL(/patente\.html\?id=/);

    await page.goBack();
    await expect(cards(page)).toHaveCount(ESPERADO.patentes);
    await expect
      .poll(() => page.evaluate(() => window.scrollY), { timeout: 5_000 })
      .toBeGreaterThan(600);
  });
});
