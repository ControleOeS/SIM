/** Casos de uso da tela Cadastro (somente inclusão, como no original). */
import { validateCentroCustoDraft } from '../domain/rules.js';

export async function cadastrarCentroCusto(repo, draft) {
  const { ok, errors, values } = validateCentroCustoDraft(draft);
  if (!ok) return { ok: false, errors };
  return { ok: true, registro: await repo.criarCentroCusto(values) };
}
