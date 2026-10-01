/* ============================================================
   api-cliente.js — o UNICO ponto da interface que toca
   window.pywebview.api.

   Por que centralizar: a ponte do pywebview so existe depois do evento
   `pywebviewready`, toda resposta vem no formato {ok, dados|erro}, e nenhum
   erro pode chegar cru a tela. Espalhar isso pelas telas garantiria que uma
   delas esquecesse de tratar um dos tres casos.

   Expoe window.API. Cada metodo devolve uma Promise que:
     - RESOLVE com `dados` quando ok;
     - REJEITA com um Error que tem `.codigo`, `.mensagem` e `.campos`.

   Assim as telas usam try/catch normal e nunca precisam olhar `resposta.ok`.
   ============================================================ */
(function () {
  "use strict";

  /* A lista de metodos e a tabela 5.3 do PRD. Esta escrita aqui de proposito:
     se a interface chamar algo que o Python nao expoe, o erro aparece no
     desenvolvimento e nao numa tela que a equipe abriu. */
  var METODOS = [
    "estado",
    "configurar",
    "escolher_pasta",
    "listar",
    "obter",
    "escolher_arquivo",
    "receber_arquivo",
    "ler_ficha",
    "ler_texto_ficha",
    "previa",
    "salvar",
    "alternar_oculta",
    "excluir",
    "rodar_build",
    "historico",
    "restaurar",
    "gerar_pacote",
    "abrir_pasta",
    "abrir_link",
    "ver_site_local",
  ];

  var pronto = null;

  /** Resolve quando a ponte do pywebview estiver disponivel. */
  function esperaPonte() {
    if (pronto) return pronto;
    pronto = new Promise(function (resolve, reject) {
      if (window.pywebview && window.pywebview.api) return resolve();

      var acabou = false;
      function ok() {
        if (acabou) return;
        acabou = true;
        resolve();
      }
      window.addEventListener("pywebviewready", ok, { once: true });

      /* Sem a ponte em 8 segundos, algo esta errado de verdade. Falhar com
         mensagem e melhor que uma tela que nunca carrega. */
      setTimeout(function () {
        if (acabou) return;
        if (window.pywebview && window.pywebview.api) return ok();
        acabou = true;
        reject(
          erro(
            "E-PONTE",
            "Não conseguimos falar com o programa. Feche e abra o painel de novo."
          )
        );
      }, 8000);
    });
    return pronto;
  }

  function erro(codigo, mensagem, campos) {
    var e = new Error(mensagem);
    e.codigo = codigo || "E-GERAL";
    e.mensagem = mensagem;
    e.campos = campos || null;
    return e;
  }

  function chama(nome, args) {
    return esperaPonte()
      .then(function () {
        var fn = window.pywebview.api[nome];
        if (typeof fn !== "function") {
          throw erro("E-METODO", "Esta ação não está disponível nesta versão.");
        }
        return fn.apply(window.pywebview.api, args);
      })
      .then(function (r) {
        /* Resposta fora do formato {ok, ...} e bug, nao erro de uso: trata
           como falha em vez de seguir com dados indefinidos. */
        if (!r || typeof r !== "object" || typeof r.ok !== "boolean") {
          throw erro("E-FORMATO", "O programa respondeu de forma inesperada.");
        }
        if (r.ok) return r.dados;
        var d = r.erro || {};
        throw erro(d.codigo, d.mensagem || "Algo deu errado.", d.campos);
      });
  }

  var API = {};
  METODOS.forEach(function (nome) {
    API[nome] = function () {
      return chama(nome, Array.prototype.slice.call(arguments));
    };
  });

  /** Lista de metodos, para o teste de contrato da interface. */
  API._metodos = METODOS.slice();

  /** True quando ha ponte (falso nos testes com a API simulada por injecao). */
  API._temPonte = function () {
    return !!(window.pywebview && window.pywebview.api);
  };

  window.API = API;
})();
