import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  sortBMsByIdDesc, sortCentrosByTitulo, searchCentrosByCliente, defaultCentroCustoId,
  validateBMDraft, validateCentroCustoDraft, applyApprovalDate, emptyBMDraft,
} from '../../js/domain/rules.js';
import { STATUS_APROVADO_CLIENTE } from '../../js/domain/schema.js';

const draftValido = () => ({
  ...emptyBMDraft(1), titulo: 'BM.pdf', ano: '2026', mesReferencia: 'Julho', status: 'X',
  valorBM: '1.000,00', valorAprovado: '0', anexos: [{ nome: 'a.pdf' }],
});

test('RN-01 ordena por ID decrescente sem alterar a origem', () => {
  const orig = [{ id: 2 }, { id: 10 }, { id: 1 }];
  assert.deepEqual(sortBMsByIdDesc(orig).map((b) => b.id), [10, 2, 1]);
  assert.deepEqual(orig.map((b) => b.id), [2, 10, 1]);
});

test('Modal de CC ordena por título crescente', () => {
  const r = sortCentrosByTitulo([{ titulo: 'Beta' }, { titulo: 'alfa' }, { titulo: 'Ômega' }]);
  assert.deepEqual(r.map((c) => c.titulo), ['alfa', 'Beta', 'Ômega']);
});

test('RN-04 busca por cliente, sem acento e sem caixa', () => {
  const lista = [{ cliente: 'Cliente Épsilon' }, { cliente: 'Cliente Beta' }];
  assert.equal(searchCentrosByCliente(lista, 'epsi').length, 1);
  assert.equal(searchCentrosByCliente(lista, '').length, 2);
  assert.equal(searchCentrosByCliente(lista, 'zzz').length, 0);
});

test('P-01: edição usa o CC do registro; inclusão usa o CC do modal', () => {
  assert.equal(defaultCentroCustoId('edit', { centroCustoId: 7 }, 3), 7);
  assert.equal(defaultCentroCustoId('new', null, 3), 3);
  assert.equal(defaultCentroCustoId('new', null, undefined), null);
});

test('RN-05 aceita rascunho completo e converte números', () => {
  const r = validateBMDraft(draftValido());
  assert.equal(r.ok, true);
  assert.equal(r.values.valorBM, 1000);
  assert.equal(r.values.valorAprovado, 0);
  assert.equal(r.values.glosa, null);
});

test('RN-05 aponta todos os obrigatórios vazios', () => {
  const r = validateBMDraft(emptyBMDraft(null));
  assert.equal(r.ok, false);
  for (const k of ['centroCustoId', 'titulo', 'ano', 'mesReferencia', 'status', 'valorBM', 'valorAprovado', 'anexos']) {
    assert.ok(r.errors[k], `esperava erro em ${k}`);
  }
  assert.equal(r.errors.glosa, undefined);
  assert.equal(r.errors.observacoes, undefined);
});

test('RN-06: Valor Aprovado 0 é válido (não é tratado como vazio)', () => {
  assert.equal(validateBMDraft({ ...draftValido(), valorAprovado: '0' }).ok, true);
});

test('Números inválidos e título longo geram erro', () => {
  const r = validateBMDraft({ ...draftValido(), valorBM: 'abc', glosa: '1,2,3', titulo: 'x'.repeat(256) });
  assert.ok(r.errors.valorBM);
  assert.ok(r.errors.glosa);
  assert.ok(r.errors.titulo);
});

test('RN-11 Cadastro: obrigatórios e período opcional', () => {
  const vazio = validateCentroCustoDraft({});
  for (const k of ['titulo', 'cliente', 'inicioMedicao', 'fimMedicao', 'email']) assert.ok(vazio.errors[k]);
  assert.equal(vazio.errors.periodo, undefined);
  const ok = validateCentroCustoDraft({ titulo: 'CC', cliente: 'C', inicioMedicao: '1', fimMedicao: '30', email: 'x' });
  assert.equal(ok.ok, true);
  assert.equal(ok.values.fimMedicao, 30);
});

test('RN-07 grava a data de aprovação só quando aprovado e sem data', () => {
  const now = new Date('2026-10-15T12:00:00Z');
  assert.equal(applyApprovalDate({ status: STATUS_APROVADO_CLIENTE, dataAprovacaoCliente: null }, now).dataAprovacaoCliente, now.toISOString());
  assert.equal(applyApprovalDate({ status: STATUS_APROVADO_CLIENTE, dataAprovacaoCliente: '2026-01-01T00:00:00Z' }, now).dataAprovacaoCliente, '2026-01-01T00:00:00Z');
  assert.equal(applyApprovalDate({ status: 'Outro', dataAprovacaoCliente: null }, now).dataAprovacaoCliente, null);
});
