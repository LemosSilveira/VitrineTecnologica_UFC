/* ============================================================
   render.js — montagem do HTML compartilhada pelo site e pelo
   painel local de administracao.

   Mora aqui o que precisa sair IGUAL nos dois lugares: o card da grade,
   o medidor de TRL e as secoes da ficha. A previa do painel usa estas
   mesmas funcoes, entao o que a equipe ve antes de salvar e exatamente
   o que vai ao ar.

   Depende so de window.UI (esc e icone). Expoe window.RENDER.
   ============================================================ */
(function () {
  "use strict";

  var U = window.UI;

  /* Larguras da grade, para o navegador escolher a capa certa do srcset.
     Bate com o grid de pages.css: 1 coluna ate 639px, 2 ate 1023,
     3 ate 1279 e 4 acima (296px de coluna). */
  var SIZES =
    "(max-width: 639px) calc(100vw - 32px), (max-width: 1023px) calc(50vw - 32px), " +
    "(max-width: 1279px) calc(33.33vw - 32px), 296px";

  /* ---------------------------------------------------------
     View transitions

     O nome da transicao vai num data-attribute e e aplicado por JS, nao
     num style="" no HTML. E o que permite a CSP do site dispensar
     style-src 'unsafe-inline': estilo vindo do CSSOM e liberado, atributo
     style no markup nao.
     --------------------------------------------------------- */
  function aplicaTransicoes(raiz) {
    var alvos = (raiz || document).querySelectorAll("[data-vt]");
    Array.prototype.forEach.call(alvos, function (el) {
      el.style.setProperty("view-transition-name", el.getAttribute("data-vt"));
    });
  }

  /* ---------------------------------------------------------
     Card da grade
     --------------------------------------------------------- */
  /**
   * @param {object} p patente (item de window.PATENTES)
   * @param {number} [indice] posicao na grade; as 4 primeiras carregam
   *        sem lazy e com prioridade, porque estao na primeira dobra
   */
  function card(p, indice) {
    var alt = "Imagem ilustrativa da tecnologia " + p.titulo;
    var prioridade = indice < 4;
    return (
      '<article class="card" data-id="' +
      p.id +
      '">' +
      '<a class="card__link" href="patente.html?id=' +
      p.id +
      '" aria-describedby="card-' +
      p.id +
      '-meta">' +
      '<div class="card__media">' +
      '<img src="' +
      p.imagens.capa400 +
      '" srcset="' +
      p.imagens.capa400 +
      " 400w, " +
      p.imagens.capa800 +
      ' 800w" sizes="' +
      SIZES +
      '" width="' +
      p.imagens.dimensoesCapa[0] +
      '" height="' +
      p.imagens.dimensoesCapa[1] +
      '" alt="' +
      U.esc(alt) +
      '" decoding="async" ' +
      (prioridade ? 'fetchpriority="high"' : 'loading="lazy"') +
      ' data-vt="capa-' +
      p.id +
      '">' +
      "</div>" +
      '<div class="card__body">' +
      '<p class="card__eyebrow">' +
      U.esc(p.categoria) +
      "</p>" +
      '<h3 class="card__titulo">' +
      U.esc(p.titulo) +
      "</h3>" +
      '<p class="card__resumo">' +
      U.esc(p.resumo) +
      "</p>" +
      '<div class="card__meta" id="card-' +
      p.id +
      '-meta">' +
      '<span class="badge">' +
      p.tipo.sigla +
      "</span>" +
      '<span class="card__numero">' +
      U.esc(p.numero) +
      "</span>" +
      U.icone("arrow-up-right", "card__arrow") +
      "</div>" +
      "</div>" +
      "</a>" +
      "</article>"
    );
  }

  /* ---------------------------------------------------------
     Medidor de TRL
     --------------------------------------------------------- */
  function trl(t) {
    if (!t) return "";
    var segs = "";
    for (var n = 1; n <= 9; n++) {
      var ativo = n >= t.min && n <= t.max;
      segs += '<span class="trl__seg' + (ativo ? " is-ativo" : "") + '"></span>';
    }
    var descricao =
      "Technology Readiness Level, de 1 (ideia) a 9 (produto no mercado).";
    return (
      '<div class="trl">' +
      '<div class="trl__barra" role="img" title="' +
      U.esc(descricao) +
      '" aria-label="Maturidade tecnológica ' +
      U.esc(t.texto) +
      ". " +
      U.esc(descricao) +
      '">' +
      segs +
      "</div>" +
      '<p class="trl__rotulo">Maturidade tecnológica: <strong>' +
      U.esc(t.texto) +
      "</strong></p>" +
      "</div>"
    );
  }

  /* ---------------------------------------------------------
     Secoes da ficha
     --------------------------------------------------------- */
  function secao(titulo, conteudo) {
    if (!conteudo) return "";
    return (
      '<section class="ficha-secao"><h2>' +
      U.esc(titulo) +
      "</h2><p>" +
      U.esc(conteudo) +
      "</p></section>"
    );
  }

  function diferenciais(itens) {
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

  window.RENDER = {
    SIZES: SIZES,
    card: card,
    trl: trl,
    secao: secao,
    diferenciais: diferenciais,
    aplicaTransicoes: aplicaTransicoes,
  };
})();
