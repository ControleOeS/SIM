import { test } from 'node:test';
import assert from 'node:assert/strict';
import { MockRepository } from '../../js/data/mock-repository.js';
import { assertRepository } from '../../js/data/repository.js';
import { ApiRepository } from '../../js/data/api-repository.js';
import { carregarTelaBM, salvarBM, excluirBM } from '../../js/services/bm-service.js';
import { cadastrarCentroCusto } from '../../js/services/centro-custo-service.js';
import { STATUS_APROVADO_CLIENTE } from '../../js/domain/schema.js';

const now = new Date('2026-10-15T15:00:00Z');
const draft = (extra = {}) => ({
  centroCustoId: 2, titulo: 'Novo.pdf', ano: '2026', mesReferencia: 'Outubro', status: 'Em Elaboração (provisório)',
  valorBM: '500,00', valorAprovado: '0', glosa: '', observacoes: '', anexos: [{ nome: 'n.pdf' }], ...extra,
});

test('repositórios cumprem o contrato', () => {
  assertRepository(new MockRepository());
  assertRepository(new ApiRepository('/api'));
});

test('ApiRepository falha explicitamente (não simula dados reais)', async () => {
  await assert.rejects(new ApiRepository('/api').listarBMs(), /não implementada/);
});

test('carregarTelaBM devolve BMs em ID decrescente', async () => {
  const { bms, centros } = await carregarTelaBM(new MockRepository());
  const ids = bms.map((b) => b.id);
  assert.deepEqual(ids, [...ids].sort((a, b) => b - a));
  assert.ok(centros.length > 0);
});

test('inclusão gera ID novo e preserva campos ocultos como nulos', async () => {
  const repo = new MockRepository({ clock: () => now });
  const r = await salvarBM(repo, { mode: 'new', draft: draft(), now });
  assert.equal(r.ok, true);
  assert.equal(r.registro.id, 7);
  assert.equal(r.registro.valorBM, 500);
  assert.equal(r.registro.frs, null);
  assert.equal(r.registro.criado, now.toISOString());
});

test('inclusão aprovada recebe data de aprovação', async () => {
  const repo = new MockRepository();
  const r = await salvarBM(repo, { mode: 'new', draft: draft({ status: STATUS_APROVADO_CLIENTE }), now });
  assert.equal(r.registro.dataAprovacaoCliente, now.toISOString());
});

test('edição preserva campos fora do formulário e não sobrescreve data existente', async () => {
  const repo = new MockRepository();
  const antes = await repo.obterBM(1);
  const r = await salvarBM(repo, { mode: 'edit', id: 1, draft: { ...draft(), centroCustoId: antes.centroCustoId, status: STATUS_APROVADO_CLIENTE }, now });
  assert.equal(r.registro.valorEmitido, antes.valorEmitido);
  assert.equal(r.registro.dataAprovacaoCliente, antes.dataAprovacaoCliente);
  assert.equal(r.registro.criado, antes.criado);
});

test('edição de BM aprovado sem data passa a ter data (RN-07)', async () => {
  const repo = new MockRepository();
  const bm6 = await repo.obterBM(6);
  assert.equal(bm6.dataAprovacaoCliente, null);
  const r = await salvarBM(repo, { mode: 'edit', id: 6, draft: { ...draft(), centroCustoId: bm6.centroCustoId, status: STATUS_APROVADO_CLIENTE }, now });
  assert.equal(r.registro.dataAprovacaoCliente, now.toISOString());
});

test('validação falha sem gravar nada', async () => {
  const repo = new MockRepository();
  const r = await salvarBM(repo, { mode: 'new', draft: draft({ titulo: '' }), now });
  assert.equal(r.ok, false);
  assert.equal((await repo.listarBMs()).length, 6);
});

test('CC inexistente é rejeitado', async () => {
  await assert.rejects(salvarBM(new MockRepository(), { mode: 'new', draft: draft({ centroCustoId: 999 }), now }), /não encontrado/);
});

test('exclusão remove só o registro escolhido', async () => {
  const repo = new MockRepository();
  await excluirBM(repo, 3);
  const ids = (await repo.listarBMs()).map((b) => b.id);
  assert.equal(ids.includes(3), false);
  assert.equal(ids.length, 5);
});

test('editar um BM excluído informa o erro', async () => {
  const repo = new MockRepository();
  await excluirBM(repo, 2);
  await assert.rejects(salvarBM(repo, { mode: 'edit', id: 2, draft: draft(), now }), /não existe mais/);
});

test('cadastro de centro de custo', async () => {
  const repo = new MockRepository();
  const r = await cadastrarCentroCusto(repo, { titulo: 'CC Novo', cliente: 'Cli', inicioMedicao: '1', fimMedicao: '30', email: 'e', periodo: '' });
  assert.equal(r.ok, true);
  assert.equal(r.registro.id, 6);
  assert.equal((await cadastrarCentroCusto(repo, {})).ok, false);
});
