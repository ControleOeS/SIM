/** Tela Inicial: apenas navegação. Atualização de dados e NewForm acontecem ao entrar em cada tela. */
export function createHomeScreen({ go }) {
  const root = document.getElementById('screen-home');
  root.querySelector('[data-action="ir-bm"]').addEventListener('click', () => go('bm'));
  root.querySelector('[data-action="ir-cadastro"]').addEventListener('click', () => go('cadastro'));
  return { enter() { root.querySelector('[data-action="ir-bm"]').focus(); } };
}
