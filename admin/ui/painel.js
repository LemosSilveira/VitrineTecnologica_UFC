/* ============================================================
   painel.js — roteamento, barra lateral, avisos e o esqueleto das telas.

   Roteamento por hash (`#/lista`, `#/editar/61`) e nao por caminho: a janela
   carrega um unico arquivo do servidor estatico interno, e mudar o caminho
   faria o pywebview tentar buscar uma pagina que nao existe.

   Nada de innerHTML com texto vindo de fora: tudo passa por UI.esc ou
   textContent. A CSP da janela nao permite inline, entao um script injetado
   nao rodaria -- mas a marcacao quebrada ainda apagaria a tela.

   Depende de: site/js/ui.js (UI), site/js/render.js (RENDER), api-cliente.js
   ============================================================ */
(function () {
  "use strict";

  var U = window.UI;
  var API = window.API;

  var elTela = document.querySelector("[data-tela]");
  var elMenu = document.querySelector("[data-menu]");
  var elToasts = document.querySelector("[data-toasts]");
  var elPendentes = document.querySelector("[data-pendentes]");

  /* Estado em memoria. Nada e gravado no navegador: a fonte da verdade e o
     acervo, e o painel sempre pergunta ao Python. */
  var estado = {
    info: null, // resposta de API.estado()
    patentes: null, // cache da ultima listagem
    sujo: false, // ha rascunho nao salvo na tela atual?
  };

  /* ---------------------------------------------------------
     Icones so do painel

     O conjunto de `UI.icone` cobre o que o SITE usa. O painel precisa de
     alguns a mais (lista, engrenagem, relogio, olho riscado). Eles ficam
     aqui, e nao em js/ui.js: o site nao deve carregar icone que nao usa, e
     usar "check" para Historico ou setas diagonais para Configurar seria
     enganar quem le a barra lateral.

     Mesmo traco 1.5 e mesma caixa 24x24 do site, para o conjunto parecer um
     so.
     --------------------------------------------------------- */
  var ICONES = {
    lista:
      '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/>' +
      '<path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
    mais: '<path d="M12 5v14"/><path d="M5 12h14"/>',
    publicar:
      '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>' +
      '<path d="M7 9l5-5 5 5"/><path d="M12 4v12"/>',
    relogio:
      '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    engrenagem:
      '<circle cx="12" cy="12" r="3"/>' +
      '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1.08-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "olho-riscado":
      '<path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 10 8 10 8a18.5 18.5 0 0 1-2.16 3.19"/>' +
      '<path d="M6.61 6.61A18.15 18.15 0 0 0 2 12s3 8 10 8a9.12 9.12 0 0 0 5.39-1.61"/>' +
      '<path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><path d="m2 2 20 20"/>',
    alerta:
      '<path d="M12 9v4"/><path d="M12 17h.01"/>' +
      '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>',
    "seta-baixo": '<path d="m6 9 6 6 6-6"/>',
  };

  function icone(nome, cls) {
    var d = ICONES[nome];
    if (!d) return U.icone(nome, cls);
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

  /** Troca <span data-icone-painel="nome"> pelo SVG, como UI.hidrataIcones. */
  function hidrata(raiz) {
    Array.prototype.forEach.call(
      (raiz || document).querySelectorAll("[data-icone-painel]"),
      function (el) {
        var svg = icone(el.getAttribute("data-icone-painel"), el.className || null);
        if (svg) el.outerHTML = svg;
      }
    );
    U.hidrataIcones(raiz || document);
  }

  /* ---------------------------------------------------------
     Avisos (toast)
     --------------------------------------------------------- */
  var SEGUNDOS_SUCESSO = 5000;

  /**
   * @param {string} mensagem
   * @param {{tipo?: "ok"|"erro", acoes?: Array<{texto:string, ir?:string, aoClicar?:Function}>}} [op]
   */
  function avisa(mensagem, op) {
    op = op || {};
    var erro = op.tipo === "erro";

    var el = document.createElement("div");
    el.className = "toast" + (erro ? " toast--erro" : "");
    el.innerHTML = U.icone(erro ? "x" : "check");

    var corpo = document.createElement("div");
    corpo.className = "toast__corpo";
    corpo.textContent = mensagem;
    el.appendChild(corpo);

    (op.acoes || []).forEach(function (a) {
      var acoes = corpo.querySelector(".toast__acoes");
      if (!acoes) {
        acoes = document.createElement("div");
        acoes.className = "toast__acoes";
        corpo.appendChild(acoes);
      }
      var b = document.createElement("button");
      b.className = "botao botao--claro";
      b.type = "button";
      b.textContent = a.texto;
      b.addEventListener("click", function () {
        fecha();
        if (a.ir) vaiPara(a.ir);
        if (a.aoClicar) a.aoClicar();
      });
      acoes.appendChild(b);
    });

    var fechar = document.createElement("button");
    fechar.className = "toast__fechar";
    fechar.type = "button";
    fechar.setAttribute("aria-label", "Fechar aviso");
    fechar.innerHTML = U.icone("x");
    fechar.addEventListener("click", fecha);
    el.appendChild(fechar);

    /* role="alert" faz o leitor de tela interromper e anunciar na hora; para
       sucesso, "status" espera a pausa natural (PRD 7.7). */
    elToasts.setAttribute("role", erro ? "alert" : "status");
    elToasts.appendChild(el);

    var timer = null;
    function fecha() {
      if (timer) clearTimeout(timer);
      el.classList.add("is-saindo");
      setTimeout(function () {
        el.remove();
      }, 200);
    }
    /* Erro fica na tela ate ser fechado: a pessoa precisa poder ler com
       calma, e pode estar olhando outra coisa quando ele apareceu. */
    if (!erro) timer = setTimeout(fecha, SEGUNDOS_SUCESSO);
    return fecha;
  }

  /* ---------------------------------------------------------
     Montagem de HTML auxiliar
     --------------------------------------------------------- */
  function h(tag, attrs, filhos) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "class") el.className = attrs[k];
      else if (k === "texto") el.textContent = attrs[k];
      else if (k === "html") el.innerHTML = attrs[k];
      else if (attrs[k] != null) el.setAttribute(k, attrs[k]);
    });
    (filhos || []).forEach(function (f) {
      if (f) el.appendChild(typeof f === "string" ? document.createTextNode(f) : f);
    });
    return el;
  }

  function telaTopo(titulo, texto, acao) {
    return h("div", { class: "tela-topo" }, [
      h("div", {}, [
        h("p", { class: "eyebrow", texto: "UFC Inova · Propriedade Intelectual" }),
        h("h2", { texto: titulo }),
        texto ? h("p", { class: "tela-topo__texto", texto: texto }) : null,
      ]),
      acao || null,
    ]);
  }

  function caixa(titulo, filhos) {
    return h("section", { class: "painel-caixa" }, [
      titulo ? h("h3", { class: "painel-caixa__titulo", texto: titulo }) : null,
    ].concat(filhos || []));
  }

  function vazio(mensagem, icone) {
    return h("div", { class: "painel-vazio" }, [
      h("div", { html: U.icone(icone || "search") }),
      h("p", { texto: mensagem }),
    ]);
  }

  /** Placeholder honesto para as telas que ainda nao existem. */
  function emConstrucao(qual, fase) {
    return h("div", { class: "painel-vazio" }, [
      h("div", { html: U.icone("file-text") }),
      h("p", { texto: qual + " entra na Fase " + fase + " do plano." }),
      h("p", {
        class: "campo__ajuda",
        texto: "A casca, a navegação e os componentes visuais já estão prontos.",
      }),
    ]);
  }

  /* ---------------------------------------------------------
     Status de uma patente (PRD 7.4)
     --------------------------------------------------------- */
  function statusDaPatente(p) {
    if (p.problema) {
      return { classe: "problema", icone: "x", texto: "Precisa de atenção" };
    }
    if (p.oculta) {
      return { classe: "oculta", icone: "x", texto: "Oculta" };
    }
    return { classe: "publicada", icone: "check", texto: "Na vitrine" };
  }

  function chipDeStatus(p) {
    var s = statusDaPatente(p);
    return h("span", { class: "status-chip status-chip--" + s.classe }, [
      h("span", { html: U.icone(s.icone) }),
      s.texto,
    ]);
  }

  /* ---------------------------------------------------------
     T1 — Patentes
     --------------------------------------------------------- */
  function telaLista() {
    var frag = document.createDocumentFragment();

    frag.appendChild(
      telaTopo(
        "Patentes",
        null,
        h("a", { class: "botao botao--primario", href: "#/nova" }, ["+ Nova patente"])
      )
    );

    var info = estado.info || {};
    frag.appendChild(
      h("dl", { class: "tela-numeros" }, [
        h("div", {}, [
          h("dt", { texto: "Na vitrine" }),
          h("dd", { texto: String(info.naVitrine || 0) }),
        ]),
        h("div", {}, [
          h("dt", { texto: "Ocultas" }),
          h("dd", { texto: String(info.ocultas || 0) }),
        ]),
        h("div", {}, [
          h("dt", { texto: "Na lixeira" }),
          h("dd", { texto: String(info.naLixeira || 0) }),
        ]),
        h("div", {}, [
          h("dt", { texto: "Áreas" }),
          h("dd", { texto: String(info.areas || 0) }),
        ]),
      ])
    );

    var busca = h("div", { class: "busca" }, [
      h("span", { class: "busca__icone", html: U.icone("search") }),
      h("label", {
        class: "visualmente-oculto",
        for: "busca-painel",
        texto: "Buscar patentes por título, número ou área",
      }),
      h("input", {
        class: "busca__campo",
        id: "busca-painel",
        type: "search",
        autocomplete: "off",
        spellcheck: "false",
        placeholder: "Buscar por título, número ou área",
      }),
    ]);
    frag.appendChild(h("div", { class: "painel-busca" }, [busca]));

    var corpo = h("tbody", {});
    var tabela = h("div", { class: "tabela-envolve" }, [
      h("table", { class: "tabela" }, [
        h("thead", {}, [
          h("tr", {}, [
            h("th", { class: "tabela__col-mini", scope: "col" }),
            h("th", { class: "tabela__col-id", texto: "ID", scope: "col" }),
            h("th", { texto: "Título", scope: "col" }),
            h("th", { texto: "Área", scope: "col" }),
            h("th", { texto: "Status", scope: "col" }),
            h("th", { class: "tabela__col-acoes", scope: "col" }),
          ]),
        ]),
        corpo,
      ]),
    ]);
    frag.appendChild(tabela);

    var lista = estado.patentes || [];

    function pinta(termo) {
      corpo.textContent = "";
      var filtradas = lista.filter(function (p) {
        if (!termo) return true;
        var alvo = U.normaliza(
          [p.titulo, p.numero, p.categoria, p.id].join(" ")
        );
        return alvo.indexOf(U.normaliza(termo)) >= 0;
      });

      if (!filtradas.length) {
        var td = h("td", { colspan: "6" }, [
          vazio(lista.length ? "Nenhuma patente encontrada." : "O acervo está vazio."),
        ]);
        corpo.appendChild(h("tr", {}, [td]));
        return;
      }

      filtradas.forEach(function (p) {
        corpo.appendChild(
          h("tr", { "data-id": String(p.id) }, [
            h("td", { class: "tabela__col-mini" }, [h("div", { class: "tabela__mini" })]),
            h("td", { class: "tabela__id tabela__col-id", texto: String(p.id) }),
            h("td", {}, [
              h("span", { class: "tabela__titulo", texto: p.titulo || "(sem título)" }),
              h("span", { class: "tabela__numero", texto: p.numero }),
            ]),
            h("td", {}, [h("span", { class: "eyebrow", texto: p.categoria || "—" })]),
            h("td", {}, [chipDeStatus(p)]),
            h("td", { class: "tabela__col-acoes" }, [
              h("div", { class: "tabela__acoes" }, [
                h(
                  "a",
                  { class: "botao botao--terciario", href: "#/editar/" + p.id },
                  ["Editar"]
                ),
              ]),
            ]),
          ])
        );
      });
    }

    pinta("");
    busca.querySelector("input").addEventListener(
      "input",
      U.debounce(function (e) {
        pinta(e.target.value);
      }, 150)
    );

    return frag;
  }

  /* ---------------------------------------------------------
     T5 — Configurar
     --------------------------------------------------------- */
  function telaConfigurar() {
    var frag = document.createDocumentFragment();
    var info = estado.info || {};

    frag.appendChild(
      telaTopo(
        info.configurado ? "Configurar" : "Vamos conectar o painel à vitrine",
        info.configurado
          ? "As pastas só mudam pelo seletor do Windows: não há campo para digitar caminho."
          : "Dois passos. Depois disso o painel lembra das pastas."
      )
    );

    [
      {
        n: 1,
        tipo: "site",
        titulo: "Pasta do site",
        ajuda: "A pasta que contém o arquivo index.html da vitrine.",
        valor: info.pastaSite,
      },
      {
        n: 2,
        tipo: "acervo",
        titulo: "Pasta do acervo (fichas originais)",
        ajuda: "A pasta com as subpastas no padrão 1. BR 10 2014 030019 8.",
        valor: info.pastaAcervo,
      },
    ].forEach(function (passo) {
      var caminho = h("p", {
        class: "campo__ajuda",
        texto: passo.valor || "Nenhuma pasta escolhida ainda.",
      });
      frag.appendChild(
        caixa(passo.n + ". " + passo.titulo, [
          h("p", { class: "campo__ajuda", texto: passo.ajuda }),
          h("div", { class: "arquivo__acoes", style: null }, [
            h(
              "button",
              {
                class: "botao botao--secundario",
                type: "button",
                "data-escolher": passo.tipo,
              },
              ["Escolher pasta"]
            ),
          ]),
          caminho,
        ])
      );
    });

    frag.appendChild(
      caixa("Áreas tecnológicas", [
        h("p", {
          class: "campo__ajuda",
          texto:
            (info.areas || 0) +
            " áreas no mapa. Acrescentar uma área entra na Fase 6.",
        }),
      ])
    );

    return frag;
  }

  /* ---------------------------------------------------------
     Roteador
     --------------------------------------------------------- */
  var ROTAS = {
    lista: { titulo: "Patentes", monta: telaLista },
    nova: {
      titulo: "Nova patente",
      monta: function () {
        return emConstrucao("O cadastro de patente", 5);
      },
    },
    editar: {
      titulo: "Editar patente",
      monta: function () {
        return emConstrucao("A edição de patente", 5);
      },
    },
    publicar: {
      titulo: "Publicar",
      monta: function () {
        return emConstrucao("A tela de publicação", 6);
      },
    },
    historico: {
      titulo: "Histórico",
      monta: function () {
        return emConstrucao("O histórico", 6);
      },
    },
    configurar: { titulo: "Configurar", monta: telaConfigurar },
  };

  function rotaAtual() {
    var bruto = (location.hash || "").replace(/^#\/?/, "");
    var partes = bruto.split("/").filter(Boolean);
    var nome = partes[0] || "lista";
    if (!ROTAS[nome]) nome = "lista";
    return { nome: nome, args: partes.slice(1) };
  }

  function vaiPara(hash) {
    if (location.hash === hash) desenha();
    else location.hash = hash;
  }

  function marcaMenu(nome) {
    var pronto = !estado.info || estado.info.configurado;
    Array.prototype.forEach.call(
      elMenu.querySelectorAll("[data-rota]"),
      function (a) {
        var rota = a.getAttribute("data-rota");
        var ativo = rota === nome || (nome === "editar" && rota === "lista");
        if (ativo) a.setAttribute("aria-current", "page");
        else a.removeAttribute("aria-current");

        /* Sem configuracao, so Configurar leva a algum lugar. */
        if (!pronto && rota !== "configurar") {
          a.setAttribute("aria-disabled", "true");
          a.setAttribute("tabindex", "-1");
        } else {
          a.removeAttribute("aria-disabled");
          a.removeAttribute("tabindex");
        }
      }
    );
  }

  function desenha() {
    var r = rotaAtual();
    marcaMenu(r.nome);

    /* Primeira execucao sem configuracao valida: a tela T0 e a unica saida.
       Deixar a pessoa navegar para "Nova patente" sem saber onde gravar
       renderia um formulario que nao pode salvar. */
    if (estado.info && !estado.info.configurado && r.nome !== "configurar") {
      location.hash = "#/configurar";
      return;
    }

    document.title = ROTAS[r.nome].titulo + " — Painel da Vitrine";

    var tela = h("div", { class: "painel-largura painel-tela" }, []);
    tela.appendChild(ROTAS[r.nome].monta(r.args));
    elTela.textContent = "";
    elTela.appendChild(tela);
    hidrata(elTela);
    elTela.scrollTop = 0;
  }

  /* ---------------------------------------------------------
     Contador de alteracoes nao publicadas
     --------------------------------------------------------- */
  function pintaPendentes() {
    var n = (estado.info && estado.info.naoPublicadas) || 0;
    elPendentes.hidden = n === 0;
    if (!n) return;
    elPendentes.querySelector("[data-pendentes-n]").textContent = String(n);
    elPendentes.querySelector("[data-pendentes-texto]").textContent =
      n === 1 ? "alteração não publicada" : "alterações não publicadas";
  }

  /* ---------------------------------------------------------
     Carregamento
     --------------------------------------------------------- */
  function carregaEstado() {
    return API.estado()
      .then(function (info) {
        estado.info = info;
        var u = document.querySelector("[data-usuario]");
        if (u && info.usuario) u.textContent = info.usuario;
        pintaPendentes();
        return info;
      })
      .catch(function (e) {
        avisa(e.mensagem, { tipo: "erro" });
        estado.info = { configurado: false };
      });
  }

  function carregaPatentes() {
    if (!estado.info || !estado.info.configurado) return Promise.resolve();
    return API.listar()
      .then(function (d) {
        estado.patentes = d.patentes;
      })
      .catch(function (e) {
        avisa(e.mensagem, { tipo: "erro" });
        estado.patentes = [];
      });
  }

  function recarrega() {
    return carregaEstado().then(carregaPatentes).then(desenha);
  }

  /* ---------------------------------------------------------
     Eventos
     --------------------------------------------------------- */
  window.addEventListener("hashchange", function () {
    if (estado.sujo && !confirm("Há alterações não salvas. Sair mesmo assim?")) {
      return;
    }
    estado.sujo = false;
    desenha();
  });

  /* Delegacao: as telas sao redesenhadas, entao ouvir no container evita
     religar handler a cada pintura. */
  elTela.addEventListener("click", function (e) {
    var escolher = e.target.closest("[data-escolher]");
    if (escolher) {
      var tipo = escolher.getAttribute("data-escolher");
      API.escolher_pasta(tipo)
        .then(function (d) {
          if (d.cancelado) return;
          var outra = tipo === "site" ? "pastaAcervo" : "pastaSite";
          var args =
            tipo === "site"
              ? [d.caminho, (estado.info || {}).pastaAcervo || ""]
              : [(estado.info || {}).pastaSite || "", d.caminho];
          /* Guarda o escolhido na tela mesmo antes de as duas estarem
             prontas, para a pessoa ver o progresso dos dois passos. */
          estado.info = estado.info || {};
          estado.info[tipo === "site" ? "pastaSite" : "pastaAcervo"] = d.caminho;
          if (!estado.info[outra]) {
            desenha();
            return;
          }
          return API.configurar(args[0], args[1]).then(function (info) {
            estado.info = info;
            avisa("Pastas conectadas. O painel está pronto.");
            return carregaPatentes().then(function () {
              vaiPara("#/lista");
            });
          });
        })
        .catch(function (err) {
          avisa(err.mensagem, { tipo: "erro" });
        });
    }
  });

  /* Expoe o minimo para as telas das fases seguintes, sem poluir o global. */
  /* A casca (barra lateral e cabecalho) e montada uma vez e nunca redesenhada,
     entao os icones dela precisam ser hidratados aqui -- `desenha()` so cuida
     da area de conteudo. */
  hidrata(document);

  window.PAINEL = {
    icone: icone,
    hidrata: hidrata,
    avisa: avisa,
    h: h,
    caixa: caixa,
    vazio: vazio,
    telaTopo: telaTopo,
    chipDeStatus: chipDeStatus,
    estado: estado,
    recarrega: recarrega,
    vaiPara: vaiPara,
    desenha: desenha,
  };

  recarrega();
})();
