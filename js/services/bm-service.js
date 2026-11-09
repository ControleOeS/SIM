/**
 * Casos de uso da tela BM Mensal. Orquestra regras de domínio e repositório,
 * sem tocar na interface.
 */
import { validateBMDraft, applyApprovalDate, sortBMsByIdDesc, sortCentrosByTitulo } from '../domain/rules.js';

/** Carrega o que a tela precisa: BMs (ID desc.), centros de custo e escolhas. */
export async function carregarTelaBM(repo) {
  await repo.refresh();
  const [bms, centros, escolhas] = await Promise.all([
    repo.listarBMs(), repo.listarCentrosCusto(), repo.obterEscolhas(),
  ]);
  return { bms: sortBMsByIdDesc(bms), centros: sortCentrosByTitulo(centros), escolhas };
}

/**
 * Salvar (botão Salvar + Form1.OnSuccess), numa única gravação.
 * mode = 'new' | 'edit'. Em edição, os campos que não aparecem no formulário são preservados.
 * Retorna { ok:false, errors } ou { ok:true, registro }.
 */
export async function salvarBM(repo, { mode, id, draft, now = new Date() }) {
  const { ok, errors, values } = validateBMDraft(draft);
  if (!ok) return { ok: false, errors };

  if (mode === 'edit') {
    const atual = await repo.obterBM(id);
    if (!atual) throw new Error(`O BM ${id} não existe mais. Ele pode ter sido excluído.`);
    const final = applyApprovalDate({ ...atual, ...values }, now);
    return { ok: true, registro: await repo.atualizarBM(id, final) };
  }
  const final = applyApprovalDate({ ...values, dataAprovacaoCliente: null }, now);
  return { ok: true, registro: await repo.criarBM(final) };
}

/** Exclusão confirmada (botão SIM do modal). */
export async function excluirBM(repo, id) {
  await repo.excluirBM(id);
}
