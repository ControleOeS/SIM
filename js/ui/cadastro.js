/** Tela Cadastro: inclusão de centro de custo (o original não edita nem exclui). */
import { toast, renderFieldErrors } from './components.js';
import { emptyCentroCustoDraft } from '../domain/rules.js';
import { cadastrarCentroCusto } from '../services/centro-custo-service.js';

export function createCadastroScreen({ repo, go }) {
  const root = document.getElementById('screen-cadastro');
  const form = document.getElementById('cc-form');
  const salvar = document.getElementById('cc-salvar');
  const keys = Object.keys(emptyCentroCustoDraft());

  root.querySelectorAll('[data-action="ir-home"]').forEach((b) => b.addEventListener('click', () => go('home')));
  document.getElementById('cc-cancelar').addEventListener('click', novoFormulario);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (salvar.disabled) return;
    salvar.disabled = true;
    try {
      const draft = Object.fromEntries(keys.map((k) => [k, form.elements[k].value]));
      const r = await cadastrarCentroCusto(repo, draft);
      if (!r.ok) {
        renderFieldErrors(form, 'cc', r.errors)?.focus();
        toast('Revise os campos destacados.', { error: true });
        return;
      }
      toast(`Centro de custo "${r.registro.titulo}" cadastrado.`);
      novoFormulario();
    } catch (err) {
      toast(err.message, { error: true });
    } finally {
      salvar.disabled = false;
    }
  });

  function novoFormulario() {
    form.reset();
    renderFieldErrors(form, 'cc', {});
    form.elements.titulo.focus();
  }

  return { enter: novoFormulario };
}
