/* ============================================================
   Utilidades compartilhadas pelos specs.
   ============================================================ */
"use strict";

const { expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

/** Constantes da vitrine atual — mudam so quando o acervo muda. */
const ESPERADO = { patentes: 60, areas: 10 };

/** Le window.PATENTES / window.CATEGORIAS da pagina ja carregada. */
async function lerDados(page) {
  return page.evaluate(() => ({
    patentes: window.PATENTES,
    categorias: window.CATEGORIAS,
  }));
}

/**
 * Coleta erros de console e falhas de rede durante o teste.
 * Chame antes de navegar; o array vai sendo preenchido.
 */
function vigiaConsole(page) {
  const problemas = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") problemas.push(`console: ${msg.text()}`);
  });
  page.on("pageerror", (err) => problemas.push(`pageerror: ${err.message}`));
  page.on("requestfailed", (req) => {
    // requisicoes abortadas pela navegacao nao sao falha do site
    const erro = req.failure() && req.failure().errorText;
    if (erro === "net::ERR_ABORTED") return;
    problemas.push(`requestfailed: ${req.url()} (${erro})`);
  });
  return problemas;
}

/** O documento nao pode rolar na horizontal em nenhuma largura. */
async function semRolagemHorizontal(page) {
  const { scroll, cliente } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    cliente: document.documentElement.clientWidth,
  }));
  // 1px de folga para arredondamento de subpixel
  expect(scroll, `scrollWidth ${scroll} > clientWidth ${cliente}`).toBeLessThanOrEqual(
    cliente + 1
  );
}

/** axe-core: zero violacoes serious/critical (PRD 12.1 / README). */
async function semViolacoesAxe(page, { excluir = [] } = {}) {
  let builder = new AxeBuilder({ page }).withTags([
    "wcag2a",
    "wcag2aa",
    "wcag21a",
    "wcag21aa",
  ]);
  for (const sel of excluir) builder = builder.exclude(sel);

  const { violations } = await builder.analyze();
  const graves = violations.filter((v) =>
    ["serious", "critical"].includes(v.impact)
  );

  const resumo = graves
    .map(
      (v) =>
        `${v.impact.toUpperCase()} ${v.id}: ${v.help}\n    ` +
        v.nodes
          .slice(0, 5)
          .map((n) => n.target.join(" "))
          .join("\n    ")
    )
    .join("\n");

  expect(graves.length, `Violacoes serious/critical:\n${resumo}`).toBe(0);
}

/**
 * Espera a rolagem parar.
 *
 * O `html` do site tem `scroll-behavior: smooth`, e a previa da ficha fecha
 * em qualquer evento de scroll. Rolar ate um card e passar o mouse em
 * seguida faz a previa abrir aos 350ms e fechar logo depois, com a rolagem
 * suave ainda em curso -- algo que nao acontece no uso real, em que a
 * distancia entre um card e o vizinho e curta.
 */
async function esperaRolagemParar(page) {
  /* Exige TRES leituras iguais em sequencia. Com duas, a espera terminava
     cedo: chamado logo depois de scrollIntoViewIfNeeded, o navegador ainda
     nao tinha comecado a animacao, e as duas primeiras amostras eram
     identicas por isso -- nao por a rolagem ter acabado. */
    let anterior = null;
    let iguais = 0;
    for (let i = 0; i < 60 && iguais < 3; i++) {
      await page.waitForTimeout(100);
      const y = await page.evaluate(() => window.scrollY);
      iguais = y === anterior ? iguais + 1 : 0;
      anterior = y;
    }
    expect(iguais, "a rolagem nao parou em 6s").toBeGreaterThanOrEqual(3);
}

/** Rola ate o card, espera a rolagem terminar e passa o mouse. */
async function passaOMouseNoCard(page, seletor) {
  const card = page.locator(seletor);
  await card.scrollIntoViewIfNeeded();
  await esperaRolagemParar(page);
  await card.hover();
}

/** Espera o contador animado chegar ao valor final (dura ate 1,2s). */
async function valorDoContador(page, chave) {
  const el = page.locator(`[data-numero="${chave}"]`);
  const alvo = await el.getAttribute("data-conta");
  await expect(el).toHaveText(alvo, { timeout: 5_000 });
  return Number(alvo);
}

module.exports = {
  ESPERADO,
  lerDados,
  vigiaConsole,
  semRolagemHorizontal,
  semViolacoesAxe,
  valorDoContador,
  esperaRolagemParar,
  passaOMouseNoCard,
};
