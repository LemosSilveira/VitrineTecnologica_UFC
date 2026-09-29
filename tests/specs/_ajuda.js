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
};
