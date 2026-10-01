/* ============================================================
   home.js — busca, filtros, ordenacao, grade e previa no hover.
   Depende de: config.js, data/patentes.js, ui.js, render.js
   ============================================================ */
(function () {
  "use strict";

  var PATENTES = window.PATENTES || [];
  var CATEGORIAS = window.CATEGORIAS || [];
  var U = window.UI;
  var R = window.RENDER;

  var grade = document.querySelector("[data-grade]");
  if (!grade) return;

  var campoBusca = document.getElementById("busca");
  var selOrdem = document.getElementById("ordem");
  var elAreas = document.querySelector("[data-areas]");
  var elTipos = document.querySelector("[data-tipos]");
  var elStatus = document.querySelector("[data-status]");

  /* Indice de busca: uma string normalizada por patente, montada uma vez. */
  var INDICE = PATENTES.map(function (p) {
    var s = p.secoes || {};
    return U.normaliza(
      [
        p.titulo,
        p.numero,
        p.numero.replace(/[\s-]/g, ""),
        p.categoria,
        p.tipo.sigla,
        p.tipo.nome,
        p.ano,
        p.resumo,
        s.oQueE,
        s.problema,
        s.exemploDeUso,
        s.beneficio,
        (s.diferenciais || []).join(" "),
      ].join(" ")
    );
  });

  var estado = { q: "", area: "", tipo: "", ordem: "vitrine" };

  /* ---------------------------------------------------------
     Estado na URL
     --------------------------------------------------------- */
  function slugArea(nome) {
    return U.normaliza(nome).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  function leUrl() {
    var p = new URLSearchParams(location.search);
    estado.q = p.get("q") || "";
    estado.tipo = (p.get("tipo") || "").toUpperCase();
    if (estado.tipo !== "PI" && estado.tipo !== "MU") estado.tipo = "";
    estado.ordem = p.get("ordem") || "vitrine";
    if (["vitrine", "recentes", "titulo"].indexOf(estado.ordem) < 0) {
      estado.ordem = "vitrine";
    }
    var area = p.get("area") || "";
    estado.area = "";
    if (area) {
      for (var i = 0; i < CATEGORIAS.length; i++) {
        if (slugArea(CATEGORIAS[i].nome) === area.toLowerCase()) {
          estado.area = CATEGORIAS[i].nome;
          break;
        }
      }
    }
  }

  function escreveUrl() {
    var p = new URLSearchParams();
    if (estado.q) p.set("q", estado.q);
    if (estado.area) p.set("area", slugArea(estado.area));
    if (estado.tipo) p.set("tipo", estado.tipo);
    if (estado.ordem !== "vitrine") p.set("ordem", estado.ordem);
    var qs = p.toString();
    history.replaceState(
      history.state,
      "",
      location.pathname + (qs ? "?" + qs : "") + location.hash
    );
  }

  /* ---------------------------------------------------------
     Filtro e ordenacao
     --------------------------------------------------------- */
  function filtra() {
    var termo = U.normaliza(estado.q).trim();
    var termos = termo ? termo.split(/\s+/) : [];

    var out = PATENTES.filter(function (p, i) {
      if (estado.area && p.categoria !== estado.area) return false;
      if (estado.tipo && p.tipo.sigla !== estado.tipo) return false;
      if (!termos.length) return true;
      var alvo = INDICE[i];
      // todos os termos precisam aparecer (AND)
      for (var t = 0; t < termos.length; t++) {
        if (alvo.indexOf(termos[t]) < 0) return false;
      }
      return true;
    });

    if (estado.ordem === "recentes") {
      out.sort(function (a, b) {
        return b.ano - a.ano || a.id - b.id;
      });
    } else if (estado.ordem === "titulo") {
      out.sort(function (a, b) {
        return a.titulo.localeCompare(b.titulo, "pt-BR", { sensitivity: "base" });
      });
    } else {
      out.sort(function (a, b) {
        return a.id - b.id;
      });
    }
    return out;
  }

  /* ---------------------------------------------------------
     Render
     --------------------------------------------------------- */

  function htmlVazio() {
    return (
      '<div class="vazio">' +
      U.icone("search") +
      "<p>Nenhuma patente encontrada" +
      (estado.q ? " para <strong>“" + U.esc(estado.q) + "”</strong>" : "") +
      ".</p>" +
      '<button class="botao botao--secundario" type="button" data-limpar>' +
      "Limpar filtros</button>" +
      "</div>"
    );
  }

  var primeiroRender = true;

  function render() {
    var lista = filtra();

    grade.innerHTML = lista.length
      ? lista.map(R.card).join("")
      : htmlVazio();
    R.aplicaTransicoes(grade);

    // marca a capa como carregada para parar o shimmer
    Array.prototype.forEach.call(grade.querySelectorAll(".card__media"), function (m) {
      var img = m.querySelector("img");
      if (!img) return;
      if (img.complete) m.classList.add("is-carregada");
      else
        img.addEventListener(
          "load",
          function () {
            m.classList.add("is-carregada");
          },
          { once: true }
        );
      img.addEventListener(
        "error",
        function () {
          m.classList.add("is-carregada");
        },
        { once: true }
      );
    });

    // revelacao: so na primeira pintura; nas trocas de filtro o fade e imediato
    var cards = grade.querySelectorAll(".card");
    if (primeiroRender) {
      Array.prototype.forEach.call(cards, function (c) {
        c.setAttribute("data-revela", "");
      });
      U.revela(cards);
      primeiroRender = false;
    }

    atualizaStatus(lista.length);
    montaPrevia();
  }

  function atualizaStatus(n) {
    if (!elStatus) return;
    var total = PATENTES.length;
    var partes = ["Mostrando <strong>" + n + "</strong> de " + total + " patentes"];
    if (estado.area) partes.push("em <strong>" + U.esc(estado.area) + "</strong>");
    if (estado.tipo) {
      partes.push(
        estado.tipo === "PI"
          ? "do tipo <strong>Patente de Invenção</strong>"
          : "do tipo <strong>Modelo de Utilidade</strong>"
      );
    }
    if (estado.q) partes.push("para <strong>“" + U.esc(estado.q) + "”</strong>");

    var temFiltro = !!(estado.q || estado.area || estado.tipo);
    elStatus.innerHTML =
      partes.join(" ") +
      "." +
      (temFiltro
        ? ' <button class="botao botao--terciario" type="button" data-limpar>Limpar filtros</button>'
        : "");
  }

  /* ---------------------------------------------------------
     Controles
     --------------------------------------------------------- */
  function montaAreas() {
    if (!elAreas) return;
    var html = [
      '<button class="chip" type="button" data-area="" aria-pressed="' +
        (estado.area === "") +
        '">Todas <span class="chip__total">' +
        PATENTES.length +
        "</span></button>",
    ];
    CATEGORIAS.forEach(function (c) {
      html.push(
        '<button class="chip" type="button" data-area="' +
          U.esc(c.nome) +
          '" aria-pressed="' +
          (estado.area === c.nome) +
          '">' +
          U.esc(c.nome) +
          ' <span class="chip__total">' +
          c.total +
          "</span></button>"
      );
    });
    elAreas.innerHTML = html.join("");
  }

  function montaTipos() {
    if (!elTipos) return;
    // O rotulo curto evita que o controle estoure a largura no celular;
    // o aria-label mantem o nome por extenso para leitores de tela.
    var opcoes = [
      { v: "", r: "Todos", curto: "Todos" },
      { v: "PI", r: "Invenção (PI)", curto: "PI" },
      { v: "MU", r: "Modelo de Utilidade (MU)", curto: "MU" },
    ];
    elTipos.innerHTML = opcoes
      .map(function (o) {
        return (
          '<button class="segmentado__opcao" type="button" role="radio" ' +
          'data-tipo="' +
          o.v +
          '" aria-label="' +
          U.esc(o.r) +
          '" aria-checked="' +
          (estado.tipo === o.v) +
          '" tabindex="' +
          (estado.tipo === o.v ? "0" : "-1") +
          '">' +
          '<span class="segmentado__longo">' +
          U.esc(o.r) +
          "</span>" +
          '<span class="segmentado__curto" aria-hidden="true">' +
          U.esc(o.curto) +
          "</span>" +
          "</button>"
        );
      })
      .join("");
  }

  function sincronizaControles() {
    if (campoBusca && campoBusca.value !== estado.q) campoBusca.value = estado.q;
    if (selOrdem) selOrdem.value = estado.ordem;
    Array.prototype.forEach.call(elAreas.querySelectorAll("[data-area]"), function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-area") === estado.area));
    });
    Array.prototype.forEach.call(elTipos.querySelectorAll("[data-tipo]"), function (b) {
      var sel = b.getAttribute("data-tipo") === estado.tipo;
      b.setAttribute("aria-checked", String(sel));
      b.setAttribute("tabindex", sel ? "0" : "-1");
    });
  }

  function aplica() {
    sincronizaControles();
    escreveUrl();
    render();
  }

  function limpar() {
    estado.q = "";
    estado.area = "";
    estado.tipo = "";
    aplica();
    if (campoBusca) campoBusca.focus();
  }

  /* ---------------------------------------------------------
     Eventos
     --------------------------------------------------------- */
  if (campoBusca) {
    campoBusca.addEventListener(
      "input",
      U.debounce(function () {
        estado.q = campoBusca.value;
        escreveUrl();
        render();
      }, 150)
    );
    campoBusca.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        campoBusca.value = "";
        estado.q = "";
        aplica();
      }
    });
  }

  if (selOrdem) {
    selOrdem.addEventListener("change", function () {
      estado.ordem = selOrdem.value;
      escreveUrl();
      render();
    });
  }

  if (elAreas) {
    elAreas.addEventListener("click", function (e) {
      var b = e.target.closest("[data-area]");
      if (!b) return;
      estado.area = b.getAttribute("data-area");
      aplica();
    });
  }

  if (elTipos) {
    elTipos.addEventListener("click", function (e) {
      var b = e.target.closest("[data-tipo]");
      if (!b) return;
      estado.tipo = b.getAttribute("data-tipo");
      aplica();
    });
    // navegacao por setas dentro do radiogroup
    elTipos.addEventListener("keydown", function (e) {
      var teclas = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"];
      if (teclas.indexOf(e.key) < 0) return;
      e.preventDefault();
      var btns = Array.prototype.slice.call(elTipos.querySelectorAll("[data-tipo]"));
      var i = btns.indexOf(document.activeElement);
      if (i < 0) i = 0;
      var d = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1;
      var alvo = btns[(i + d + btns.length) % btns.length];
      estado.tipo = alvo.getAttribute("data-tipo");
      aplica();
      alvo.focus();
    });
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-limpar]")) limpar();
  });

  // "/" foca a busca (fora de campos de texto)
  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
    var a = document.activeElement;
    var tag = a ? a.tagName : "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (a && a.isContentEditable)) {
      return;
    }
    e.preventDefault();
    if (campoBusca) {
      campoBusca.focus();
      campoBusca.select();
    }
  });

  var btnBuscaMob = document.querySelector("[data-foca-busca]");
  if (btnBuscaMob) {
    btnBuscaMob.addEventListener("click", function () {
      var alvo = document.getElementById("patentes");
      if (alvo) {
        alvo.scrollIntoView({
          behavior: U.reduzido.matches ? "auto" : "smooth",
          block: "start",
        });
      }
      setTimeout(
        function () {
          if (campoBusca) campoBusca.focus();
        },
        U.reduzido.matches ? 0 : 320
      );
    });
  }

  /* ---------------------------------------------------------
     Previa flutuante da ficha (PRD 7.4)
     --------------------------------------------------------- */
  var ATRASO_ABRE = 350;
  var ATRASO_FECHA = 120;
  var previa = null;
  var previaImg = null;
  var previaTrl = null;
  var previaResumo = null;
  var previaCta = null;
  var timerAbre = null;
  var timerFecha = null;
  var alvoAtual = null;

  function podeMostrarPrevia() {
    return (
      window.matchMedia("(hover: hover) and (pointer: fine)").matches &&
      window.innerWidth >= 1024
    );
  }

  function criaPrevia() {
    if (previa) return;
    previa = document.createElement("div");
    previa.className = "previa";
    previa.id = "previa-ficha";
    previa.setAttribute("role", "tooltip");
    previa.innerHTML =
      '<img class="previa__img" alt="" decoding="async">' +
      '<p class="previa__resumo" data-previa-resumo hidden></p>' +
      '<div class="previa__rodape">' +
      '<span class="trl-chip" data-previa-trl></span>' +
      '<span class="previa__cta" data-previa-cta>Clique para ver a ficha completa →</span>' +
      "</div>";
    document.body.appendChild(previa);
    previaImg = previa.querySelector(".previa__img");
    previaTrl = previa.querySelector("[data-previa-trl]");
    previaResumo = previa.querySelector("[data-previa-resumo]");
    previaCta = previa.querySelector("[data-previa-cta]");

    // manter aberta enquanto o ponteiro estiver sobre a propria previa
    previa.addEventListener("mouseenter", function () {
      clearTimeout(timerFecha);
    });
    previa.addEventListener("mouseleave", agendaFecha);
  }

  function posiciona(card) {
    var r = card.getBoundingClientRect();
    var margem = 16;
    var larg = previa.offsetWidth || 340;
    var alt = previa.offsetHeight || 460;

    // preferencia: a direita do card; se nao couber, a esquerda
    var x = r.right + margem;
    var lado = 1;
    if (x + larg > window.innerWidth - margem) {
      x = r.left - larg - margem;
      lado = -1;
    }
    // se tambem nao couber a esquerda, encaixa na viewport
    if (x < margem) {
      x = Math.max(margem, window.innerWidth - larg - margem);
    }

    // centraliza verticalmente no card, sem sair da tela
    var y = r.top + r.height / 2 - alt / 2;
    y = Math.max(margem, Math.min(y, window.innerHeight - alt - margem));

    previa.style.transform = "";
    previa.style.setProperty("--previa-dx", lado * 8 + "px");
    previa.style.left = Math.round(x) + "px";
    previa.style.top = Math.round(y) + "px";
  }

  function abrePrevia(card) {
    var id = parseInt(card.getAttribute("data-id"), 10);
    var p = PATENTES.find(function (x) {
      return x.id === id;
    });
    if (!p) return;

    criaPrevia();

    /* Patente sem PDF nao tem imagem da ficha: cai para a capa e mostra o
       resumo, que e a informacao que a ficha traria (PRD 6.4). */
    var semFicha = !p.imagens.ficha600;
    previa.classList.toggle("previa--sem-ficha", semFicha);
    previaResumo.hidden = !semFicha;
    if (semFicha) previaResumo.textContent = p.resumo;
    previaCta.textContent = semFicha
      ? "Clique para ver os detalhes →"
      : "Clique para ver a ficha completa →";

    // carrega a imagem so na primeira vez que a previa daquela patente abre
    if (previaImg.getAttribute("data-id") !== String(id)) {
      previaImg.setAttribute("data-id", String(id));
      previaImg.src = semFicha ? p.imagens.capa800 : p.imagens.ficha600;
      previaImg.alt = semFicha
        ? "Imagem ilustrativa da tecnologia " + p.titulo
        : "Prévia da ficha técnica: " + p.titulo;
    }
    previaTrl.textContent = p.trl ? p.trl.texto.replace(" (estimado)", " · estimado") : "—";
    previaTrl.hidden = !p.trl;

    previa.classList.add("is-visivel");
    posiciona(card);

    var link = card.querySelector(".card__link");
    if (link) link.setAttribute("aria-describedby", "previa-ficha");
    alvoAtual = card;
  }

  function fechaPrevia() {
    clearTimeout(timerAbre);
    clearTimeout(timerFecha);
    if (!previa) return;
    previa.classList.remove("is-visivel");
    if (alvoAtual) {
      var link = alvoAtual.querySelector(".card__link");
      if (link) link.setAttribute("aria-describedby", "card-" + alvoAtual.getAttribute("data-id") + "-meta");
    }
    alvoAtual = null;
  }

  function agendaAbre(card) {
    if (!podeMostrarPrevia()) return;
    clearTimeout(timerFecha);
    clearTimeout(timerAbre);
    timerAbre = setTimeout(function () {
      abrePrevia(card);
    }, ATRASO_ABRE);
  }

  function agendaFecha() {
    clearTimeout(timerAbre);
    clearTimeout(timerFecha);
    timerFecha = setTimeout(fechaPrevia, ATRASO_FECHA);
  }

  function montaPrevia() {
    if (!podeMostrarPrevia()) return;
    Array.prototype.forEach.call(grade.querySelectorAll(".card"), function (card) {
      card.addEventListener("mouseenter", function () {
        agendaAbre(card);
      });
      card.addEventListener("mouseleave", agendaFecha);
      var link = card.querySelector(".card__link");
      if (!link) return;
      link.addEventListener("focus", function () {
        agendaAbre(card);
      });
      link.addEventListener("blur", agendaFecha);
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && alvoAtual) fechaPrevia();
  });

  /* Rolar fecha a previa ABERTA, mas nao cancela uma abertura pendente:
     ao rolar com o ponteiro sobre a grade, o mouseenter dispara junto com os
     eventos de scroll e o timer de 350ms seria zerado a cada quadro -- a
     previa nunca chegaria a abrir. */
  function fechaSeAberta() {
    if (alvoAtual) fechaPrevia();
  }
  window.addEventListener("scroll", fechaSeAberta, { passive: true });
  window.addEventListener("resize", fechaSeAberta, { passive: true });

  /* ---------------------------------------------------------
     Restauracao de rolagem ao voltar do detalhe
     --------------------------------------------------------- */
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";

  function guardaPosicao() {
    try {
      sessionStorage.setItem(
        "vitrine:scroll",
        JSON.stringify({ y: window.scrollY, url: location.search })
      );
    } catch (err) {
      /* sessionStorage indisponivel: seguir sem restaurar */
    }
  }

  window.addEventListener("pagehide", guardaPosicao);
  grade.addEventListener("click", function (e) {
    if (e.target.closest(".card__link")) guardaPosicao();
  });

  function restauraPosicao() {
    try {
      var raw = sessionStorage.getItem("vitrine:scroll");
      if (!raw) return;
      var dados = JSON.parse(raw);
      sessionStorage.removeItem("vitrine:scroll");
      if (dados.url !== location.search) return;
      window.scrollTo(0, dados.y);
    } catch (err) {
      /* ignora */
    }
  }

  /* ---------------------------------------------------------
     Numeros do hero
     --------------------------------------------------------- */
  function montaNumeros() {
    var mapa = {
      total: PATENTES.length,
      areas: CATEGORIAS.length,
      pi: PATENTES.filter(function (p) {
        return p.tipo.sigla === "PI";
      }).length,
      mu: PATENTES.filter(function (p) {
        return p.tipo.sigla === "MU";
      }).length,
    };
    Object.keys(mapa).forEach(function (k) {
      var el = document.querySelector('[data-numero="' + k + '"]');
      if (!el) return;
      el.setAttribute("data-conta", mapa[k]);
      el.textContent = U.reduzido.matches ? String(mapa[k]) : "0";
    });
  }

  /* ---------------------------------------------------------
     Mosaicos decorativos
     --------------------------------------------------------- */
  function montaMosaicos() {
    U.montaMosaico(
      document.querySelector("[data-mosaico-hero]"),
      [
        { x: 8, y: 6, t: 92, o: 1 },
        { x: 52, y: 2, t: 56, o: 0.4 },
        { x: 70, y: 30, t: 120, o: 0.15 },
        { x: 14, y: 42, t: 64, o: 0.4, c: true },
        { x: 44, y: 46, t: 150, o: 1 },
        { x: 6, y: 72, t: 44, o: 0.15 },
        { x: 60, y: 76, t: 78, o: 0.4, c: true },
        { x: 30, y: 24, t: 36, o: 1 },
      ],
      true
    );
    U.montaMosaicoRodape();
  }

  /* ---------------------------------------------------------
     Inicio
     --------------------------------------------------------- */
  U.iniciar();
  leUrl();
  montaAreas();
  montaTipos();
  montaNumeros();
  montaMosaicos();
  aplica();
  U.revela(document.querySelectorAll("[data-revela]"));
  U.iniciaContadores(document);
  restauraPosicao();
})();
