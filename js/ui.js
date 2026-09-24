/* ============================================================
   ui.js — utilidades compartilhadas por todas as paginas.
   Script classico (sem modulos) para funcionar tambem via file://.
   Expoe window.UI.
   ============================================================ */
(function () {
  "use strict";

  /* Marca que o JS esta ativo: o CSS so esconde elementos animados
     quando ha JS para revela-los de volta. */
  document.documentElement.classList.add("js");

  var reduzido = window.matchMedia("(prefers-reduced-motion: reduce)");

  /* ---------------------------------------------------------
     Texto
     --------------------------------------------------------- */

  /** Minusculo e sem acento, para busca e comparacao. */
  function normaliza(s) {
    return String(s == null ? "" : s)
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();
  }

  /** Escapa texto para interpolar em HTML. */
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /** Espera `ms` sem chamadas antes de executar. */
  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments,
        self = this;
      clearTimeout(t);
      t = setTimeout(function () {
        fn.apply(self, args);
      }, ms);
    };
  }

  /* ---------------------------------------------------------
     Icones (SVG inline, traco 1.5, estilo Lucide)
     --------------------------------------------------------- */
  var CAMINHOS = {
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "arrow-up-right": '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    download:
      '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>',
    "file-text":
      '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><path d="M14 2v5h5"/><path d="M10 13h5"/><path d="M10 17h5"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    "maximize-2":
      '<path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/>',
    mail:
      '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "chevron-up": '<path d="m18 15-6-6-6 6"/>',
  };

  /**
   * SVG inline de um icone.
   * @param {string} nome chave de CAMINHOS
   * @param {string} [cls] classe CSS opcional
   */
  function icone(nome, cls) {
    var d = CAMINHOS[nome];
    if (!d) return "";
    return (
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" ' +
      'aria-hidden="true" focusable="false"' +
      (cls ? ' class="' + cls + '"' : "") +
      ">" +
      d +
      "</svg>"
    );
  }

  /** Troca todo <span data-icone="nome"> pelo SVG correspondente. */
  function hidrataIcones(raiz) {
    var alvos = (raiz || document).querySelectorAll("[data-icone]");
    Array.prototype.forEach.call(alvos, function (el) {
      var svg = icone(el.getAttribute("data-icone"), el.className || null);
      if (!svg) return;
      el.outerHTML = svg;
    });
  }

  /* ---------------------------------------------------------
     Header: compacta ao rolar
     --------------------------------------------------------- */
  function iniciaHeader() {
    var header = document.querySelector(".cabecalho");
    if (!header) return;
    var compacto = false;

    function aoRolar() {
      var deve = window.scrollY > 24;
      if (deve === compacto) return;
      compacto = deve;
      header.classList.toggle("is-compacto", deve);
      document.documentElement.classList.toggle("is-compacto-scroll", deve);
    }

    window.addEventListener("scroll", aoRolar, { passive: true });
    aoRolar();
  }

  /* ---------------------------------------------------------
     Revelacao na rolagem
     --------------------------------------------------------- */
  var observador = null;

  function observadorRevela() {
    if (observador) return observador;
    if (!("IntersectionObserver" in window)) return null;
    observador = new IntersectionObserver(
      function (entradas) {
        entradas.forEach(function (e) {
          if (!e.isIntersecting) return;
          e.target.classList.add("is-visivel");
          observador.unobserve(e.target);
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
    );
    return observador;
  }

  /**
   * Revela elementos ao entrarem na tela, com stagger de 40ms
   * (teto de 320ms, conforme o PRD).
   */
  function revela(elementos) {
    var lista = Array.prototype.slice.call(elementos);
    if (!lista.length) return;

    if (reduzido.matches) {
      lista.forEach(function (el) {
        el.classList.add("is-visivel");
      });
      return;
    }

    var obs = observadorRevela();
    lista.forEach(function (el, i) {
      // garante o estado inicial mesmo para quem nao trouxe o atributo no HTML
      if (!el.hasAttribute("data-revela")) el.setAttribute("data-revela", "");
      el.style.setProperty("--atraso", Math.min(i * 40, 320) + "ms");
      if (obs) obs.observe(el);
      else el.classList.add("is-visivel");
    });
  }

  /* ---------------------------------------------------------
     Contador animado
     --------------------------------------------------------- */
  function contaAte(el, valor) {
    if (reduzido.matches) {
      el.textContent = String(valor);
      return;
    }
    var inicio = null;
    var dur = 1200;
    function passo(t) {
      if (inicio === null) inicio = t;
      var p = Math.min((t - inicio) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
      el.textContent = String(Math.round(eased * valor));
      if (p < 1) requestAnimationFrame(passo);
      else el.textContent = String(valor);
    }
    requestAnimationFrame(passo);
  }

  /** Dispara o contador quando o bloco de numeros entra na tela (uma vez). */
  function iniciaContadores(raiz) {
    var alvos = (raiz || document).querySelectorAll("[data-conta]");
    if (!alvos.length) return;

    function roda() {
      Array.prototype.forEach.call(alvos, function (el) {
        contaAte(el, parseInt(el.getAttribute("data-conta"), 10) || 0);
      });
    }

    if (reduzido.matches || !("IntersectionObserver" in window)) {
      roda();
      return;
    }

    /* threshold 0: basta encostar na tela. Com um limiar alto (0.4) o bloco
       de numeros nunca dispara em telas baixas, onde ele aparece so em parte
       na primeira dobra -- e os contadores ficariam parados em zero. */
    var obs = new IntersectionObserver(
      function (entradas, o) {
        entradas.forEach(function (e) {
          if (!e.isIntersecting) return;
          roda();
          o.disconnect();
        });
      },
      { threshold: 0 }
    );
    obs.observe(alvos[0].closest("[data-numeros]") || alvos[0]);
  }

  /* ---------------------------------------------------------
     Voltar ao topo
     --------------------------------------------------------- */
  function iniciaAoTopo() {
    var btn = document.querySelector(".ao-topo");
    if (!btn) return;

    window.addEventListener(
      "scroll",
      function () {
        btn.classList.toggle("is-visivel", window.scrollY > 800);
      },
      { passive: true }
    );

    btn.addEventListener("click", function () {
      window.scrollTo({
        top: 0,
        behavior: reduzido.matches ? "auto" : "smooth",
      });
      var pular = document.querySelector(".pular-link");
      if (pular) pular.focus();
    });
  }

  /* ---------------------------------------------------------
     Mosaico de quadrados decorativo
     --------------------------------------------------------- */
  /**
   * Preenche um .mosaico com quadrados posicionados em %.
   * @param {Element} el
   * @param {Array<{x:number,y:number,t:number,o:number,c?:boolean}>} pecas
   *        x/y em %, t = tamanho em px, o = opacidade, c = so contorno
   */
  function montaMosaico(el, pecas) {
    if (!el) return;
    var html = pecas
      .map(function (p, i) {
        return (
          '<span style="left:' +
          p.x +
          "%;top:" +
          p.y +
          "%;width:" +
          p.t +
          "px;height:" +
          p.t +
          "px;opacity:" +
          p.o +
          ";animation-delay:" +
          (i * 0.7).toFixed(1) +
          's"' +
          (p.c ? " data-contorno" : "") +
          "></span>"
        );
      })
      .join("");
    el.innerHTML = html;
  }

  window.UI = {
    normaliza: normaliza,
    esc: esc,
    debounce: debounce,
    icone: icone,
    hidrataIcones: hidrataIcones,
    revela: revela,
    contaAte: contaAte,
    iniciaContadores: iniciaContadores,
    montaMosaico: montaMosaico,
    reduzido: reduzido,
    iniciar: function () {
      hidrataIcones(document);
      iniciaHeader();
      iniciaAoTopo();
    },
  };
})();
