/* Preenche a galeria de componentes. Ferramenta de revisao, nao produto.

   Sem atributo style em lugar nenhum: a CSP bloqueia. O unico estilo aplicado
   por JS e via CSSOM (`el.style.background`), que a CSP permite. */
(function () {
  "use strict";

  var U = window.UI;

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

  /* ---------------------------------------------------------
     Amostras de cor, com o contraste medido
     --------------------------------------------------------- */
  var CORES = [
    {
      nome: "--c-danger",
      hex: "#ED455A",
      fundo: "#ED455A",
      texto: "#fff",
      contraste: "3,41:1 sobre o fundo",
      fraco: true,
      uso: "Borda de campo inválido (2 px), ícone de erro, barra do resumo, anel de foco. Nunca como texto.",
    },
    {
      nome: "--c-danger-700",
      hex: "#D1142C",
      fundo: "#D1142C",
      texto: "#fff",
      contraste: "4,97:1 sobre o fundo",
      uso: "TEXTO das mensagens de erro e fundo do botão de exclusão definitiva.",
    },
    {
      nome: "--c-danger-800",
      hex: "#A71023",
      fundo: "#A71023",
      texto: "#fff",
      contraste: "6,97:1 sobre o fundo",
      uso: "Hover e pressed do botão destrutivo.",
    },
    {
      nome: "--c-danger-100",
      hex: "#FCDEE2",
      fundo: "#FCDEE2",
      texto: "#A71023",
      uso: "Fundo de badge e de marcador de checagem reprovada.",
    },
    {
      nome: "--c-danger-50",
      hex: "#FEF1F3",
      fundo: "#FEF1F3",
      texto: "#A71023",
      uso: "Fundo da caixa de resumo de erros.",
    },
    {
      nome: "--c-brand",
      hex: "#5C069D",
      fundo: "#5C069D",
      texto: "#fff",
      contraste: "9,4:1 sobre o fundo",
      uso: "A cor da marca. Tudo que não é erro continua usando a paleta do site.",
    },
  ];

  var cores = document.querySelector("[data-cores]");
  CORES.forEach(function (c) {
    var faixa = h("div", { class: "amostra__faixa", texto: c.hex });
    /* CSSOM, nao atributo style: a CSP permite um e bloqueia o outro. */
    faixa.style.background = c.fundo;
    faixa.style.color = c.texto;
    cores.appendChild(
      h("div", { class: "amostra" }, [
        faixa,
        h("div", { class: "amostra__corpo" }, [
          h("p", { class: "amostra__nome", texto: c.nome }),
          h("p", { class: "amostra__uso", texto: c.uso }),
          c.contraste
            ? h("span", {
                class: "amostra__contraste" + (c.fraco ? " is-fraco" : ""),
                texto:
                  c.contraste + (c.fraco ? " · só gráfico" : " · serve como texto"),
              })
            : null,
        ]),
      ])
    );
  });

  /* ---------------------------------------------------------
     Diferenciais
     --------------------------------------------------------- */
  var SETA_BAIXO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="m6 9 6 6 6-6"/></svg>';

  var ITENS = [
    "Alto teor proteico",
    "Preservação do sabor natural",
    "Processo eficiente de secagem",
  ];
  var dif = document.querySelector("[data-diferenciais]");
  ITENS.forEach(function (texto, i) {
    dif.appendChild(
      h("div", { class: "diferencial" }, [
        h("input", {
          type: "text",
          value: texto,
          "aria-label": "Diferencial " + (i + 1),
        }),
        h("div", { class: "diferencial__botoes" }, [
          h("button", {
            class: "botao-icone",
            type: "button",
            "aria-label": "Mover para cima",
            disabled: i === 0 ? "" : null,
            html: U.icone("chevron-up"),
          }),
          h("button", {
            class: "botao-icone",
            type: "button",
            "aria-label": "Mover para baixo",
            disabled: i === ITENS.length - 1 ? "" : null,
            html: SETA_BAIXO,
          }),
          h("button", {
            class: "botao-icone botao-icone--remover",
            type: "button",
            "aria-label": "Remover diferencial " + (i + 1),
            html: U.icone("x"),
          }),
        ]),
      ])
    );
  });

  /* ---------------------------------------------------------
     TRL
     --------------------------------------------------------- */
  var trl = document.querySelector("[data-trl]");
  var barra = h("div", {
    class: "trl__barra",
    role: "group",
    "aria-label": "Nível de maturidade",
  });
  for (var n = 1; n <= 9; n++) {
    var ativo = n >= 5 && n <= 6;
    barra.appendChild(
      h("button", {
        class: "trl-seg" + (ativo ? " is-ativo" : ""),
        type: "button",
        "aria-label": "TRL " + n,
        "aria-pressed": String(ativo),
      })
    );
  }
  trl.appendChild(
    h("div", { class: "trl" }, [
      barra,
      h("p", {
        class: "trl__rotulo",
        html: "Maturidade tecnológica: <strong>TRL 5–6</strong>",
      }),
    ])
  );

  function selectTrl(rotulo, valor) {
    var sel = h("select", { "aria-label": rotulo });
    for (var i = 1; i <= 9; i++) {
      sel.appendChild(
        h("option", { texto: String(i), selected: i === valor ? "" : null })
      );
    }
    return h("div", { class: "campo" }, [
      h("label", { class: "campo__rotulo" }, [h("span", { texto: rotulo })]),
      sel,
    ]);
  }

  trl.appendChild(
    h("div", { class: "trl-editor__alternativa" }, [
      selectTrl("Mínimo", 5),
      selectTrl("Máximo", 6),
      h("label", { class: "campo__rotulo" }, [
        h("input", { type: "checkbox" }),
        h("span", { texto: " Estimado" }),
      ]),
    ])
  );

  /* ---------------------------------------------------------
     Tabela
     --------------------------------------------------------- */
  var LINHAS = [
    {
      id: 1,
      titulo: "Camarão em Pó Natural para Aplicações Alimentícias",
      numero: "BR 10 2014 030019-8",
      area: "Alimentos",
      tipo: "PI",
      status: "publicada",
    },
    {
      id: 12,
      titulo: "Compósito cerâmico estável para micro-ondas (τf próximo de zero)",
      numero: "BR 10 2019 014234-1",
      area: "Engenharias",
      tipo: "PI",
      status: "pendente",
    },
    {
      id: 29,
      titulo: "Método de pigmentação para plastinação anatômica",
      numero: "BR 10 2020 001102-2",
      area: "Ciências da Saúde",
      tipo: "PI",
      status: "oculta",
    },
    {
      id: 62,
      titulo: "Patente com patente.json inválido",
      numero: "BR 20 2026 088888-8",
      area: "—",
      tipo: "MU",
      status: "problema",
    },
  ];

  var STATUS = {
    publicada: { icone: "check", texto: "Na vitrine" },
    pendente: { icone: "arrow-up-right", texto: "Alterada — não publicada" },
    oculta: { icone: "x", texto: "Oculta" },
    problema: { icone: "x", texto: "Precisa de atenção" },
  };

  var corpo = h("tbody", {});
  LINHAS.forEach(function (l) {
    var s = STATUS[l.status];
    corpo.appendChild(
      h("tr", {}, [
        h("td", {}, [h("div", { class: "tabela__mini" })]),
        h("td", { class: "tabela__id", texto: String(l.id) }),
        h("td", {}, [
          h("span", { class: "tabela__titulo", texto: l.titulo }),
          h("span", { class: "tabela__numero", texto: l.numero }),
        ]),
        h("td", {}, [h("span", { class: "eyebrow", texto: l.area })]),
        h("td", {}, [h("span", { class: "badge", texto: l.tipo })]),
        h("td", {}, [
          h("span", { class: "status-chip status-chip--" + l.status }, [
            h("span", { html: U.icone(s.icone) }),
            s.texto,
          ]),
        ]),
        h("td", {}, [
          h("div", { class: "tabela__acoes" }, [
            h("button", {
              class: "botao botao--terciario",
              type: "button",
              texto: "Editar",
            }),
            h("button", {
              class: "botao-icone",
              type: "button",
              "aria-label": "Mais ações",
              texto: "⋯",
            }),
          ]),
        ]),
      ])
    );
  });

  document.querySelector("[data-tabela]").appendChild(
    h("table", { class: "tabela" }, [
      h("thead", {}, [
        h("tr", {}, [
          h("th", { scope: "col" }),
          h("th", { scope: "col", texto: "ID" }),
          h("th", { scope: "col", texto: "Título" }),
          h("th", { scope: "col", texto: "Área" }),
          h("th", { scope: "col", texto: "Tipo" }),
          h("th", { scope: "col", texto: "Status" }),
          h("th", { scope: "col" }),
        ]),
      ]),
      corpo,
    ])
  );

  /* ---------------------------------------------------------
     Etapas do build
     --------------------------------------------------------- */
  var ETAPAS = [
    ["Validando as informações", "ok"],
    ["Salvando no acervo", "ok"],
    ["Otimizando as imagens", "fazendo"],
    ["Gerando a ficha", ""],
    ["Atualizando a vitrine", ""],
  ];
  var ul = document.querySelector("[data-etapas]");
  ETAPAS.forEach(function (e) {
    var icone = e[1] === "ok" ? U.icone("check") : e[1] === "erro" ? U.icone("x") : "";
    ul.appendChild(
      h("li", { class: "etapa" + (e[1] ? " is-" + e[1] : "") }, [
        h("span", { class: "etapa__marca", html: icone }),
        e[0],
      ])
    );
  });

  /* ---------------------------------------------------------
     Checklist
     --------------------------------------------------------- */
  var CHECAGENS = [
    ["A vitrine foi gerada sem erros", true, ""],
    ["60 patentes na vitrine", true, ""],
    ["Todos os arquivos da vitrine estão presentes", true, ""],
    [
      "Nenhuma pasta de patente fora da vitrine",
      false,
      "1 pasta sobrando em assets/patentes: 29-metodo-de-pigmentacao. Rode a atualização da vitrine.",
    ],
  ];
  var cl = document.querySelector("[data-checklist]");
  CHECAGENS.forEach(function (c) {
    cl.appendChild(
      h("li", { class: "checagem " + (c[1] ? "is-ok" : "is-erro") }, [
        h("span", { class: "checagem__marca", html: U.icone(c[1] ? "check" : "x") }),
        h("div", {}, [
          h("p", { class: "checagem__texto", texto: c[0] }),
          c[2] ? h("p", { class: "checagem__detalhe", texto: c[2] }) : null,
        ]),
      ])
    );
  });

  /* ---------------------------------------------------------
     Toasts
     --------------------------------------------------------- */
  function toast(tipo, mensagem, acoes) {
    var el = h("div", { class: "toast" + (tipo === "erro" ? " toast--erro" : "") }, []);
    el.innerHTML = U.icone(tipo === "erro" ? "x" : "check");
    var corpoToast = h("div", { class: "toast__corpo", texto: mensagem });
    if (acoes) {
      corpoToast.appendChild(
        h(
          "div",
          { class: "toast__acoes" },
          acoes.map(function (t) {
            return h("button", {
              class: "botao botao--claro",
              type: "button",
              texto: t,
            });
          })
        )
      );
    }
    el.appendChild(corpoToast);
    var f = h("button", {
      class: "toast__fechar",
      type: "button",
      "aria-label": "Fechar",
    });
    f.innerHTML = U.icone("x");
    el.appendChild(f);
    return el;
  }

  var demo = document.querySelector("[data-toasts-demo]");
  demo.appendChild(
    toast("ok", "Patente salva. A vitrine local foi atualizada.", [
      "Ver no site local",
      "Voltar para a lista",
    ])
  );
  demo.appendChild(
    toast(
      "erro",
      "A vitrine não foi atualizada porque encontramos 2 problemas. Nada foi alterado no site."
    )
  );

  /* ---------------------------------------------------------
     Confirmacao destrutiva
     --------------------------------------------------------- */
  document.querySelector("[data-modal-demo]").appendChild(
    h("div", { class: "modal" }, [
      h("div", { class: "modal__corpo" }, [
        h("h3", { class: "modal__titulo", texto: "Mover para a lixeira" }),
        h("p", {
          class: "modal__texto",
          texto:
            "A patente sai da vitrine, mas nada é apagado: a pasta vai para a lixeira do acervo e pode ser restaurada pelo histórico.",
        }),
        h("div", { class: "campo" }, [
          h("label", { class: "campo__rotulo", for: "g-conf" }, [
            h("span", { texto: "Digite o número do pedido para confirmar" }),
          ]),
          h("input", {
            id: "g-conf",
            type: "text",
            placeholder: "BR 10 2020 001102-2",
          }),
          h("p", { class: "campo__ajuda", texto: "BR 10 2020 001102-2" }),
        ]),
      ]),
      h("div", { class: "modal__acoes" }, [
        h("button", {
          class: "botao botao--terciario",
          type: "button",
          texto: "Cancelar",
        }),
        h("button", {
          class: "botao botao--perigo",
          type: "button",
          disabled: "",
          texto: "Mover para a lixeira",
        }),
      ]),
    ])
  );

  /* O icone entra antes do texto nas mensagens de erro: o erro precisa ser
     reconhecivel sem depender da cor (PRD 7.3). */
  document.querySelectorAll("[data-icone-erro]").forEach(function (p) {
    p.insertAdjacentHTML("afterbegin", U.icone("x"));
  });
  document.querySelectorAll("[data-resumo-erros] h3").forEach(function (t) {
    t.insertAdjacentHTML("afterbegin", U.icone("x"));
  });

  U.hidrataIcones(document);
})();
