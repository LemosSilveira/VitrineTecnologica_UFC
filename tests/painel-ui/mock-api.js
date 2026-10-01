/* ============================================================
   mock-api.js — implementa window.pywebview.api para os testes de
   interface e para a revisao visual.

   Injetado ANTES dos scripts da pagina, entao `api-cliente.js` encontra a
   ponte ja pronta e nao espera pelo evento `pywebviewready`.

   Respostas controladas, no MESMO formato do Python ({ok, dados|erro}): a
   interface nao deve conseguir distinguir este mock do backend real. Cenarios
   de erro sao ligados por `window.__MOCK.cenario`.
   ============================================================ */
(function () {
  "use strict";

  var cfg = (window.__MOCK = window.__MOCK || {});
  cfg.cenario = cfg.cenario || "normal";
  cfg.chamadas = [];

  var AREAS = [
    "Agropecuária",
    "Alimentos",
    "Biotecnologia",
    "Ciências da Saúde",
    "Cosméticos",
    "Energia e Meio Ambiente",
    "Engenharias",
    "Indústria",
    "Química",
    "TIC",
  ];

  var PATENTES = [
    {
      id: 1,
      numero: "BR 10 2014 030019-8",
      titulo: "Camarão em Pó Natural para Aplicações Alimentícias",
      categoria: "Alimentos",
      oculta: false,
      editada: false,
      temPdf: true,
      temCapa: true,
      problema: "",
    },
    {
      id: 12,
      numero: "BR 10 2019 014234-1",
      titulo: "Compósito cerâmico estável para micro-ondas (τf próximo de zero)",
      categoria: "Engenharias",
      oculta: false,
      editada: true,
      temPdf: true,
      temCapa: true,
      problema: "",
    },
    {
      id: 29,
      numero: "BR 10 2020 001102-2",
      titulo: "Método de pigmentação para plastinação anatômica de baixo custo",
      categoria: "Ciências da Saúde",
      oculta: true,
      editada: true,
      temPdf: true,
      temCapa: true,
      problema: "",
    },
    {
      id: 47,
      numero: "BR 10 2021 019930-0",
      titulo: "Concreto ecológico de alto desempenho",
      categoria: "Engenharias",
      oculta: false,
      editada: false,
      temPdf: true,
      temCapa: true,
      problema: "",
    },
    {
      id: 61,
      numero: "BR 10 2026 099999-9",
      titulo: "Tecnologia cadastrada sem ficha em PDF",
      categoria: "Alimentos",
      oculta: false,
      editada: true,
      temPdf: false,
      temCapa: true,
      problema: "",
    },
    {
      id: 62,
      numero: "BR 20 2026 088888-8",
      titulo: "Patente com patente.json inválido",
      categoria: "",
      oculta: false,
      editada: true,
      temPdf: true,
      temCapa: true,
      problema: "campos: campo desconhecido 'titluo'.",
    },
  ];

  function ok(dados) {
    return Promise.resolve({ ok: true, dados: dados });
  }

  function erro(codigo, mensagem, campos) {
    var e = { codigo: codigo, mensagem: mensagem };
    if (campos) e.campos = campos;
    return Promise.resolve({ ok: false, erro: e });
  }

  function registra(nome, args) {
    cfg.chamadas.push({ metodo: nome, args: args });
  }

  var api = {
    estado: function () {
      registra("estado", []);
      if (cfg.cenario === "sem-configuracao") {
        return ok({
          configurado: false,
          versao: "1.0.0",
          usuario: "usuario.windows",
          pastaSite: "",
          pastaAcervo: "",
          proximoPasso: "",
          naVitrine: 0,
          ocultas: 0,
          naLixeira: 0,
          areas: 0,
        });
      }
      return ok({
        configurado: true,
        versao: "1.0.0",
        usuario: "usuario.windows",
        pastaSite: "C:\\Users\\Usuario\\Desktop\\vitrinePI_site",
        pastaAcervo: "C:\\Users\\Usuario\\Documents\\50 Patentes Observatório",
        proximoPasso: "Envie o .zip para a STI pelo e-mail de sempre.",
        naVitrine: 60,
        ocultas: 1,
        naLixeira: 2,
        areas: AREAS.length,
        naoPublicadas: 3,
      });
    },

    configurar: function (site, acervo) {
      registra("configurar", [site, acervo]);
      if (cfg.cenario === "pasta-errada") {
        return erro(
          "E-CONF",
          "Esta pasta não parece ser a vitrine. Escolha a pasta que contém o arquivo index.html."
        );
      }
      return api.estado();
    },

    escolher_pasta: function (tipo) {
      registra("escolher_pasta", [tipo]);
      if (cfg.cenario === "cancelar-seletor") return ok({ cancelado: true });
      return ok({
        cancelado: false,
        caminho:
          tipo === "site"
            ? "C:\\Users\\Usuario\\Desktop\\vitrinePI_site"
            : "C:\\Users\\Usuario\\Documents\\50 Patentes Observatório",
      });
    },

    listar: function () {
      registra("listar", []);
      if (cfg.cenario === "acervo-vazio") return ok({ patentes: [] });
      if (cfg.cenario === "erro-ao-listar") {
        return erro("E-ARQ", "Não conseguimos ler a pasta do acervo.");
      }
      return ok({ patentes: PATENTES.map(function (p) { return Object.assign({}, p); }) });
    },

    obter: function (id) {
      registra("obter", [id]);
      var p = PATENTES.filter(function (x) { return x.id === Number(id); })[0];
      if (!p) return erro("E-404", "Não encontrei a patente " + id + " no acervo.");
      return ok({
        id: p.id,
        numero: p.numero,
        oculta: p.oculta,
        temPdf: p.temPdf,
        temCapa: p.temCapa,
        areas: AREAS,
        campos: {
          titulo: p.titulo,
          categoria: p.categoria,
          secoes: {
            oQueE:
              "Ingrediente obtido pela desidratação por spray-dryer, resultando em produto em pó com alto valor nutritivo.",
            problema: "Existe demanda por ingredientes práticos com maior vida útil.",
            exemploDeUso: "Molhos, temperos, sopas desidratadas e snacks.",
            diferenciais: ["Alto teor proteico", "Preservação do sabor natural"],
            beneficio: "Agrega sabor natural a diversos produtos alimentícios.",
          },
          trl: { min: 5, max: 6, estimado: false },
        },
      });
    },

    escolher_arquivo: function (tipo) {
      registra("escolher_arquivo", [tipo]);
      if (cfg.cenario === "cancelar-seletor") return ok({ cancelado: true });
      return ok(arquivoRecebido(tipo));
    },

    receber_arquivo: function (tipo, nome) {
      registra("receber_arquivo", [tipo, nome]);
      if (cfg.cenario === "arquivo-recusado") {
        return erro(
          "E-ARQ",
          "Este arquivo não é um PDF. Confira se escolheu a ficha técnica certa — o nome terminar em .pdf não basta."
        );
      }
      var d = arquivoRecebido(tipo);
      d.nomeOriginal = nome;
      return ok(d);
    },

    ler_ficha: function (token) {
      registra("ler_ficha", [token]);
      return ok({
        numero: { valor: "BR 10 2014 030019-8", origem: "nome_arquivo" },
        categoria: { valor: "Alimentos", origem: "nome_arquivo" },
        titulo: {
          valor: "Camarão em Pó Natural para Aplicações Alimentícias",
          origem: "pdf",
        },
        secoes: {
          oQueE: {
            valor:
              "Ingrediente obtido pela desidratação de camarão por spray-dryer, resultando em produto em pó com alto valor nutritivo.",
            origem: "pdf",
          },
          problema: {
            valor: "Existe demanda por ingredientes práticos com maior vida útil.",
            origem: "pdf",
          },
          exemploDeUso: { valor: null, origem: "nao_encontrado" },
          diferenciais: {
            valor: ["Alto teor proteico", "Preservação do sabor natural"],
            origem: "pdf",
          },
          beneficio: {
            valor: "Agrega sabor natural de camarão a diversos produtos.",
            origem: "pdf",
          },
        },
        trl: { valor: { min: 5, max: 6, estimado: false }, origem: "pdf" },
        paginas: 1,
        avisos: [],
      });
    },

    ler_texto_ficha: function (texto) {
      registra("ler_texto_ficha", [texto]);
      return ok({
        numero: { valor: null, origem: "nao_encontrado" },
        categoria: { valor: null, origem: "nao_encontrado" },
        titulo: { valor: null, origem: "nao_encontrado" },
        secoes: {
          oQueE: { valor: "Texto colado pela equipe.", origem: "pdf" },
          problema: { valor: null, origem: "nao_encontrado" },
          exemploDeUso: { valor: null, origem: "nao_encontrado" },
          diferenciais: { valor: null, origem: "nao_encontrado" },
          beneficio: { valor: null, origem: "nao_encontrado" },
        },
        trl: { valor: null, origem: "nao_encontrado" },
      });
    },

    previa: function (dados) {
      registra("previa", [dados]);
      return ok({ patente: montaPrevia(dados), erros: {}, avisos: {}, valido: true });
    },

    salvar: function (dados) {
      registra("salvar", [dados]);
      if (cfg.cenario === "salvar-invalido") {
        return erro(
          "E-VALID",
          "Confira os campos destacados: alguns dados ainda precisam de ajuste.",
          {
            titulo: "O título está muito curto: 5 caracteres, e o mínimo é 10.",
            "secoes.oQueE": "O campo “O que é?” é obrigatório.",
          }
        );
      }
      if (cfg.cenario === "build-com-erro") {
        return ok({
          id: 61,
          novo: true,
          build: {
            patentes: 60,
            erros: ["[61] categoria fora do mapa: `Astrologia`."],
            avisos: [],
            ignorados: [],
            ocultas: [],
            assetsRemovidos: [],
            vitrineAtualizada: false,
          },
        });
      }
      return ok({
        id: 61,
        novo: true,
        build: {
          patentes: 61,
          erros: [],
          avisos: ["[61] sem PDF: a vitrine nao tera o botao de download."],
          ignorados: [],
          ocultas: [],
          assetsRemovidos: [],
          vitrineAtualizada: true,
        },
      });
    },

    alternar_oculta: function (id, oculta) {
      registra("alternar_oculta", [id, oculta]);
      PATENTES.forEach(function (p) {
        if (p.id === Number(id)) p.oculta = !!oculta;
      });
      return ok({ id: Number(id), oculta: !!oculta, build: buildOk() });
    },

    excluir: function (id, confirmacao) {
      registra("excluir", [id, confirmacao]);
      var p = PATENTES.filter(function (x) { return x.id === Number(id); })[0];
      if (!p || confirmacao !== p.numero) {
        return erro(
          "E-CONFIRMA",
          "Para mover esta patente para a lixeira, digite o número do pedido: " +
            (p ? p.numero : "")
        );
      }
      return ok({ id: Number(id), build: buildOk() });
    },

    rodar_build: function () {
      registra("rodar_build", []);
      if (cfg.cenario === "build-com-erro") {
        return ok({
          patentes: 60,
          erros: ["[62] patente.json invalido: campo desconhecido 'titluo'."],
          avisos: [],
          ignorados: [],
          ocultas: [],
          assetsRemovidos: [],
          vitrineAtualizada: false,
        });
      }
      return ok(buildOk());
    },

    historico: function (pagina) {
      registra("historico", [pagina]);
      var linhas = [
        {
          ts: "2026-09-30T14:02:11-03:00",
          usuario: "usuario.windows",
          maquina: "UFCINOVA-01",
          acao: "criar",
          id: 61,
          numero: "BR 10 2026 099999-9",
          resumo: "categoria, secoes, titulo",
          resultado: "ok",
        },
        {
          ts: "2026-09-30T11:40:02-03:00",
          usuario: "usuario.windows",
          maquina: "UFCINOVA-01",
          acao: "ocultar",
          id: 29,
          resultado: "ok",
        },
        {
          ts: "2026-09-29T17:15:44-03:00",
          usuario: "usuario.windows",
          maquina: "UFCINOVA-01",
          acao: "rodar_build",
          resumo: "60 patentes",
          resultado: "erro",
        },
      ];
      return ok({
        linhas: linhas,
        pagina: 1,
        paginas: 1,
        total: linhas.length,
        backups: [
          {
            id: "2026-09-30_140211_salvar_61",
            acao: "salvar",
            patenteId: 61,
            quando: "2026-09-30T14:02:11-03:00",
            usuario: "usuario.windows",
            descricao: "salvar em patente 61",
          },
        ],
      });
    },

    restaurar: function (id, confirmacao) {
      registra("restaurar", [id, confirmacao]);
      if (String(confirmacao).toUpperCase() !== "RESTAURAR") {
        return erro(
          "E-CONFIRMA",
          "Para restaurar este ponto, digite RESTAURAR para confirmar."
        );
      }
      return ok({ backup: id, build: buildOk() });
    },

    gerar_pacote: function () {
      registra("gerar_pacote", []);
      if (cfg.cenario === "pacote-bloqueado") {
        return ok({
          gerado: false,
          checagens: [
            { chave: "build", titulo: "A vitrine foi gerada sem erros", ok: false,
              detalhe: "O último build terminou com 1 erro." },
            { chave: "dados", titulo: "60 patentes na vitrine", ok: true, detalhe: "" },
            { chave: "arquivos", titulo: "Todos os arquivos da vitrine estão presentes",
              ok: true, detalhe: "" },
            { chave: "orfas", titulo: "Nenhuma pasta de patente fora da vitrine",
              ok: false,
              detalhe: "1 pasta sobrando em assets/patentes: 29-metodo-de-pigmentacao." },
          ],
        });
      }
      return ok({
        gerado: true,
        checagens: [
          { chave: "build", titulo: "A vitrine foi gerada sem erros", ok: true, detalhe: "" },
          { chave: "dados", titulo: "60 patentes na vitrine", ok: true, detalhe: "" },
          { chave: "arquivos", titulo: "Todos os arquivos da vitrine estão presentes",
            ok: true, detalhe: "" },
          { chave: "orfas", titulo: "Nenhuma pasta de patente fora da vitrine",
            ok: true, detalhe: "" },
        ],
        nome: "vitrine-patentes_2026-09-30_1402.zip",
        sha256: "3f786850e387550fdab836ed7e6dc881de23001b4e1f9a9c8b2f4e0d3c5a7b91",
        arquivos: 312,
        patentes: 60,
        tamanho: "128.4 MB",
        proximoPasso: "Envie o .zip para a STI pelo e-mail de sempre.",
      });
    },

    abrir_pasta: function (tipo) {
      registra("abrir_pasta", [tipo]);
      return ok({ caminho: "C:\\..." });
    },

    abrir_link: function (chave) {
      registra("abrir_link", [chave]);
      return ok({ url: "https://ufcinova.sitios.sti.ufc.br" });
    },

    ver_site_local: function () {
      registra("ver_site_local", []);
      return ok({ url: "http://127.0.0.1:52341/index.html" });
    },
  };

  /* ---- auxiliares ---- */

  /* Quadrado roxo de 1px, ampliado pelo CSS: serve de capa sem precisar de
     arquivo binario no repositorio dos testes. */
  var PIXEL_ROXO =
    "data:image/gif;base64,R0lGODlhAQABAPAAAFwGnQAAACH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==";

  function arquivoRecebido(tipo) {
    if (tipo === "pdf") {
      return { token: "t-pdf-" + Date.now(), tipo: "pdf", tamanho: 3_407_872, avisos: [] };
    }
    return {
      token: "t-capa-" + Date.now(),
      tipo: "capa",
      tamanho: 2_174_976,
      avisos: [],
      largura: cfg.cenario === "capa-retrato" ? 600 : 900,
      altura: cfg.cenario === "capa-retrato" ? 900 : 900,
      quadrada: cfg.cenario !== "capa-retrato",
      precisaRecorte: cfg.cenario === "capa-retrato",
    };
  }

  function buildOk() {
    return {
      patentes: 60,
      erros: [],
      avisos: [],
      ignorados: [],
      ocultas: [],
      assetsRemovidos: [],
      vitrineAtualizada: true,
    };
  }

  function montaPrevia(dados) {
    dados = dados || {};
    var secoes = dados.secoes || {};
    var trl = dados.trl
      ? {
          min: dados.trl.min,
          max: dados.trl.max,
          estimado: !!dados.trl.estimado,
          texto:
            "TRL " +
            dados.trl.min +
            (dados.trl.max !== dados.trl.min ? "–" + dados.trl.max : "") +
            (dados.trl.estimado ? " (estimado)" : ""),
        }
      : null;
    var oQueE = secoes.oQueE || "";
    return {
      id: 61,
      slug: "61-previa",
      numero: dados.numero || "BR 10 2026 099999-9",
      ano: 2026,
      tipo: { sigla: "PI", nome: "Patente de Invenção" },
      categoria: dados.categoria || "Alimentos",
      titulo: dados.titulo || "",
      resumo: oQueE.length > 160 ? oQueE.slice(0, 157) + "…" : oQueE,
      secoes: {
        oQueE: secoes.oQueE || null,
        problema: secoes.problema || null,
        exemploDeUso: secoes.exemploDeUso || null,
        diferenciais: secoes.diferenciais || null,
        beneficio: secoes.beneficio || null,
      },
      trl: trl,
      imagens: {
        capa400: PIXEL_ROXO,
        capa800: PIXEL_ROXO,
        ficha600: cfg.cenario === "sem-pdf" ? null : PIXEL_ROXO,
        ficha1620: cfg.cenario === "sem-pdf" ? null : PIXEL_ROXO,
        dimensoesCapa: [800, 800],
      },
      pdf: cfg.cenario === "sem-pdf" ? null : "#",
    };
  }

  window.pywebview = { api: api };
  cfg.api = api;
  cfg.PATENTES = PATENTES;
  cfg.AREAS = AREAS;
})();
