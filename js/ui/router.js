/** Navegação entre telas por hash (#/, #/bm-mensal, #/cadastro), equivalente a Navigate(). */
const ROUTES = { '#/': 'home', '#/bm-mensal': 'bm', '#/cadastro': 'cadastro' };
const HASH_BY_SCREEN = Object.fromEntries(Object.entries(ROUTES).map(([h, s]) => [s, h]));

export function createRouter(screens) {
  async function show() {
    const name = ROUTES[location.hash] ?? 'home';
    document.querySelectorAll('[data-screen]').forEach((s) => { s.hidden = s.dataset.screen !== name; });
    window.scrollTo(0, 0);
    await screens[name]?.enter?.();
  }
  window.addEventListener('hashchange', show);
  return {
    start: show,
    go(name) {
      const hash = HASH_BY_SCREEN[name];
      if (location.hash === hash) show(); // reentrar na mesma tela repete o OnVisible
      else location.hash = hash;
    },
  };
}
