/* ============================================================
   tela-editar.js — T2: Nova patente / Editar (PRD 7.5, Fase 5).

   Uma unica tela cuida dos dois casos: "nova" (sem id) e "editar/:id".
   O formulario e montado UMA vez (criaEsqueleto); dali em diante so o
   conteudo de campos, badges, erros e a coluna de previa sao atualizados
   no lugar -- nunca o form inteiro de novo, para nao perder o foco nem a
   posicao do cursor enquanto a pessoa digita.

   Depende de: site/js/ui.js (UI), site/js/render.js (RENDER),
   api-cliente.js (API), painel.js (window.PAINEL).
   ============================================================ */
(function () {
  "use strict";

  var U = window.UI;
  var R = window.RENDER;
  var API = window.API;

  /* ---------------------------------------------------------
     Limites dos campos (espelham vitrine_core.acervo.LIMITES --
     PRD 8). A validacao que vale de verdade e a do Python; isto aqui
     e so para o retorno imediato ao digitar e ao sair do campo.
     --------------------------------------------------------- */
  var LIMITES = {
    titulo: [10, 160],
    "secoes.oQueE": [40, 900],
    "secoes.problema": [0, 900],
    "secoes.exemploDeUso": [0, 900],
    "secoes.beneficio": [0, 900],
  };
  var DIFERENCIAL_LIMITES = [3, 200];
  var DIFERENCIAIS_MAX = 8;

  var NUMERO_RE = /BR\s*(10|20)\s*(\d{4})\s*(\d{6})[\s-]*(\d)/i;

  var CAMPOS_TEXTO = [
    { chave: "titulo", rotulo: "O título", linhas: 2, obrigatorio: true },
    { chave: "secoes.oQueE", rotulo: "O campo “O que é?”", linhas: 3, obrigatorio: true },
    { chave: "secoes.problema", rotulo: "O campo “Problema que resolve”", linhas: 2, obrigatorio: false },
    { chave: "secoes.exemploDeUso", rotulo: "O campo “Exemplo de uso”", linhas: 2, obrigatorio: false },
    { chave: "secoes.beneficio", rotulo: "O campo “Benefício principal”", linhas: 2, obrigatorio: false },
  ];

  var ETAPAS = [
    "Validando",
    "Salvando no acervo",
    "Otimizando imagens",
    "Gerando a ficha",
    "Atualizando a vitrine",
  ];

  /* ---------------------------------------------------------
     Caminho com ponto: "secoes.oQueE" <-> dados.secoes.oQueE
     --------------------------------------------------------- */
  function leCaminho(obj, caminho) {
    var partes = caminho.split(".");
    var alvo = obj;
    for (var i = 0; i < partes.length; i++) {
      if (alvo == null) return undefined;
      alvo = alvo[partes[i]];
    }
    return alvo;
  }

  function escreveCaminho(obj, caminho, valor) {
    var partes = caminho.split(".");
    var alvo = obj;
    for (var i = 0; i < partes.length - 1; i++) {
      if (alvo[partes[i]] == null) alvo[partes[i]] = {};
      alvo = alvo[partes[i]];
    }
    alvo[partes[partes.length - 1]] = valor;
  }

  function idDoCampo(chave) {
    return "campo-" + chave.replace(/\./g, "-");
  }

  /* ---------------------------------------------------------
     Estado em memoria da tela (um por montagem)
     --------------------------------------------------------- */
  function criaContexto(idEditando) {
    return {
      idEditando: idEditando,
      nova: idEditando == null,
      areas: [],
      dados: {
        numero: "",
        categoria: "",
        titulo: "",
        secoes: { oQueE: "", problema: "", exemploDeUso: "", diferenciais: [], beneficio: "" },
        trl: null,
        oculta: false,
      },
      origens: {}, // chave -> "pdf" | "nome_arquivo" | "nao_encontrado"
      autopreenchido: false,
      confirmado: false,
      tokenPdf: null,
      arquivoPdf: null, // {nome, tamanho, paginas, avisos}
      temPdfAtual: false,
      tokenCapa: null,
      arquivoCapa: null, // {tamanho, largura, altura, quadrada}
      temCapaAtual: false,
      recorte: null,
      els: {}, // chave -> {input, erro, contador, campo}
      sujo: false,
      previaAba: "card",
      carregando: true,
    };
  }

  /* ---------------------------------------------------------
     Validacao local (espelha PRD 8; a do Python e a que vale)
     --------------------------------------------------------- */
  function validaCampoTexto(ctx, chave) {
    var def = CAMPOS_TEXTO.filter(function (c) { return c.chave === chave; })[0];
    if (!def) return null;
    var limites = LIMITES[chave];
    var valor = String(leCaminho(ctx.dados, chave) || "").trim();
    if (!valor) {
      return def.obrigatorio ? def.rotulo + " é obrigatório." : null;
    }
    if (valor.length < Math.max(limites[0], 1)) {
      return (
        def.rotulo + " está muito curto: " + valor.length + " caracteres, e o mínimo é " +
        limites[0] + "."
      );
    }
    if (valor.length > limites[1]) {
      return (
        def.rotulo + " está muito longo: " + valor.length + " caracteres, e o máximo é " +
        limites[1] + "."
      );
    }
    return null;
  }

  function normalizaNumero(bruto) {
    var m = NUMERO_RE.exec(String(bruto || ""));
    if (!m) return null;
    return "BR " + m[1] + " " + m[2] + " " + m[3] + "-" + m[4];
  }

  /** Roda toda a validacao local. Devolve {erros, primeiraChave}. */
  function validaTudo(ctx) {
    var erros = {};
    var primeira = null;
    function marca(chave, msg) {
      if (!msg) return;
      erros[chave] = msg;
      if (!primeira) primeira = chave;
    }

    if (ctx.nova) {
      var numero = normalizaNumero(ctx.dados.numero);
      if (!numero) {
        marca("numero", "Informe o número do pedido no formato BR 10 2025 012345-6.");
      } else {
        ctx.dados.numero = numero;
      }
    }
    if (!ctx.dados.categoria) marca("categoria", "Escolha a área tecnológica.");

    CAMPOS_TEXTO.forEach(function (def) {
      marca(def.chave, validaCampoTexto(ctx, def.chave));
    });

    var diferenciais = ctx.dados.secoes.diferenciais || [];
    diferenciais.forEach(function (d, i) {
      var v = String(d || "").trim();
      if (!v) return;
      if (v.length < DIFERENCIAL_LIMITES[0] || v.length > DIFERENCIAL_LIMITES[1]) {
        marca(
          "secoes.diferenciais." + i,
          "O diferencial " + (i + 1) + " precisa ter entre " + DIFERENCIAL_LIMITES[0] +
            " e " + DIFERENCIAL_LIMITES[1] + " caracteres."
        );
      }
    });

    var temCapa = !!ctx.tokenCapa || ctx.temCapaAtual;
    if (ctx.nova && !temCapa) marca("capa", "Escolha a imagem de capa: ela é obrigatória.");

    if (ctx.autopreenchido && !ctx.confirmado) {
      marca(
        "confirmar",
        "Confirme que conferiu as informações preenchidas automaticamente."
      );
    }

    return { erros: erros, primeira: primeira };
  }

  /* ---------------------------------------------------------
     Montagem de um campo de texto (titulo / secoes.*)
     --------------------------------------------------------- */
  function montaCampoTexto(ctx, def) {
    var id = idDoCampo(def.chave);
    var idErro = id + "-erro";
    var idAjuda = id + "-ajuda";
    var limites = LIMITES[def.chave];

    var campo = document.createElement("div");
    campo.className = "campo";
    campo.setAttribute("data-campo-wrap", def.chave);

    var rotulo = document.createElement("label");
    rotulo.className = "campo__rotulo";
    rotulo.setAttribute("for", id);
    var rotuloTexto = document.createElement("span");
    rotuloTexto.textContent = rotuloCurto(def.chave);
    if (def.obrigatorio) {
      var ob = document.createElement("span");
      ob.className = "campo__obrigatorio";
      ob.setAttribute("aria-hidden", "true");
      ob.textContent = " *";
      rotuloTexto.appendChild(ob);
      var sr = document.createElement("span");
      sr.className = "visualmente-oculto";
      sr.textContent = " (obrigatório)";
      rotuloTexto.appendChild(sr);
    }
    rotulo.appendChild(rotuloTexto);

    var fonte = document.createElement("span");
    fonte.className = "campo__fonte";
    fonte.hidden = true;
    rotulo.appendChild(fonte);

    var contador = document.createElement("span");
    contador.className = "campo__contador";
    if (limites[1]) contador.textContent = "0/" + limites[1];
    else contador.hidden = true;
    rotulo.appendChild(contador);

    campo.appendChild(rotulo);

    var textarea = document.createElement("textarea");
    textarea.id = id;
    textarea.rows = def.linhas;
    textarea.setAttribute("data-campo", def.chave);
    textarea.setAttribute("aria-describedby", idAjuda + " " + idErro);
    if (def.obrigatorio) textarea.required = true;
    campo.appendChild(textarea);

    var ajuda = document.createElement("p");
    ajuda.className = "campo__ajuda";
    ajuda.id = idAjuda;
    ajuda.textContent =
      def.chave === "titulo" ? "Como vai aparecer no card e na página." : "";
    if (!ajuda.textContent) ajuda.hidden = true;
    campo.appendChild(ajuda);

    var conversor = null;
    if (def.chave === "titulo") {
      conversor = document.createElement("button");
      conversor.type = "button";
      conversor.className = "botao botao--terciario";
      conversor.hidden = true;
      conversor.setAttribute("data-converter-titulo", "");
      conversor.textContent = "Converter para caixa de frase";
      campo.appendChild(conversor);
    }

    var erro = document.createElement("p");
    erro.className = "campo__erro";
    erro.id = idErro;
    erro.hidden = true;
    campo.appendChild(erro);

    ctx.els[def.chave] = {
      campo: campo,
      input: textarea,
      erro: erro,
      contador: contador,
      fonte: fonte,
      ajuda: ajuda,
    };

    return campo;
  }

  /* Rotulos curtos para o <label> (sem o prefixo "O campo..." usado nas
     mensagens de erro, que seguem o texto do Python ao pe da letra). */
  function rotuloCurto(chave) {
    return (
      {
        titulo: "Título",
        "secoes.oQueE": "O que é?",
        "secoes.problema": "Problema que resolve",
        "secoes.exemploDeUso": "Exemplo de uso",
        "secoes.beneficio": "Benefício principal",
      }[chave] || chave
    );
  }

  /* ---------------------------------------------------------
     Origem do preenchimento automatico (PRD 7.4)
     --------------------------------------------------------- */
  function aplicaOrigem(ctx, chave, origem) {
    var el = ctx.els[chave];
    if (!el) return;
    ctx.origens[chave] = origem;
    el.campo.classList.remove("is-do-pdf", "is-nao-encontrado");
    if (origem === "pdf" || origem === "nome_arquivo") {
      el.campo.classList.add("is-do-pdf");
      el.fonte.hidden = false;
      el.fonte.textContent = origem === "pdf" ? "✦ do PDF" : "✦ do nome do arquivo";
    } else if (origem === "nao_encontrado") {
      el.campo.classList.add("is-nao-encontrado");
      el.fonte.hidden = true;
      el.ajuda.hidden = false;
      el.ajuda.textContent = "Não encontramos no PDF. Preencha manualmente.";
    } else {
      el.fonte.hidden = true;
    }
  }

  function limpaOrigem(ctx, chave) {
    var el = ctx.els[chave];
    if (!el) return;
    delete ctx.origens[chave];
    el.campo.classList.remove("is-do-pdf", "is-nao-encontrado");
    el.fonte.hidden = true;
    if (chave === "titulo") el.ajuda.hidden = false;
    else if (el.ajuda.textContent === "Não encontramos no PDF. Preencha manualmente.") {
      el.ajuda.hidden = true;
      el.ajuda.textContent = "";
    }
  }

  function temAutopreenchimento(ctx) {
    return Object.keys(ctx.origens).some(function (k) {
      return ctx.origens[k] === "pdf" || ctx.origens[k] === "nome_arquivo";
    });
  }

  /* ---------------------------------------------------------
     Erros de campo (locais ou vindos do Python)
     --------------------------------------------------------- */
  function marcaErroCampo(ctx, chave, mensagem) {
    var el = ctx.els[chave];
    if (!el) return;
    el.input.setAttribute("aria-invalid", "true");
    el.erro.hidden = false;
    el.erro.innerHTML = window.PAINEL.icone("alerta") + "<span>" + U.esc(mensagem) + "</span>";
  }

  function limpaErroCampo(ctx, chave) {
    var el = ctx.els[chave];
    if (!el) return;
    el.input.removeAttribute("aria-invalid");
    el.erro.hidden = true;
    el.erro.textContent = "";
  }

  function limpaTodosOsErros(ctx) {
    Object.keys(ctx.els).forEach(function (chave) {
      limpaErroCampo(ctx, chave);
    });
    if (ctx.elNumeroErro) {
      ctx.elNumero.removeAttribute("aria-invalid");
      ctx.elNumeroErro.hidden = true;
    }
    if (ctx.elCategoriaErro) {
      ctx.elCategoria.removeAttribute("aria-invalid");
      ctx.elCategoriaErro.hidden = true;
    }
  }

  /* ---------------------------------------------------------
     Resumo de erros (so aparece ao tentar salvar — PRD 7.5)
     --------------------------------------------------------- */
  function ROTULOS_RESUMO() {
    var mapa = {
      numero: "Número do pedido",
      categoria: "Área tecnológica",
      capa: "Imagem de capa",
      confirmar: "Conferência dos dados preenchidos",
    };
    CAMPOS_TEXTO.forEach(function (d) {
      mapa[d.chave] = rotuloCurto(d.chave);
    });
    return mapa;
  }

  function mostraResumoErros(ctx, erros) {
    var rotulos = ROTULOS_RESUMO();
    ctx.elResumo.innerHTML = "";
    var chaves = Object.keys(erros);
    if (!chaves.length) {
      ctx.elResumo.hidden = true;
      return;
    }
    ctx.elResumo.hidden = false;
    var titulo = document.createElement("h3");
    titulo.innerHTML =
      window.PAINEL.icone("alerta") +
      "<span>Confira " +
      chaves.length +
      (chaves.length === 1 ? " campo antes de salvar" : " campos antes de salvar") +
      "</span>";
    ctx.elResumo.appendChild(titulo);

    var lista = document.createElement("ul");
    chaves.forEach(function (chave) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      var alvoId = chave === "numero" ? "campo-numero" : chave === "categoria" ? "campo-categoria" : idDoCampo(chave);
      a.href = "#" + alvoId;
      var rotuloBase = rotulos[chave.split(".").slice(0, 2).join(".")] || rotulos[chave] || chave;
      a.textContent = rotuloBase + ": " + erros[chave];
      a.addEventListener("click", function (e) {
        e.preventDefault();
        var alvo =
          document.getElementById(alvoId) ||
          (/^secoes\.diferenciais\.\d+$/.test(chave)
            ? document.querySelector('[data-dif-idx="' + chave.split(".")[2] + '"]')
            : null) ||
          (chave === "capa" ? ctx.elZonaCapa.querySelector("button, input") : null) ||
          (chave === "confirmar" ? ctx.elConfirmar : null);
        if (alvo) {
          alvo.scrollIntoView({ behavior: U.reduzido.matches ? "auto" : "smooth", block: "center" });
          alvo.focus();
        }
      });
      li.appendChild(a);
      lista.appendChild(li);
    });
    ctx.elResumo.appendChild(lista);
  }

  /* ---------------------------------------------------------
     Diferenciais (editor de lista, PRD 7.4)
     --------------------------------------------------------- */
  function pintaDiferenciais(ctx) {
    var raiz = ctx.elDiferenciais;
    raiz.innerHTML = "";
    var itens = ctx.dados.secoes.diferenciais || [];
    itens.forEach(function (valor, i) {
      var linha = document.createElement("div");
      linha.className = "diferencial";

      var input = document.createElement("input");
      input.type = "text";
      input.value = valor;
      input.setAttribute("aria-label", "Diferencial " + (i + 1));
      input.setAttribute("data-dif-idx", String(i));
      linha.appendChild(input);

      var botoes = document.createElement("div");
      botoes.className = "diferencial__botoes";

      var subir = botaoIcone("chevron-up", "Mover diferencial " + (i + 1) + " para cima");
      subir.setAttribute("data-dif-acao", "subir");
      subir.setAttribute("data-dif-idx", String(i));
      subir.disabled = i === 0;
      botoes.appendChild(subir);

      var descer = botaoIcone("chevron-up", "Mover diferencial " + (i + 1) + " para baixo");
      descer.querySelector("span").className = "girado-180";
      descer.setAttribute("data-dif-acao", "descer");
      descer.setAttribute("data-dif-idx", String(i));
      descer.disabled = i === itens.length - 1;
      botoes.appendChild(descer);

      var remover = document.createElement("button");
      remover.type = "button";
      remover.className = "botao-icone botao-icone--remover";
      remover.setAttribute("aria-label", "Remover diferencial " + (i + 1));
      remover.setAttribute("data-dif-acao", "remover");
      remover.setAttribute("data-dif-idx", String(i));
      remover.innerHTML = '<span data-icone="x"></span>';
      botoes.appendChild(remover);

      linha.appendChild(botoes);
      raiz.appendChild(linha);
    });
    U.hidrataIcones(raiz);
    ctx.elDiferenciaisAdicionar.disabled = itens.length >= DIFERENCIAIS_MAX;
  }

  /* botao-icone com um span[data-icone] -- so hidrataIcones troca, entao o
     proprio <button> sobrevive (PRD: "O icone vai num <span> DENTRO do
     botao"). */
  function botaoIcone(nomeIcone, rotulo) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "botao-icone";
    b.setAttribute("aria-label", rotulo);
    b.innerHTML = '<span data-icone="' + nomeIcone + '"></span>';
    return b;
  }

  /* ---------------------------------------------------------
     TRL (PRD 7.4)
     --------------------------------------------------------- */
  function pintaTrl(ctx) {
    var trl = ctx.dados.trl;
    var raiz = ctx.elTrl;
    raiz.innerHTML = "";

    var barra = document.createElement("div");
    barra.className = "trl trl-editor";
    var pista = document.createElement("div");
    pista.className = "trl__barra";
    pista.setAttribute("role", "group");
    pista.setAttribute("aria-label", "Faixa de maturidade tecnológica, de 1 a 9");
    for (var n = 1; n <= 9; n++) {
      var seg = document.createElement("button");
      seg.type = "button";
      seg.className = "trl-seg" + (trl && n >= trl.min && n <= trl.max ? " is-ativo" : "");
      seg.setAttribute("data-trl-seg", String(n));
      seg.setAttribute("aria-pressed", String(!!(trl && n >= trl.min && n <= trl.max)));
      seg.setAttribute("aria-label", "TRL " + n + (trl && n >= trl.min && n <= trl.max ? ", selecionado" : ""));
      pista.appendChild(seg);
    }
    barra.appendChild(pista);
    var rotulo = document.createElement("p");
    rotulo.className = "trl__rotulo";
    rotulo.textContent = trl
      ? "Maturidade tecnológica: TRL " + trl.min + (trl.max !== trl.min ? "–" + trl.max : "") +
        (trl.estimado ? " (estimado)" : "")
      : "Maturidade tecnológica: não informada.";
    barra.appendChild(rotulo);
    raiz.appendChild(barra);

    var alt = document.createElement("div");
    alt.className = "trl-editor__alternativa";

    function selectTrl(rotuloTxt, dataAttr, valor) {
      var campo = document.createElement("div");
      campo.className = "campo";
      var lb = document.createElement("label");
      lb.className = "campo__rotulo";
      var id = "trl-" + dataAttr;
      lb.setAttribute("for", id);
      lb.innerHTML = "<span>" + rotuloTxt + "</span>";
      campo.appendChild(lb);
      var sel = document.createElement("select");
      sel.id = id;
      sel.setAttribute("data-trl-select", dataAttr);
      for (var n = 1; n <= 9; n++) {
        var op = document.createElement("option");
        op.value = String(n);
        op.textContent = String(n);
        if (valor === n) op.selected = true;
        sel.appendChild(op);
      }
      campo.appendChild(sel);
      return campo;
    }

    alt.appendChild(selectTrl("Mínimo", "min", trl ? trl.min : 1));
    alt.appendChild(selectTrl("Máximo", "max", trl ? trl.max : 1));

    var campoEst = document.createElement("div");
    campoEst.className = "campo";
    var lbEst = document.createElement("label");
    lbEst.className = "campo__rotulo";
    lbEst.setAttribute("for", "trl-estimado");
    lbEst.innerHTML = "<span>Estimado</span>";
    campoEst.appendChild(lbEst);
    var chk = document.createElement("input");
    chk.type = "checkbox";
    chk.id = "trl-estimado";
    chk.setAttribute("data-trl-estimado", "");
    chk.checked = !!(trl && trl.estimado);
    campoEst.appendChild(chk);
    alt.appendChild(campoEst);

    if (trl) {
      var limpar = document.createElement("button");
      limpar.type = "button";
      limpar.className = "botao botao--terciario";
      limpar.setAttribute("data-trl-limpar", "");
      limpar.textContent = "Remover TRL";
      alt.appendChild(limpar);
    }

    barra.appendChild(alt);
  }

  function defineTrl(ctx, min, max, estimado) {
    if (min > max) { var tmp = min; min = max; max = tmp; }
    min = Math.max(1, Math.min(9, min));
    max = Math.max(1, Math.min(9, max));
    ctx.dados.trl = { min: min, max: max, estimado: !!estimado };
    pintaTrl(ctx);
    marcaSujo(ctx);
    agendaPrevia(ctx);
  }

  /* ---------------------------------------------------------
     Zona de soltar — PDF e capa (PRD 7.4, 9.1, 9.2)
     --------------------------------------------------------- */
  function lerComoBase64(file) {
    return new Promise(function (resolve, reject) {
      var r = new FileReader();
      r.onload = function () {
        var s = String(r.result || "");
        var i = s.indexOf(",");
        resolve(i >= 0 ? s.slice(i + 1) : s);
      };
      r.onerror = function () { reject(new Error("Não foi possível ler o arquivo.")); };
      r.readAsDataURL(file);
    });
  }

  function aplicaAvisoFicha(ctx, avisos) {
    if (!avisos || !avisos.length) return;
    window.PAINEL.avisa(avisos.join(" "), { tipo: "ok" });
  }

  function preencheComFicha(ctx, campos) {
    ctx.autopreenchido = true;
    if (ctx.nova && campos.numero && campos.numero.valor) {
      ctx.dados.numero = campos.numero.valor;
      ctx.elNumero.value = campos.numero.valor;
      atualizaTipoAno(ctx);
    }
    if (campos.categoria && campos.categoria.valor && ctx.areas.indexOf(campos.categoria.valor) > -1) {
      ctx.dados.categoria = campos.categoria.valor;
      ctx.elCategoria.value = campos.categoria.valor;
    }
    if (campos.titulo) {
      ctx.dados.titulo = campos.titulo.valor || "";
      ctx.els.titulo.input.value = ctx.dados.titulo;
      aplicaOrigem(ctx, "titulo", campos.titulo.origem);
      atualizaContador(ctx, "titulo");
    }
    ["oQueE", "problema", "exemploDeUso", "beneficio"].forEach(function (campo) {
      var info = campos.secoes && campos.secoes[campo];
      if (!info) return;
      var chave = "secoes." + campo;
      ctx.dados.secoes[campo] = info.valor || "";
      ctx.els[chave].input.value = ctx.dados.secoes[campo];
      aplicaOrigem(ctx, chave, info.origem);
      atualizaContador(ctx, chave);
    });
    if (campos.secoes && campos.secoes.diferenciais && campos.secoes.diferenciais.valor) {
      ctx.dados.secoes.diferenciais = campos.secoes.diferenciais.valor.slice(0, DIFERENCIAIS_MAX);
      pintaDiferenciais(ctx);
    }
    if (campos.trl && campos.trl.valor) {
      ctx.dados.trl = {
        min: campos.trl.valor.min,
        max: campos.trl.valor.max,
        estimado: !!campos.trl.valor.estimado,
      };
      pintaTrl(ctx);
    }

    // o fundo pisca em sequencia, mostrando o que foi preenchido (PRD 7.6).
    // O atraso entre campos vem de um `setTimeout` por campo, e nao da
    // variavel CSS `--atraso` (usada no site): aqui e so para nao duplicar a
    // logica de agendamento em CSS quando o JS ja teria que orquestrar a
    // remocao da classe de qualquer forma.
    Object.keys(ctx.origens).forEach(function (chave, i) {
      var el = ctx.els[chave];
      if (!el) return;
      setTimeout(function () {
        el.campo.classList.add("is-piscando");
        setTimeout(function () {
          el.campo.classList.remove("is-piscando");
        }, 450);
      }, Math.min(i * 40, 400));
    });

    atualizaConfirmacao(ctx);
    aplicaAvisoFicha(ctx, campos.avisos);
    marcaSujo(ctx);
    agendaPrevia(ctx);
  }

  function montaDropzone(tipo, rotuloPrincipal) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "dropzone";
    btn.setAttribute("data-dropzone", tipo);
    btn.innerHTML =
      '<span class="dropzone__icone" data-icone="file-text"></span>' +
      '<span class="dropzone__texto">' + rotuloPrincipal + "</span>";
    U.hidrataIcones(btn);
    return btn;
  }

  function montaArquivoCard(tipo) {
    var div = document.createElement("div");
    div.className = "arquivo";
    div.setAttribute("data-arquivo-card", tipo);
    div.innerHTML =
      '<div class="arquivo__mini"></div>' +
      '<div class="arquivo__info">' +
      '<p class="arquivo__nome" data-arquivo-nome></p>' +
      '<p class="arquivo__meta" data-arquivo-meta></p>' +
      "</div>" +
      '<div class="arquivo__acoes">' +
      '<button class="botao botao--terciario" type="button" data-arquivo-trocar="' + tipo + '">Trocar</button>' +
      '<button class="botao-icone botao-icone--remover" type="button" data-arquivo-remover="' + tipo +
      '" aria-label="Remover arquivo"><span data-icone="x"></span></button>' +
      "</div>";
    return div;
  }

  function tamanhoLegivel(bytes) {
    if (!bytes) return "0 KB";
    var mb = bytes / (1024 * 1024);
    return mb >= 1 ? mb.toFixed(1).replace(".", ",") + " MB" : Math.round(bytes / 1024) + " KB";
  }

  function mostraBarraLeitura(container, texto) {
    container.innerHTML =
      '<div class="painel-caixa"><div class="barra"></div>' +
      '<p class="campo__ajuda campo__ajuda--espaco" data-texto-barra></p></div>';
    container.querySelector("[data-texto-barra]").textContent = texto;
  }

  /* ---- PDF ---- */
  function mostraDropzonePdf(ctx) {
    ctx.elZonaPdf.innerHTML = "";
    ctx.elZonaPdf.appendChild(
      montaDropzone(
        "pdf",
        "<strong>Arraste a ficha em PDF aqui</strong>, cole com <kbd>Ctrl</kbd>+<kbd>V</kbd> " +
          "ou clique para escolher o arquivo"
      )
    );
  }

  function mostraArquivoPdf(ctx) {
    var card = montaArquivoCard("pdf");
    ctx.elZonaPdf.innerHTML = "";
    ctx.elZonaPdf.appendChild(card);
    var info = ctx.arquivoPdf;
    card.querySelector("[data-arquivo-nome]").textContent = info.nome || "Ficha técnica (PDF)";
    var partes = [];
    if (info.tamanho) partes.push(tamanhoLegivel(info.tamanho));
    if (info.paginas) partes.push(info.paginas + (info.paginas === 1 ? " página" : " páginas"));
    card.querySelector("[data-arquivo-meta]").textContent =
      partes.length ? partes.join(" · ") : "Envie um novo arquivo para trocar.";
    U.hidrataIcones(card);
  }

  function processaPdf(ctx, promessaArquivo) {
    mostraBarraLeitura(ctx.elZonaPdf, "Lendo a ficha…");
    return promessaArquivo
      .then(function (resumo) {
        ctx.tokenPdf = resumo.token;
        ctx.arquivoPdf = { nome: resumo.nomeOriginal || "Ficha técnica (PDF)", tamanho: resumo.tamanho };
        return API.ler_ficha(resumo.token);
      })
      .then(function (campos) {
        ctx.arquivoPdf.paginas = campos.paginas;
        mostraArquivoPdf(ctx);
        preencheComFicha(ctx, campos);
      })
      .catch(function (e) {
        mostraDropzonePdf(ctx);
        if (!e.semAviso) window.PAINEL.avisa(e.mensagem || e.message || "Algo deu errado.", { tipo: "erro" });
      });
  }

  /* ---- capa ---- */
  function mostraDropzoneCapa(ctx) {
    ctx.elZonaCapa.innerHTML = "";
    ctx.elZonaCapa.appendChild(
      montaDropzone(
        "capa",
        "<strong>Arraste a imagem aqui</strong>, cole com <kbd>Ctrl</kbd>+<kbd>V</kbd> " +
          "ou clique para escolher o arquivo"
      )
    );
  }

  function mostraArquivoCapa(ctx) {
    var card = montaArquivoCard("capa");
    ctx.elZonaCapa.innerHTML = "";
    ctx.elZonaCapa.appendChild(card);
    var info = ctx.arquivoCapa;
    card.querySelector("[data-arquivo-nome]").textContent = "Imagem de capa";
    var meta = tamanhoLegivel(info.tamanho) + " · " + info.largura + "×" + info.altura + " px";
    card.querySelector("[data-arquivo-meta]").textContent = meta;
    U.hidrataIcones(card);
  }

  function processaCapa(ctx, promessaArquivo) {
    mostraBarraLeitura(ctx.elZonaCapa, "Conferindo a imagem…");
    return promessaArquivo
      .then(function (resumo) {
        ctx.tokenCapa = resumo.token;
        ctx.arquivoCapa = resumo;
        ctx.recorte = null;
        limpaErroCampo(ctx, "capa");
        if (resumo.precisaRecorte) {
          abreRecorte(ctx);
        } else {
          mostraArquivoCapa(ctx);
        }
        if (resumo.largura < 800 || resumo.altura < 800) {
          window.PAINEL.avisa("A capa pode ficar borrada em telas de alta resolução.");
        }
        marcaSujo(ctx);
        agendaPrevia(ctx);
      })
      .catch(function (e) {
        mostraDropzoneCapa(ctx);
        if (!e.semAviso) window.PAINEL.avisa(e.mensagem || e.message || "Algo deu errado.", { tipo: "erro" });
      });
  }

  /* ---------------------------------------------------------
     Recorte 1:1 (PRD 7.4) — modal com moldura arrastavel/redimensionavel
     --------------------------------------------------------- */
  function abreRecorte(ctx) {
    var dlg = ctx.elRecorteDlg;
    var img = dlg.querySelector(".recorte img");
    var moldura = dlg.querySelector(".recorte__moldura");
    var area = dlg.querySelector(".recorte");

    // a capa recem recebida nao tem URL local: usamos a previa (data: URL)
    // para mostrar a imagem real dentro do recorte.
    API.previa({ categoria: ctx.dados.categoria || ctx.areas[0] || "" }, ctx.tokenCapa)
      .then(function (r) {
        img.src = r.patente.imagens.capa800;
      })
      .catch(function () {});

    var estadoRecorte = { x: 0.1, y: 0.1, lado: 0.8 }; // fracoes da imagem exibida

    function aplicaMoldura() {
      var r = img.getBoundingClientRect();
      var base = area.getBoundingClientRect();
      moldura.style.left = r.left - base.left + estadoRecorte.x * r.width + "px";
      moldura.style.top = r.top - base.top + estadoRecorte.y * r.height + "px";
      moldura.style.width = estadoRecorte.lado * r.width + "px";
      moldura.style.height = estadoRecorte.lado * r.height + "px";
    }

    img.onload = aplicaMoldura;
    window.addEventListener("resize", aplicaMoldura);

    function arrasta(e, mover) {
      e.preventDefault();
      var r = img.getBoundingClientRect();
      function aoMover(ev) {
        var px = (ev.clientX - r.left) / r.width;
        var py = (ev.clientY - r.top) / r.height;
        mover(px, py);
        aplicaMoldura();
      }
      function aoSoltar() {
        document.removeEventListener("pointermove", aoMover);
        document.removeEventListener("pointerup", aoSoltar);
      }
      document.addEventListener("pointermove", aoMover);
      document.addEventListener("pointerup", aoSoltar);
    }

    moldura.onpointerdown = function (e) {
      if (e.target.classList.contains("recorte__alca")) return;
      var origemX = estadoRecorte.x, origemY = estadoRecorte.y;
      var r = img.getBoundingClientRect();
      var inicioPx = (e.clientX - r.left) / r.width;
      var inicioPy = (e.clientY - r.top) / r.height;
      arrasta(e, function (px, py) {
        var dx = px - inicioPx, dy = py - inicioPy;
        estadoRecorte.x = Math.max(0, Math.min(1 - estadoRecorte.lado, origemX + dx));
        estadoRecorte.y = Math.max(0, Math.min(1 - estadoRecorte.lado, origemY + dy));
      });
    };

    var alca = dlg.querySelector(".recorte__alca");
    alca.onpointerdown = function (e) {
      e.stopPropagation();
      arrasta(e, function (px) {
        var lado = Math.max(0.1, Math.min(1 - estadoRecorte.x, px - estadoRecorte.x));
        estadoRecorte.lado = lado;
      });
    };

    dlg.querySelector("[data-recorte-centralizar]").onclick = function () {
      estadoRecorte = { x: (1 - estadoRecorte.lado) / 2, y: (1 - estadoRecorte.lado) / 2, lado: estadoRecorte.lado };
      aplicaMoldura();
    };

    dlg.querySelector("[data-recorte-aplicar]").onclick = function () {
      var larg = ctx.arquivoCapa.largura, alt = ctx.arquivoCapa.altura;
      var lado = Math.round(estadoRecorte.lado * Math.min(larg, alt));
      ctx.recorte = {
        x: Math.round(estadoRecorte.x * larg),
        y: Math.round(estadoRecorte.y * alt),
        lado: lado,
      };
      dlg.close();
      window.removeEventListener("resize", aplicaMoldura);
      mostraArquivoCapa(ctx);
      agendaPrevia(ctx);
    };

    dlg.showModal();
  }

  /* ---------------------------------------------------------
     Contadores e marca de "sujo"
     --------------------------------------------------------- */
  function atualizaContador(ctx, chave) {
    var el = ctx.els[chave];
    var limites = LIMITES[chave];
    if (!el || !limites || !limites[1]) return;
    var len = String(leCaminho(ctx.dados, chave) || "").length;
    el.contador.textContent = len + "/" + limites[1];
    el.contador.classList.toggle("is-acima", len > limites[1]);
    el.contador.classList.toggle("is-perto", len <= limites[1] && limites[1] - len <= 20);
  }

  function marcaSujo(ctx) {
    ctx.sujo = true;
    window.PAINEL.estado.sujo = true;
  }

  function atualizaConfirmacao(ctx) {
    ctx.autopreenchido = temAutopreenchimento(ctx);
    ctx.elConfirmacao.hidden = !ctx.autopreenchido;
  }

  function atualizaTipoAno(ctx) {
    var m = NUMERO_RE.exec(ctx.dados.numero || "");
    if (!m) {
      ctx.elTipoAno.textContent = "";
      return;
    }
    var tipo = m[1] === "10" ? "Patente de Invenção (PI)" : "Modelo de Utilidade (MU)";
    ctx.elTipoAno.textContent = tipo + " · depósito em " + m[2] + ".";
  }

  /* ---------------------------------------------------------
     Previa (Card / Prévia do hover / Página) — PRD 7.5
     --------------------------------------------------------- */
  function dadosParaApi(ctx) {
    return {
      id: ctx.idEditando,
      numero: ctx.dados.numero,
      categoria: ctx.dados.categoria,
      titulo: ctx.dados.titulo,
      secoes: ctx.dados.secoes,
      trl: ctx.dados.trl,
      oculta: ctx.dados.oculta,
      recorte: ctx.recorte,
    };
  }

  var timerPrevia = null;
  function agendaPrevia(ctx) {
    clearTimeout(timerPrevia);
    timerPrevia = setTimeout(function () { atualizaPrevia(ctx); }, 300);
  }

  function atualizaPrevia(ctx) {
    if (!ctx.dados.titulo && !ctx.dados.secoes.oQueE) {
      ctx.elPreviaConteudo.innerHTML =
        '<div class="painel-vazio">' + U.icone("file-text") +
        "<p>Preencha a ficha para ver a prévia.</p></div>";
      return;
    }
    API.previa(dadosParaApi(ctx), ctx.tokenCapa, ctx.tokenPdf)
      .then(function (r) {
        ctx.ultimaPrevia = r.patente;
        pintaAbaPrevia(ctx);
      })
      .catch(function () { /* previa e so visual: um erro aqui nao bloqueia o formulario */ });
  }

  function pintaAbaPrevia(ctx) {
    var p = ctx.ultimaPrevia;
    if (!p) return;
    if (ctx.previaAba === "card") {
      ctx.elPreviaConteudo.innerHTML = '<div class="previa-card-wrap">' + R.card(p, 0) + "</div>";
    } else if (ctx.previaAba === "hover") {
      ctx.elPreviaConteudo.innerHTML = htmlPreviaHover(p);
    } else {
      ctx.elPreviaConteudo.innerHTML = htmlPreviaPagina(p);
    }
  }

  function htmlPreviaHover(p) {
    var semFicha = !p.imagens.ficha600;
    return (
      '<div class="previa-painel' + (semFicha ? " previa-painel--sem-ficha" : "") + '">' +
      '<img class="previa__img" src="' + (semFicha ? p.imagens.capa800 : p.imagens.ficha600) + '" alt="">' +
      (semFicha ? '<p class="previa__resumo">' + U.esc(p.resumo) + "</p>" : "") +
      '<div class="previa__rodape">' +
      '<span class="trl-chip">' + (p.trl ? U.esc(p.trl.texto) : "—") + "</span>" +
      '<span class="previa__cta">' +
      (semFicha ? "Clique para ver os detalhes →" : "Clique para ver a ficha completa →") +
      "</span></div></div>"
    );
  }

  function htmlPreviaPagina(p) {
    var s = p.secoes || {};
    var corpo =
      R.secao("O que é?", s.oQueE) +
      R.secao("Problema que resolve", s.problema) +
      R.secao("Exemplo de uso", s.exemploDeUso) +
      R.diferenciais(s.diferenciais) +
      R.secao("Benefício principal", s.beneficio);
    return (
      '<div class="previa-pagina">' +
      '<header class="previa-pagina__topo">' +
      '<img class="previa-pagina__capa" src="' + p.imagens.capa400 + '" alt="">' +
      "<div>" +
      '<p class="eyebrow">' + U.esc(p.categoria || "—") + "</p>" +
      "<h3>" + U.esc(p.titulo || "(sem título)") + "</h3>" +
      '<p class="numero-tecnico">' + U.esc(p.numero || "") + "</p>" +
      "</div></header>" +
      R.trl(p.trl) +
      '<div class="previa-pagina__corpo">' + (corpo || "<p class=\"campo__ajuda\">Sem conteúdo ainda.</p>") + "</div>" +
      "</div>"
    );
  }

  /* ---------------------------------------------------------
     Etapas do build + salvar (PRD 7.4, 9.1)
     --------------------------------------------------------- */
  function abreEtapas() {
    var dlg = document.createElement("dialog");
    dlg.className = "modal";
    dlg.innerHTML =
      '<div class="modal__corpo">' +
      '<h2 class="modal__titulo">Atualizando a vitrine</h2>' +
      '<ul class="etapas" aria-live="polite" data-lista-etapas>' +
      ETAPAS.map(function (texto) {
        return (
          '<li class="etapa"><span class="etapa__marca"></span><span>' + U.esc(texto) + "</span></li>"
        );
      }).join("") +
      "</ul></div>";
    document.body.appendChild(dlg);
    dlg.showModal();

    var itens = dlg.querySelectorAll("[data-lista-etapas] .etapa");
    var idx = 0;
    function marca(i, classe) {
      itens[i].className = "etapa " + classe;
      if (classe === "is-ok") itens[i].querySelector(".etapa__marca").innerHTML = U.icone("check");
      else if (classe === "is-erro") itens[i].querySelector(".etapa__marca").innerHTML = U.icone("x");
      else itens[i].querySelector(".etapa__marca").innerHTML = "";
    }
    marca(0, "is-fazendo");
    var timer = setInterval(function () {
      if (idx < itens.length - 1) {
        marca(idx, "is-ok");
        idx++;
        marca(idx, "is-fazendo");
      }
    }, 450);

    return {
      dlg: dlg,
      termina: function (ok) {
        clearInterval(timer);
        for (var i = 0; i < itens.length; i++) marca(i, i <= idx ? (ok ? "is-ok" : i === idx ? "is-erro" : "is-ok") : "");
        setTimeout(function () {
          if (dlg.open) dlg.close();
          dlg.remove();
        }, ok ? 350 : 900);
      },
    };
  }

  function executaSalvar(ctx) {
    var r = validaTudo(ctx);
    limpaTodosOsErros(ctx);
    if (Object.keys(r.erros).length) {
      Object.keys(r.erros).forEach(function (chave) {
        if (chave === "numero") {
          ctx.elNumero.setAttribute("aria-invalid", "true");
          ctx.elNumeroErro.hidden = false;
          ctx.elNumeroErro.textContent = r.erros[chave];
        } else if (chave === "categoria") {
          ctx.elCategoria.setAttribute("aria-invalid", "true");
          ctx.elCategoriaErro.hidden = false;
          ctx.elCategoriaErro.textContent = r.erros[chave];
        } else if (ctx.els[chave]) {
          marcaErroCampo(ctx, chave, r.erros[chave]);
        }
      });
      mostraResumoErros(ctx, r.erros);
      var alvoId =
        r.primeira === "numero" ? "campo-numero" : r.primeira === "categoria" ? "campo-categoria" : idDoCampo(r.primeira) || null;
      ctx.elResumo.scrollIntoView({ behavior: U.reduzido.matches ? "auto" : "smooth", block: "start" });
      var alvo = alvoId && document.getElementById(alvoId);
      if (alvo) alvo.focus();
      return;
    }
    mostraResumoErros(ctx, {});

    var etapas = abreEtapas();
    API.salvar(dadosParaApi(ctx), ctx.tokenCapa, ctx.tokenPdf, ctx.idEditando)
      .then(function (res) {
        var semErro = !res.build.erros.length;
        etapas.termina(semErro);
        ctx.sujo = false;
        window.PAINEL.estado.sujo = false;
        if (semErro) {
          ctx.idEditando = res.id;
          ctx.nova = false;
          ctx.tokenCapa = null;
          ctx.tokenPdf = null;
          window.PAINEL.avisa("Patente salva. A vitrine local foi atualizada.", {
            acoes: [
              { texto: "Ver no site local", aoClicar: function () { API.abrir_link("site_local"); } },
              { texto: "Voltar para a lista", ir: "#/lista" },
            ],
          });
        } else {
          window.PAINEL.avisa(
            "A patente foi salva, mas a vitrine não foi atualizada: " + res.build.erros.join(" "),
            { tipo: "erro" }
          );
        }
        window.PAINEL.atualizaContadores();
      })
      .catch(function (e) {
        etapas.termina(false);
        if (e.campos) {
          Object.keys(e.campos).forEach(function (chave) {
            if (chave === "numero") {
              ctx.elNumero.setAttribute("aria-invalid", "true");
              ctx.elNumeroErro.hidden = false;
              ctx.elNumeroErro.textContent = e.campos[chave];
            } else if (chave === "categoria") {
              ctx.elCategoria.setAttribute("aria-invalid", "true");
              ctx.elCategoriaErro.hidden = false;
              ctx.elCategoriaErro.textContent = e.campos[chave];
            } else if (ctx.els[chave]) {
              marcaErroCampo(ctx, chave, e.campos[chave]);
            }
          });
          mostraResumoErros(ctx, e.campos);
          ctx.elResumo.scrollIntoView({ behavior: U.reduzido.matches ? "auto" : "smooth", block: "start" });
        } else {
          window.PAINEL.avisa(e.mensagem, { tipo: "erro" });
        }
      });
  }

  /* ---------------------------------------------------------
     Esqueleto do formulario (montado uma unica vez)
     --------------------------------------------------------- */
  function criaEsqueleto(ctx) {
    var h = window.PAINEL.h;
    var raiz = document.createDocumentFragment();

    raiz.appendChild(
      window.PAINEL.telaTopo(ctx.nova ? "Nova patente" : "Editar patente", null)
    );

    ctx.elResumo = h("div", { class: "resumo-erros" });
    ctx.elResumo.hidden = true;
    raiz.appendChild(ctx.elResumo);

    var duas = h("div", { class: "duas-colunas" });

    /* ---- coluna do formulario ---- */
    var colForm = h("div", {});

    var caixaFicha = h("section", { class: "painel-caixa" }, [
      h("h3", { class: "painel-caixa__titulo", texto: "Comece pela ficha (recomendado)" }),
    ]);
    ctx.elZonaPdf = h("div", {});
    caixaFicha.appendChild(ctx.elZonaPdf);

    var linkManual = h(
      "button",
      { type: "button", class: "botao botao--terciario", "data-ir-manual": "" },
      ["Não tem o PDF? Preencha manualmente ↓"]
    );
    var linkColar = h(
      "button",
      { type: "button", class: "botao botao--terciario", "data-abrir-colar": "" },
      ["Colar o texto da ficha"]
    );
    var acoesFicha = h("div", { class: "tela-topo__acoes mt-3" }, [linkManual, linkColar]);
    caixaFicha.appendChild(acoesFicha);

    ctx.elColar = h("div", {});
    ctx.elColar.hidden = true;
    var taColar = h("textarea", { rows: "6", placeholder: "Cole aqui o texto da ficha…" });
    var btnUsarTexto = h("button", { type: "button", class: "botao botao--secundario mt-3" }, ["Usar este texto"]);
    ctx.elColar.appendChild(h("div", { class: "campo" }, [taColar]));
    ctx.elColar.appendChild(btnUsarTexto);
    caixaFicha.appendChild(ctx.elColar);
    btnUsarTexto.addEventListener("click", function () {
      var texto = taColar.value;
      if (!texto.trim()) return;
      API.ler_texto_ficha(texto).then(function (campos) {
        preencheComFicha(ctx, campos);
        ctx.elColar.hidden = true;
      }).catch(function (e) {
        window.PAINEL.avisa(e.mensagem, { tipo: "erro" });
      });
    });
    linkColar.addEventListener("click", function () {
      ctx.elColar.hidden = !ctx.elColar.hidden;
    });
    linkManual.addEventListener("click", function () {
      var alvo = document.getElementById("campo-categoria") || ctx.elCategoria;
      if (alvo) {
        alvo.scrollIntoView({ behavior: U.reduzido.matches ? "auto" : "smooth", block: "center" });
        alvo.focus();
      }
    });
    colForm.appendChild(caixaFicha);

    /* ---- identificacao ---- */
    var caixaId = h("section", { class: "painel-caixa" }, [
      h("h3", { class: "painel-caixa__titulo", texto: "Identificação" }),
    ]);
    var campoNumero = h("div", { class: "campo" });
    var rotNumero = h("label", { class: "campo__rotulo", for: "campo-numero" }, [
      h("span", { texto: "Número do pedido" }),
    ]);
    campoNumero.appendChild(rotNumero);
    ctx.elNumero = h("input", {
      type: "text",
      id: "campo-numero",
      placeholder: "BR 10 2025 012345-6",
      "aria-describedby": "campo-numero-erro",
    });
    if (!ctx.nova) {
      ctx.elNumero.disabled = true;
      ctx.elNumero.setAttribute(
        "aria-label",
        "Número do pedido (não editável: o número de uma patente já cadastrada não muda)"
      );
    }
    campoNumero.appendChild(ctx.elNumero);
    ctx.elTipoAno = h("p", { class: "campo__ajuda" });
    campoNumero.appendChild(ctx.elTipoAno);
    ctx.elNumeroErro = h("p", { class: "campo__erro", id: "campo-numero-erro" });
    ctx.elNumeroErro.hidden = true;
    campoNumero.appendChild(ctx.elNumeroErro);
    caixaId.appendChild(campoNumero);

    var campoArea = h("div", { class: "campo" });
    campoArea.appendChild(
      h("label", { class: "campo__rotulo", for: "campo-categoria" }, [h("span", { texto: "Área tecnológica" })])
    );
    ctx.elCategoria = h("select", { id: "campo-categoria", "aria-describedby": "campo-categoria-erro" });
    campoArea.appendChild(ctx.elCategoria);
    ctx.elCategoriaErro = h("p", { class: "campo__erro", id: "campo-categoria-erro" });
    ctx.elCategoriaErro.hidden = true;
    campoArea.appendChild(ctx.elCategoriaErro);
    caixaId.appendChild(campoArea);
    colForm.appendChild(caixaId);

    /* ---- conteudo ---- */
    var caixaConteudo = h("section", { class: "painel-caixa" }, [
      h("h3", { class: "painel-caixa__titulo", texto: "Conteúdo" }),
    ]);
    CAMPOS_TEXTO.forEach(function (def) {
      caixaConteudo.appendChild(montaCampoTexto(ctx, def));
      if (def.chave === "secoes.exemploDeUso") {
        var campoDif = h("div", { class: "campo" }, [
          h("label", { class: "campo__rotulo" }, [h("span", { texto: "Diferenciais competitivos" })]),
        ]);
        ctx.elDiferenciais = h("div", { class: "diferenciais-editor" });
        campoDif.appendChild(ctx.elDiferenciais);
        ctx.elDiferenciaisAdicionar = h(
          "button",
          { type: "button", class: "botao botao--terciario" },
          ["+ Adicionar diferencial"]
        );
        campoDif.appendChild(ctx.elDiferenciaisAdicionar);
        campoDif.appendChild(h("p", { class: "campo__ajuda", texto: "Máximo de 8. Reordene com as setas." }));
        caixaConteudo.appendChild(campoDif);
      }
    });
    colForm.appendChild(caixaConteudo);

    /* ---- maturidade ---- */
    var caixaTrl = h("section", { class: "painel-caixa" }, [
      h("h3", { class: "painel-caixa__titulo", texto: "Maturidade tecnológica" }),
    ]);
    ctx.elTrl = h("div", {});
    caixaTrl.appendChild(ctx.elTrl);
    colForm.appendChild(caixaTrl);

    /* ---- capa ---- */
    var caixaCapa = h("section", { class: "painel-caixa" }, [
      h("h3", { class: "painel-caixa__titulo", texto: "Imagem de capa" }),
      h("p", { class: "campo__ajuda", texto: "Quadrada, ao menos 800×800 px." }),
    ]);
    ctx.elZonaCapa = h("div", {});
    caixaCapa.appendChild(ctx.elZonaCapa);
    colForm.appendChild(caixaCapa);

    /* ---- visibilidade (so em edicao) ---- */
    if (!ctx.nova) {
      var caixaVis = h("section", { class: "painel-caixa" }, [
        h("h3", { class: "painel-caixa__titulo", texto: "Visibilidade" }),
      ]);
      var linhaVis = h("label", { class: "campo-check" }, []);
      ctx.elOculta = h("input", { type: "checkbox" });
      linhaVis.appendChild(ctx.elOculta);
      linhaVis.appendChild(h("span", { texto: " Mostrar na vitrine" }));
      caixaVis.appendChild(linhaVis);
      colForm.appendChild(caixaVis);
    }

    /* ---- confirmacao do preenchimento automatico ---- */
    ctx.elConfirmacao = h("div", { class: "painel-caixa" }, []);
    ctx.elConfirmacao.hidden = true;
    var lblConf = h("label", { class: "campo-check" }, []);
    ctx.elConfirmar = h("input", { type: "checkbox" });
    lblConf.appendChild(ctx.elConfirmar);
    lblConf.appendChild(h("span", { texto: " Conferi as informações preenchidas automaticamente" }));
    ctx.elConfirmacao.appendChild(lblConf);
    colForm.appendChild(ctx.elConfirmacao);

    /* ---- acoes fixas ---- */
    var acoes = h("div", { class: "acoes-fixas" });
    var btnCancelar = h("button", { type: "button", class: "botao botao--terciario" }, ["Cancelar"]);
    var btnSalvar = h("button", { type: "button", class: "botao botao--primario" }, ["Salvar e atualizar a vitrine"]);
    acoes.appendChild(btnCancelar);
    acoes.appendChild(btnSalvar);
    colForm.appendChild(acoes);

    btnCancelar.addEventListener("click", function () {
      if (ctx.sujo) {
        if (!confirm("Há alterações não salvas. Sair mesmo assim?")) return;
        ctx.sujo = false;
        window.PAINEL.estado.sujo = false;
      }
      window.PAINEL.vaiPara("#/lista");
    });
    btnSalvar.addEventListener("click", function () { executaSalvar(ctx); });

    duas.appendChild(colForm);

    /* ---- coluna da previa ---- */
    var colPrevia = h("div", { class: "coluna-previa" });
    var abas = h("div", { class: "segmentado", role: "tablist", "aria-label": "Tipo de prévia" });
    [
      { v: "card", r: "Card" },
      { v: "hover", r: "Prévia do hover" },
      { v: "pagina", r: "Página" },
    ].forEach(function (o) {
      var b = h(
        "button",
        {
          type: "button",
          class: "segmentado__opcao",
          role: "tab",
          "aria-selected": String(o.v === "card"),
          "data-previa-aba": o.v,
        },
        [o.r]
      );
      abas.appendChild(b);
    });
    colPrevia.appendChild(abas);
    ctx.elPreviaConteudo = h("div", { class: "painel-caixa mt-4" });
    colPrevia.appendChild(ctx.elPreviaConteudo);
    colPrevia.appendChild(h("p", { class: "coluna-previa__legenda", texto: "É assim que vai aparecer na vitrine." }));
    duas.appendChild(colPrevia);

    abas.addEventListener("click", function (e) {
      var b = e.target.closest("[data-previa-aba]");
      if (!b) return;
      ctx.previaAba = b.getAttribute("data-previa-aba");
      Array.prototype.forEach.call(abas.querySelectorAll("[data-previa-aba]"), function (x) {
        x.setAttribute("aria-selected", String(x === b));
      });
      pintaAbaPrevia(ctx);
    });

    raiz.appendChild(duas);

    /* ---- modal de recorte (so criado uma vez) ---- */
    var dlgRecorte = h("dialog", { class: "modal modal--largo" });
    dlgRecorte.innerHTML =
      '<div class="modal__corpo">' +
      '<h2 class="modal__titulo">Recortar a capa (1:1)</h2>' +
      '<div class="recorte"><img alt="Prévia da capa para recortar">' +
      '<div class="recorte__moldura"><div class="recorte__alca"></div></div>' +
      "</div></div>" +
      '<div class="modal__acoes">' +
      '<button class="botao botao--terciario" type="button" data-recorte-centralizar>Centralizar</button>' +
      '<button class="botao botao--primario" type="button" data-recorte-aplicar>Aplicar</button>' +
      "</div>";
    ctx.elRecorteDlg = dlgRecorte;
    raiz.appendChild(dlgRecorte);

    return raiz;
  }

  /* ---------------------------------------------------------
     Eventos do formulario (delegacao sobre a raiz da tela)
     --------------------------------------------------------- */
  function ligaEventos(ctx, raiz) {
    raiz.addEventListener("input", function (e) {
      var t = e.target;
      if (t.hasAttribute("data-campo")) {
        var chave = t.getAttribute("data-campo");
        escreveCaminho(ctx.dados, chave, t.value);
        atualizaContador(ctx, chave);
        if (ctx.origens[chave]) limpaOrigem(ctx, chave);
        limpaErroCampo(ctx, chave);
        if (chave === "titulo") {
          ctx.els.titulo.campo.querySelector("[data-converter-titulo]").hidden =
            !(t.value && t.value === t.value.toUpperCase() && t.value !== t.value.toLowerCase());
        }
        marcaSujo(ctx);
        agendaPrevia(ctx);
      } else if (t.hasAttribute("data-dif-idx") && t.tagName === "INPUT") {
        var idx = parseInt(t.getAttribute("data-dif-idx"), 10);
        ctx.dados.secoes.diferenciais[idx] = t.value;
        marcaSujo(ctx);
        agendaPrevia(ctx);
      } else if (t === ctx.elNumero) {
        ctx.dados.numero = t.value;
        marcaSujo(ctx);
      }
    });

    raiz.addEventListener("blur", function (e) {
      var t = e.target;
      if (t.hasAttribute("data-campo")) {
        var chave = t.getAttribute("data-campo");
        var msg = validaCampoTexto(ctx, chave);
        if (msg) marcaErroCampo(ctx, chave, msg);
        else limpaErroCampo(ctx, chave);
      } else if (t === ctx.elNumero && ctx.nova) {
        var normalizado = normalizaNumero(t.value);
        if (normalizado) {
          t.value = normalizado;
          ctx.dados.numero = normalizado;
          ctx.elNumero.removeAttribute("aria-invalid");
          ctx.elNumeroErro.hidden = true;
          atualizaTipoAno(ctx);
        } else if (t.value.trim()) {
          t.setAttribute("aria-invalid", "true");
          ctx.elNumeroErro.hidden = false;
          ctx.elNumeroErro.textContent = "Informe o número do pedido no formato BR 10 2025 012345-6.";
        }
      }
    }, true);

    raiz.addEventListener("change", function (e) {
      var t = e.target;
      if (t === ctx.elCategoria) {
        ctx.dados.categoria = t.value;
        ctx.elCategoria.removeAttribute("aria-invalid");
        ctx.elCategoriaErro.hidden = true;
        marcaSujo(ctx);
        agendaPrevia(ctx);
      } else if (t === ctx.elOculta) {
        ctx.dados.oculta = !t.checked;
        marcaSujo(ctx);
      } else if (t === ctx.elConfirmar) {
        ctx.confirmado = t.checked;
        marcaSujo(ctx);
      } else if (t.hasAttribute("data-trl-select")) {
        var trl = ctx.dados.trl || { min: 1, max: 1, estimado: false };
        var campo = t.getAttribute("data-trl-select");
        var min = campo === "min" ? parseInt(t.value, 10) : trl.min;
        var max = campo === "max" ? parseInt(t.value, 10) : trl.max;
        defineTrl(ctx, min, max, trl.estimado);
      } else if (t.hasAttribute("data-trl-estimado")) {
        var atual = ctx.dados.trl || { min: 1, max: 1 };
        defineTrl(ctx, atual.min, atual.max, t.checked);
      }
    });

    raiz.addEventListener("click", function (e) {
      var dz = e.target.closest("[data-dropzone]");
      if (dz) {
        var tipo = dz.getAttribute("data-dropzone");
        if (tipo === "pdf") {
          processaPdf(ctx, API.escolher_arquivo("pdf").then(function (r) {
            if (r.cancelado) throw { mensagem: "", semAviso: true };
            return r;
          }));
        } else {
          processaCapa(ctx, API.escolher_arquivo("capa").then(function (r) {
            if (r.cancelado) throw { mensagem: "", semAviso: true };
            return r;
          }));
        }
        return;
      }

      var troca = e.target.closest("[data-arquivo-trocar]");
      if (troca) {
        var qual = troca.getAttribute("data-arquivo-trocar");
        if (qual === "pdf") mostraDropzonePdf(ctx);
        else mostraDropzoneCapa(ctx);
        return;
      }
      var remove = e.target.closest("[data-arquivo-remover]");
      if (remove) {
        var qual2 = remove.getAttribute("data-arquivo-remover");
        if (qual2 === "pdf") {
          ctx.tokenPdf = null;
          ctx.arquivoPdf = null;
          mostraDropzonePdf(ctx);
        } else {
          ctx.tokenCapa = null;
          ctx.arquivoCapa = null;
          ctx.recorte = null;
          mostraDropzoneCapa(ctx);
        }
        marcaSujo(ctx);
        agendaPrevia(ctx);
        return;
      }

      var conv = e.target.closest("[data-converter-titulo]");
      if (conv) {
        var v = ctx.els.titulo.input.value;
        var nova = v.charAt(0) + v.slice(1).toLowerCase();
        ctx.els.titulo.input.value = nova;
        ctx.dados.titulo = nova;
        conv.hidden = true;
        atualizaContador(ctx, "titulo");
        agendaPrevia(ctx);
        return;
      }

      var difAcao = e.target.closest("[data-dif-acao]");
      if (difAcao) {
        var acao = difAcao.getAttribute("data-dif-acao");
        var i = parseInt(difAcao.getAttribute("data-dif-idx"), 10);
        var lista = ctx.dados.secoes.diferenciais;
        if (acao === "remover") lista.splice(i, 1);
        else if (acao === "subir" && i > 0) { var tmp = lista[i - 1]; lista[i - 1] = lista[i]; lista[i] = tmp; }
        else if (acao === "descer" && i < lista.length - 1) { var tmp2 = lista[i + 1]; lista[i + 1] = lista[i]; lista[i] = tmp2; }
        pintaDiferenciais(ctx);
        marcaSujo(ctx);
        agendaPrevia(ctx);
        return;
      }

      if (e.target === ctx.elDiferenciaisAdicionar || e.target.closest("button") === ctx.elDiferenciaisAdicionar) {
        if (ctx.dados.secoes.diferenciais.length < DIFERENCIAIS_MAX) {
          ctx.dados.secoes.diferenciais.push("");
          pintaDiferenciais(ctx);
          var inputs = ctx.elDiferenciais.querySelectorAll("input");
          if (inputs.length) inputs[inputs.length - 1].focus();
        }
        return;
      }

      var seg = e.target.closest("[data-trl-seg]");
      if (seg) {
        var n = parseInt(seg.getAttribute("data-trl-seg"), 10);
        var atual = ctx.dados.trl;
        if (e.shiftKey && atual) defineTrl(ctx, atual.min, n, atual.estimado);
        else defineTrl(ctx, n, n, atual ? atual.estimado : false);
        return;
      }

      if (e.target.closest("[data-trl-limpar]")) {
        ctx.dados.trl = null;
        pintaTrl(ctx);
        marcaSujo(ctx);
        agendaPrevia(ctx);
      }
    });

    /* ---- arrastar e soltar ---- */
    ["dragenter", "dragover"].forEach(function (ev) {
      raiz.addEventListener(ev, function (e) {
        var dz = e.target.closest("[data-dropzone]");
        if (!dz) return;
        e.preventDefault();
        dz.classList.add("is-arrastando");
      });
    });
    raiz.addEventListener("dragleave", function (e) {
      var dz = e.target.closest("[data-dropzone]");
      if (dz) dz.classList.remove("is-arrastando");
    });
    raiz.addEventListener("drop", function (e) {
      var dz = e.target.closest("[data-dropzone]");
      if (!dz) return;
      e.preventDefault();
      dz.classList.remove("is-arrastando");
      var arquivos = e.dataTransfer && e.dataTransfer.files;
      if (!arquivos || !arquivos.length) return;
      var file = arquivos[0];
      var tipo = dz.getAttribute("data-dropzone");
      var promessa = lerComoBase64(file).then(function (b64) {
        return API.receber_arquivo(tipo, file.name, b64);
      });
      if (tipo === "pdf") processaPdf(ctx, promessa);
      else processaCapa(ctx, promessa);
    });

    /* ---- Ctrl+V (PRD 9.2) ---- */
    raiz.setAttribute("tabindex", "-1");
    document.addEventListener("paste", ctx.aoColar = function (e) {
      if (!document.contains(raiz)) {
        document.removeEventListener("paste", ctx.aoColar);
        return;
      }
      var arquivos = e.clipboardData && e.clipboardData.files;
      if (arquivos && arquivos.length) {
        var file = arquivos[0];
        var ehPdf = file.type === "application/pdf";
        var ehImagem = file.type.indexOf("image/") === 0;
        if (!ehPdf && !ehImagem) return;
        e.preventDefault();
        var promessa = lerComoBase64(file).then(function (b64) {
          return API.receber_arquivo(ehPdf ? "pdf" : "capa", file.name, b64);
        });
        if (ehPdf) processaPdf(ctx, promessa);
        else processaCapa(ctx, promessa);
        return;
      }
      var ativo = document.activeElement;
      var tag = ativo ? ativo.tagName : "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      var texto = e.clipboardData && e.clipboardData.getData("text/plain");
      if (!texto || !texto.trim()) return;
      window.PAINEL.avisa("Usar este texto para preencher a ficha?", {
        acoes: [
          {
            texto: "Usar este texto",
            aoClicar: function () {
              API.ler_texto_ficha(texto).then(function (campos) {
                preencheComFicha(ctx, campos);
              }).catch(function (err) {
                window.PAINEL.avisa(err.mensagem, { tipo: "erro" });
              });
            },
          },
        ],
      });
    });
  }

  /* ---------------------------------------------------------
     Preenche o esqueleto com os dados iniciais (areas, edicao)
     --------------------------------------------------------- */
  function preencheAreas(ctx) {
    ctx.elCategoria.innerHTML = "";
    var vazio = document.createElement("option");
    vazio.value = "";
    vazio.textContent = "Escolha uma área…";
    ctx.elCategoria.appendChild(vazio);
    ctx.areas.forEach(function (nome) {
      var op = document.createElement("option");
      op.value = nome;
      op.textContent = nome;
      ctx.elCategoria.appendChild(op);
    });
    ctx.elCategoria.value = ctx.dados.categoria || "";
  }

  function carregaDados(ctx) {
    var infoGlobal = window.PAINEL.estado.info || {};
    ctx.areas = infoGlobal.listaAreas || [];
    preencheAreas(ctx);
    pintaDiferenciais(ctx);
    pintaTrl(ctx);

    if (ctx.nova) {
      ctx.carregando = false;
      return;
    }

    API.obter(ctx.idEditando)
      .then(function (d) {
        ctx.areas = d.areas && d.areas.length ? d.areas : ctx.areas;
        preencheAreas(ctx);

        ctx.dados.numero = d.numero;
        ctx.elNumero.value = d.numero;
        atualizaTipoAno(ctx);

        var campos = d.campos || {};
        ctx.dados.categoria = campos.categoria || "";
        ctx.elCategoria.value = ctx.dados.categoria;

        ctx.dados.titulo = campos.titulo || "";
        ctx.els.titulo.input.value = ctx.dados.titulo;
        atualizaContador(ctx, "titulo");

        var secoes = campos.secoes || {};
        ["oQueE", "problema", "exemploDeUso", "beneficio"].forEach(function (campo) {
          var chave = "secoes." + campo;
          ctx.dados.secoes[campo] = secoes[campo] || "";
          ctx.els[chave].input.value = ctx.dados.secoes[campo];
          atualizaContador(ctx, chave);
        });
        ctx.dados.secoes.diferenciais = (secoes.diferenciais || []).slice();
        pintaDiferenciais(ctx);

        ctx.dados.trl = campos.trl || null;
        pintaTrl(ctx);

        ctx.dados.oculta = !!d.oculta;
        if (ctx.elOculta) ctx.elOculta.checked = !d.oculta;

        ctx.temPdfAtual = !!d.temPdf;
        ctx.temCapaAtual = !!d.temCapa;
        if (ctx.temPdfAtual) {
          ctx.arquivoPdf = { nome: "Ficha técnica já cadastrada" };
          mostraArquivoPdf(ctx);
        } else {
          mostraDropzonePdf(ctx);
        }
        if (ctx.temCapaAtual) {
          ctx.arquivoCapa = { tamanho: 0, largura: 0, altura: 0 };
          var card = montaArquivoCard("capa");
          ctx.elZonaCapa.innerHTML = "";
          ctx.elZonaCapa.appendChild(card);
          card.querySelector("[data-arquivo-nome]").textContent = "Capa já cadastrada";
          card.querySelector("[data-arquivo-meta]").textContent = "Envie uma nova imagem para trocar.";
          U.hidrataIcones(card);
        } else {
          mostraDropzoneCapa(ctx);
        }

        ctx.carregando = false;
        atualizaPrevia(ctx);
      })
      .catch(function (e) {
        window.PAINEL.avisa(e.mensagem, { tipo: "erro" });
        window.PAINEL.vaiPara("#/lista");
      });
  }

  /* ---------------------------------------------------------
     Ponto de entrada chamado pelo roteador (painel.js)
     --------------------------------------------------------- */
  function monta(idOuNull) {
    var ctx = criaContexto(idOuNull);
    var raiz = document.createElement("div");
    raiz.className = "tela-editar";
    raiz.appendChild(criaEsqueleto(ctx));

    mostraDropzonePdf(ctx);
    mostraDropzoneCapa(ctx);
    ligaEventos(ctx, raiz);

    // o DOM so entra na pagina depois que esta funcao devolve; adiar ao
    // proximo tick garante que `document.getElementById` (usado pelos links
    // do resumo de erros e pela navegacao do dropzone) ja encontre os nos.
    setTimeout(function () { carregaDados(ctx); }, 0);

    return raiz;
  }

  window.TELA_EDITAR = { monta: monta };
})();
