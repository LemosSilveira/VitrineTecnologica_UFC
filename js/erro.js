/* ============================================================
   erro.js — pagina 404. Monta o mosaico e ajusta os caminhos
   absolutos a partir de CONFIG.basePath.
   ============================================================ */
(function () {
  "use strict";

  var U = window.UI;
  var base = (window.CONFIG && window.CONFIG.basePath) || "/";
  if (base.charAt(base.length - 1) !== "/") base += "/";

  /* Se o site estiver numa subpasta, reescreve os caminhos que o HTML
     escreveu a partir da raiz. Com basePath "/" nada muda. */
  if (base !== "/") {
    var seletores = 'a[href^="/"], link[href^="/"], script[src^="/"], img[src^="/"]';
    Array.prototype.forEach.call(document.querySelectorAll(seletores), function (el) {
      var attr = el.hasAttribute("href") ? "href" : "src";
      var v = el.getAttribute(attr);
      if (v && v.charAt(0) === "/" && v.indexOf(base) !== 0) {
        el.setAttribute(attr, base + v.slice(1));
      }
    });
  }

  U.iniciar();

  /* Mosaico de quadrados flutuando, em tons do roxo da marca. */
  U.montaMosaico(document.querySelector("[data-mosaico-erro]"), [
    { x: 6, y: 14, t: 120, o: 0.45 },
    { x: 78, y: 8, t: 90, o: 0.3, c: true },
    { x: 88, y: 52, t: 150, o: 0.25 },
    { x: 14, y: 68, t: 70, o: 0.6 },
    { x: 46, y: 80, t: 110, o: 0.15 },
    { x: 66, y: 30, t: 48, o: 0.6, c: true },
    { x: 30, y: 30, t: 60, o: 0.2 },
    { x: 92, y: 80, t: 64, o: 0.35, c: true },
    { x: 2, y: 44, t: 40, o: 0.3 },
  ]);
})();
