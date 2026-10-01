/* ============================================================
   Configuracao do Playwright.

   Escopo (Fase 0 do PRD do painel): rede de seguranca da refatoracao do
   build e da extracao do js/render.js. Roda so em Chromium — Firefox e
   WebKit podem voltar depois, os specs nao dependem do motor.
   ============================================================ */
"use strict";

const { defineConfig, devices } = require("@playwright/test");

const PORTA = 4173;
const BASE = `http://127.0.0.1:${PORTA}`;

module.exports = defineConfig({
  testDir: "./specs",
  /* fixtures/ guarda .py e o snapshot da Fase 0, nada de spec. */
  testMatch: /.*\.spec\.js/,

  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"], ["html", { open: "never" }]],

  /* O build gera 60 paginas de detalhe; o spec que percorre todas precisa
     de folga em relacao ao padrao de 30s. */
  timeout: 90_000,
  expect: {
    timeout: 7_000,
    toHaveScreenshot: {
      /* PRD 6.5: tolerancia de 0,1% na comparacao antes/depois. */
      maxDiffPixelRatio: 0.001,
      animations: "disabled",
      caret: "hide",
      scale: "css",
    },
  },

  use: {
    baseURL: BASE,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    locale: "pt-BR",
    timezoneId: "America/Fortaleza",
  },

  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "chromium-mobile",
      /* Pixel 5 = 393x851; o PRD fala em 390x844, entao fixamos o viewport. */
      use: { ...devices["Pixel 5"], viewport: { width: 390, height: 844 } },
    },
  ],

  webServer: {
    command: "node server.js",
    url: BASE,
    cwd: __dirname,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
