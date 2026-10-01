/* ============================================================
   capturar.js — gera as capturas para a revisao visual das fases.

   Nao e teste: e a ferramenta que produz as imagens que o usuario aprova
   (porta de saida da Fase 4 no PRD secao 14).

   Uso, com o servidor de testes rodando (`npm run servir`):
       node painel-ui/capturar.js
       node painel-ui/capturar.js --saida ../../tmp/capturas

   As imagens saem em tests/painel-ui/capturas/, que fica fora do git.
   ============================================================ */
"use strict";

const fs = require("fs");
const path = require("path");
const { chromium } = require("@playwright/test");

const BASE = process.env.BASE || "http://127.0.0.1:4173";
const MOCK = path.join(__dirname, "mock-api.js");

const argSaida = process.argv.indexOf("--saida");
const SAIDA =
  argSaida > -1 && process.argv[argSaida + 1]
    ? path.resolve(process.argv[argSaida + 1])
    : path.join(__dirname, "capturas");

/** As telas a capturar. `cenario` liga os casos do mock-api.js. */
const TELAS = [
  {
    arquivo: "01-primeira-execucao.png",
    url: "/admin/ui/index.html#/configurar",
    cenario: "sem-configuracao",
    titulo: "T0 — primeira execução",
  },
  {
    arquivo: "02-patentes.png",
    url: "/admin/ui/index.html#/lista",
    titulo: "T1 — Patentes",
  },
  {
    arquivo: "02b-patentes-detalhes.png",
    url: "/admin/ui/index.html#/lista",
    titulo: "T1 — com os detalhes abertos",
    antes: async (page) => {
      await page.click("[data-detalhes]");
      await page.waitForTimeout(250);
    },
  },
  {
    arquivo: "03-patentes-busca.png",
    url: "/admin/ui/index.html#/lista",
    titulo: "T1 — busca por área",
    antes: async (page) => {
      await page.fill("#busca-painel", "engenharias");
      await page.waitForTimeout(300);
    },
  },
  {
    arquivo: "04-acervo-vazio.png",
    url: "/admin/ui/index.html#/lista",
    cenario: "acervo-vazio",
    titulo: "T1 — acervo vazio",
  },
  {
    arquivo: "05-configurar.png",
    url: "/admin/ui/index.html#/configurar",
    titulo: "T5 — Configurar",
  },
  {
    arquivo: "06-em-construcao.png",
    url: "/admin/ui/index.html#/nova",
    titulo: "Rota das fases seguintes",
  },
  {
    arquivo: "07-galeria-componentes.png",
    url: "/tests/painel-ui/galeria.html",
    titulo: "Componentes (7.4)",
    inteira: true,
    semMock: true,
  },
];

async function main() {
  fs.mkdirSync(SAIDA, { recursive: true });

  const navegador = await chromium.launch();
  const problemas = [];

  for (const tela of TELAS) {
    const ctx = await navegador.newContext({
      viewport: { width: 1280, height: 800 },
      deviceScaleFactor: 2, // nitidez para a revisao
      locale: "pt-BR",
    });

    if (!tela.semMock) {
      const mock = fs.readFileSync(MOCK, "utf8");
      const cenario = tela.cenario || "normal";
      await ctx.addInitScript(
        `window.__MOCK = { cenario: ${JSON.stringify(cenario)} };\n${mock}`
      );
    }

    const page = await ctx.newPage();
    page.on("pageerror", (e) => problemas.push(`${tela.arquivo}: ${e.message}`));
    page.on("console", (m) => {
      if (m.type() === "error") problemas.push(`${tela.arquivo}: ${m.text()}`);
    });

    await page.goto(BASE + tela.url, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(400);
    if (tela.antes) await tela.antes(page);

    await page.screenshot({
      path: path.join(SAIDA, tela.arquivo),
      fullPage: !!tela.inteira,
    });
    console.log(`  ${tela.arquivo}  ${tela.titulo}`);
    await ctx.close();
  }

  await navegador.close();

  console.log(`\n${TELAS.length} capturas em ${SAIDA}`);
  if (problemas.length) {
    console.log(`\n${problemas.length} problema(s) de console:`);
    problemas.forEach((p) => console.log("  " + p));
    process.exitCode = 1;
  } else {
    console.log("Nenhum erro de console em nenhuma tela.");
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
