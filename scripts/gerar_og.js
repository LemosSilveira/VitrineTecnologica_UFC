/* Gera assets/img/og-image.png (1200x630) a partir de scripts/og_template.html.
 *
 * Uso (com o servidor local em pe na porta 4173):
 *     npm --prefix tests run serve   # em outro terminal
 *     node scripts/gerar_og.js
 */
const path = require("path");
const { chromium } = require(path.join(__dirname, "..", "tests", "node_modules", "playwright"));

const BASE = process.env.BASE_URL || "http://127.0.0.1:4173";
const destino = path.join(__dirname, "..", "assets", "img", "og-image.png");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1200, height: 630 },
    deviceScaleFactor: 1,
  });
  await page.goto(BASE + "/scripts/og_template.html", { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  await page.screenshot({ path: destino });
  await browser.close();
  console.log("og-image gerada em " + destino);
})();
