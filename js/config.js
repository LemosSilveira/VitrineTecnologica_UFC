/* Configuracao global da Vitrine de Patentes UFC.
 * Carregado como script classico (sem modulos) para funcionar tambem via file://.
 */
window.CONFIG = {
  /* PENDENTE: confirmar o nome oficial com a UFC Inova. */
  siteName: "Vitrine de Patentes UFC",

  ufcInovaUrl: "https://ufcinova.sitios.sti.ufc.br",

  /* E-mail de licenciamento. Enquanto estiver vazio, o botao "Tenho interesse"
   * fica escondido na pagina de detalhe (decisao do usuario em 24/09/2026).
   * PENDENTE: canal oficial da UFC Inova. */
  contatoEmail: "",

  /* Raiz de dominio. Se um dia o site for para uma subpasta (ex.: GitHub Pages
   * em /vitrine-patentes/), basta trocar aqui: a 404 monta os caminhos
   * absolutos a partir deste valor. Sempre com barra no inicio e no fim. */
  basePath: "/",
};
