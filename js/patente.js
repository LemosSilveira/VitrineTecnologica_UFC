/* ============================================================
   patente.js — pagina de detalhe (patente.html?id=N)
   Depende de: config.js, data/patentes.js, ui.js
   ============================================================ */
(function () {
  "use strict";

  var PATENTES = window.PATENTES || [];
  var CONFIG = window.CONFIG || {};
  var U = window.UI;

  /* ---------------------------------------------------------
     Resolve o ?id=
     --------------------------------------------------------- */
  var bruto = new URLSearchParams(location.search).get("id");
  var id = /^\d+$/.test(bruto || "") ? parseInt(bruto, 10) : NaN;

  var patente = null;
  for (var i = 0; i < PATENTES.length; i++) {
    if (PATENTES[i].id === id) {
      patente = PATENTES[i];
      break;
    }
  }

  if (!patente) {
    // id ausente, nao numerico ou inexistente
    location.replace("404.html");
    return;
  }

  var indice = PATENTES.indexOf(patente);
  var anterior = PATENTES[(indice - 1 + PATENTES.length) % PATENTES.length];
  var proxima = PATENTES[(indice + 1) % PATENTES.length];

  /* ---------------------------------------------------------
     Metadados da pagina
     --------------------------------------------------------- */
  document.title = patente.titulo + " — Vitrine de Patentes UFC";

  function meta(seletor, valor) {
    var el = document.querySelector(seletor);
    if (el) el.setAttribute("content", valor);
  }
  meta('meta[name="description"]', patente.resumo);
  meta('meta[property="og:title"]', patente.titulo + " — Vitrine de Patentes UFC");
  meta('meta[property="og:description"]', patente.resumo);

  document.documentElement.lang = "pt-BR";

  /* ---------------------------------------------------------
     Migalhas
     --------------------------------------------------------- */
  function slugArea(nome) {
    return U.normaliza(nome).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  var elMigalhas = document.querySelector("[data-migalhas]");
  if (elMigalhas) {
    elMigalhas.innerHTML =
      '<a href="index.html#patentes">Patentes</a>' +
      '<span class="migalhas__sep" aria-hidden="true">/</span>' +
      '<a href="index.html?area=' +
      encodeURIComponent(slugArea(patente.categoria)) +
      '#patentes">' +
      U.esc(patente.categoria) +
      "</a>" +
      '<span class="migalhas__sep" aria-hidden="true">/</span>' +
      '<span aria-current="page">' +
      U.esc(patente.numero) +
      "</span>";
  }

  /* ---------------------------------------------------------
     Medidor de TRL
     --------------------------------------------------------- */
  function htmlTrl(trl) {
    if (!trl) return "";
    var segs = "";
    for (var n = 1; n <= 9; n++) {
      var ativo = n >= trl.min && n <= trl.max;
      segs += '<span class="trl__seg' + (ativo ? " is-ativo" : "") + '"></span>';
    }
    var descricao =
      "Technology Readiness Level, de 1 (ideia) a 9 (produto no mercado).";
    return (
      '<div class="trl">' +
      '<div class="trl__barra" role="img" title="' +
      U.esc(descricao) +
      '" aria-label="Maturidade tecnológica ' +
      U.esc(trl.texto) +
      ". " +
      U.esc(descricao) +
      '">' +
      segs +
      "</div>" +
      '<p class="trl__rotulo">Maturidade tecnológica: <strong>' +
      U.esc(trl.texto) +
      "</strong></p>" +
      "</div>"
    );
  }

  /* ---------------------------------------------------------
     Corpo da patente
     --------------------------------------------------------- */
  function htmlSecao(titulo, conteudo) {
    if (!conteudo) return "";
    return (
      '<section class="ficha-secao"><h2>' +
      U.esc(titulo) +
      "</h2><p>" +
      U.esc(conteudo) +
      "</p></section>"
    );
  }

  function htmlDiferenciais(itens) {
    if (!itens || !itens.length) return "";
    return (
      '<section class="ficha-secao"><h2>Diferenciais competitivos</h2>' +
      '<ul class="diferenciais">' +
      itens
        .map(function (d) {
          return "<li>" + U.icone("check") + "<span>" + U.esc(d) + "</span></li>";
        })
        .join("") +
      "</ul></section>"
    );
  }

  var s = patente.secoes || {};
  var temTexto = !!(
    s.oQueE ||
    s.problema ||
    s.exemploDeUso ||
    (s.diferenciais && s.diferenciais.length) ||
    s.beneficio
  );

  var corpoEsquerda = temTexto
    ? htmlSecao("O que é?", s.oQueE) +
      htmlSecao("Problema que resolve", s.problema) +
      htmlSecao("Exemplo de uso", s.exemploDeUso) +
      htmlDiferenciais(s.diferenciais) +
      htmlSecao("Benefício principal", s.beneficio)
    : // sem texto extraido: mostra a ficha em imagem grande no lugar
      '<section class="ficha-secao"><h2>Ficha técnica</h2>' +
      '<img class="ficha-imagem" src="' +
      patente.imagens.ficha1620 +
      '" alt="Ficha técnica da patente ' +
      U.esc(patente.numero) +
      '" loading="lazy" decoding="async"></section>';

  /* ---- coluna do documento ---- */
  var nomePdf = "ficha-" + patente.numero.replace(/\s/g, "-") + ".pdf";

  var btnInteresse = "";
  if (CONFIG.contatoEmail) {
    var assunto = "Interesse na patente " + patente.numero + " — " + patente.titulo;
    btnInteresse =
      '<a class="botao botao--terciario botao--bloco" href="mailto:' +
      encodeURIComponent(CONFIG.contatoEmail) +
      "?subject=" +
      encodeURIComponent(assunto) +
      '">' +
      U.icone("mail") +
      "Tenho interesse</a>";
  }

  var colunaDoc =
    '<aside class="doc">' +
    '<h2 class="doc__titulo">Documento oficial</h2>' +
    '<button class="doc__thumb" type="button" data-abre-lightbox ' +
    'aria-label="Ver a ficha técnica em tela cheia">' +
    '<img src="' +
    patente.imagens.ficha600 +
    '" alt="Ficha técnica da patente ' +
    U.esc(patente.numero) +
    '" loading="lazy" decoding="async">' +
    "</button>" +
    '<div class="doc__acoes">' +
    '<button class="botao botao--primario botao--bloco" type="button" data-abre-lightbox>' +
    U.icone("maximize-2") +
    "Ver ficha em tela cheia</button>" +
    '<a class="botao botao--secundario botao--bloco" href="' +
    patente.pdf +
    '" download="' +
    U.esc(nomePdf) +
    '">' +
    U.icone("download") +
    "Baixar PDF</a>" +
    btnInteresse +
    "</div>" +
    "</aside>";

  /* ---- monta tudo ---- */
  var elPatente = document.querySelector("[data-patente]");
  elPatente.innerHTML =
    '<header class="patente-topo">' +
    '<div class="patente-topo__info">' +
    '<p class="eyebrow">' +
    U.esc(patente.categoria) +
    "</p>" +
    "<h1>" +
    U.esc(patente.titulo) +
    "</h1>" +
    '<div class="patente-topo__meta">' +
    '<span class="badge badge--forte">' +
    U.esc(patente.tipo.nome) +
    "</span>" +
    '<span class="numero-tecnico">' +
    U.esc(patente.numero) +
    "</span>" +
    '<span class="numero-tecnico">Depósito em ' +
    patente.ano +
    "</span>" +
    "</div>" +
    htmlTrl(patente.trl) +
    "</div>" +
    '<img class="patente-topo__capa" src="' +
    patente.imagens.capa800 +
    '" width="' +
    patente.imagens.dimensoesCapa[0] +
    '" height="' +
    patente.imagens.dimensoesCapa[1] +
    '" alt="Imagem ilustrativa da tecnologia ' +
    U.esc(patente.titulo) +
    '" fetchpriority="high" decoding="async" ' +
    'style="view-transition-name: capa-' +
    patente.id +
    '">' +
    "</header>" +
    '<div class="patente-corpo">' +
    "<div>" +
    corpoEsquerda +
    "</div>" +
    '<div class="patente-corpo__doc">' +
    colunaDoc +
    "</div>" +
    "</div>";

  /* ---------------------------------------------------------
     Anterior / proxima (circular)
     --------------------------------------------------------- */
  function htmlNav(p, tipo) {
    var prox = tipo === "prox";
    return (
      '<a class="nav-patentes__item' +
      (prox ? " nav-patentes__item--prox" : "") +
      '" href="patente.html?id=' +
      p.id +
      '" rel="' +
      (prox ? "next" : "prev") +
      '">' +
      '<img class="nav-patentes__thumb" src="' +
      p.imagens.capa400 +
      '" alt="" loading="lazy" decoding="async">' +
      '<span class="nav-patentes__texto">' +
      '<span class="nav-patentes__rotulo">' +
      (prox
        ? "Próxima" + U.icone("arrow-right")
        : U.icone("arrow-left") + "Anterior") +
      "</span>" +
      '<span class="nav-patentes__titulo">' +
      U.esc(p.titulo) +
      "</span>" +
      "</span>" +
      "</a>"
    );
  }

  var elNav = document.querySelector("[data-nav]");
  if (elNav) {
    elNav.innerHTML = htmlNav(anterior, "ant") + htmlNav(proxima, "prox");
  }

  /* ---------------------------------------------------------
     Outras patentes da mesma area
     --------------------------------------------------------- */
  var relacionadas = PATENTES.filter(function (p) {
    return p.categoria === patente.categoria && p.id !== patente.id;
  }).slice(0, 4);

  if (relacionadas.length) {
    var sec = document.querySelector("[data-relacionadas]");
    sec.hidden = false;
    document.querySelector("[data-relacionadas-titulo]").textContent =
      "Outras patentes em " + patente.categoria;
    document.querySelector("[data-relacionadas-grade]").innerHTML = relacionadas
      .map(function (p) {
        return (
          '<article class="card" data-id="' +
          p.id +
          '">' +
          '<a class="card__link" href="patente.html?id=' +
          p.id +
          '">' +
          '<div class="card__media is-carregada">' +
          '<img src="' +
          p.imagens.capa400 +
          '" srcset="' +
          p.imagens.capa400 +
          " 400w, " +
          p.imagens.capa800 +
          ' 800w" sizes="(max-width: 639px) calc(100vw - 32px), ' +
          "(max-width: 1023px) calc(50vw - 32px), 296px\" width=\"" +
          p.imagens.dimensoesCapa[0] +
          '" height="' +
          p.imagens.dimensoesCapa[1] +
          '" alt="Imagem ilustrativa da tecnologia ' +
          U.esc(p.titulo) +
          '" loading="lazy" decoding="async">' +
          "</div>" +
          '<div class="card__body">' +
          '<p class="card__eyebrow">' +
          U.esc(p.categoria) +
          "</p>" +
          '<h3 class="card__titulo">' +
          U.esc(p.titulo) +
          "</h3>" +
          '<div class="card__meta">' +
          '<span class="badge">' +
          p.tipo.sigla +
          "</span>" +
          '<span class="card__numero">' +
          U.esc(p.numero) +
          "</span>" +
          U.icone("arrow-up-right", "card__arrow") +
          "</div></div></a></article>"
        );
      })
      .join("");
  }

  /* ---------------------------------------------------------
     Lightbox
     --------------------------------------------------------- */
  var dlg = document.querySelector("[data-lightbox]");
  var dlgImg = dlg ? dlg.querySelector(".lightbox__img") : null;
  var gatilho = null;

  function abreLightbox(botao) {
    if (!dlg) return;
    gatilho = botao || null;
    if (dlgImg.getAttribute("src") !== patente.imagens.ficha1620) {
      dlgImg.src = patente.imagens.ficha1620;
      dlgImg.alt = "Ficha técnica da patente " + patente.numero;
    }
    dlg.classList.remove("is-zoom");
    var rotulo = dlg.querySelector("[data-zoom-rotulo]");
    if (rotulo) rotulo.textContent = "Ampliar";
    // <dialog> nativo: showModal ja da focus trap e inert no resto da pagina
    dlg.showModal();
    document.body.style.overflow = "hidden";
  }

  function fechaLightbox() {
    if (dlg && dlg.open) dlg.close();
  }

  if (dlg) {
    document.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-abre-lightbox]");
      if (btn) {
        e.preventDefault();
        abreLightbox(btn);
      }
    });

    dlg.querySelector("[data-fechar]").addEventListener("click", fechaLightbox);

    dlg.querySelector("[data-zoom]").addEventListener("click", function () {
      var zoom = dlg.classList.toggle("is-zoom");
      var rotulo = dlg.querySelector("[data-zoom-rotulo]");
      if (rotulo) rotulo.textContent = zoom ? "Ajustar à tela" : "Ampliar";
      if (zoom) {
        // centraliza o topo da imagem ampliada
        var vp = dlg.querySelector(".lightbox__viewport");
        vp.scrollLeft = (vp.scrollWidth - vp.clientWidth) / 2;
        vp.scrollTop = 0;
      }
    });

    // clique fora da imagem fecha
    dlg.addEventListener("click", function (e) {
      if (e.target === dlg || e.target.classList.contains("lightbox__viewport")) {
        fechaLightbox();
      }
    });

    // Esc: o <dialog> ja fecha sozinho; aqui so devolvemos o foco e o scroll
    dlg.addEventListener("close", function () {
      document.body.style.overflow = "";
      if (gatilho && document.contains(gatilho)) gatilho.focus();
      gatilho = null;
    });
  }

  /* ---------------------------------------------------------
     Mosaico do rodape
     --------------------------------------------------------- */
  var rod = document.querySelector("[data-mosaico-rodape]");
  if (rod) {
    rod.innerHTML = [
      { x: 4, y: 12, t: 70 },
      { x: 22, y: 58, t: 40 },
      { x: 48, y: 8, t: 96 },
      { x: 72, y: 44, t: 56 },
      { x: 88, y: 14, t: 120 },
      { x: 62, y: 74, t: 34 },
    ]
      .map(function (p) {
        return (
          '<span style="left:' + p.x + "%;top:" + p.y + "%;width:" + p.t +
          "px;height:" + p.t + 'px"></span>'
        );
      })
      .join("");
  }

  /* ---------------------------------------------------------
     Inicio
     --------------------------------------------------------- */
  U.iniciar();
  U.revela(document.querySelectorAll(".ficha-secao, .nav-patentes__item, .relacionadas .card"));
})();
