import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatMoneyPtBR, formatDateTimePtBR, parseNumberPtBR } from '../../js/domain/formatters.js';

test('formatMoneyPtBR segue #,##0.00 pt-BR', () => {
  assert.equal(formatMoneyPtBR(1234567.891), '1.234.567,89');
  assert.equal(formatMoneyPtBR(0), '0,00');
  assert.equal(formatMoneyPtBR(-10.5), '-10,50');
});

test('formatMoneyPtBR devolve vazio para valor em branco', () => {
  assert.equal(formatMoneyPtBR(null), '');
  assert.equal(formatMoneyPtBR(undefined), '');
  assert.equal(formatMoneyPtBR(''), '');
});

test('formatDateTimePtBR usa dd/mm/yyyy hh:mm', () => {
  assert.equal(formatDateTimePtBR(new Date(2026, 9, 5, 7, 3)), '05/10/2026 07:03');
  assert.equal(formatDateTimePtBR(null), '');
  assert.equal(formatDateTimePtBR('texto'), '');
});

test('parseNumberPtBR aceita formatos comuns', () => {
  assert.equal(parseNumberPtBR('1.234,56'), 1234.56);
  assert.equal(parseNumberPtBR('1234,56'), 1234.56);
  assert.equal(parseNumberPtBR('1234.56'), 1234.56);
  assert.equal(parseNumberPtBR('1.234.567'), 1234567);
  assert.equal(parseNumberPtBR('-10'), -10);
  assert.equal(parseNumberPtBR(' 0 '), 0);
});

test('parseNumberPtBR: vazio = null, inválido = NaN', () => {
  assert.equal(parseNumberPtBR(''), null);
  assert.equal(parseNumberPtBR('   '), null);
  assert.ok(Number.isNaN(parseNumberPtBR('abc')));
  assert.ok(Number.isNaN(parseNumberPtBR('1,2,3')));
  assert.ok(Number.isNaN(parseNumberPtBR('12.34.5')));
  assert.ok(Number.isNaN(parseNumberPtBR('-')));
});
