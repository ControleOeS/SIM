/**
 * Regras de negócio do SIM ASAP (códigos RN-xx e P-xx do documento de mapeamento).
 * Funções puras: não acessam interface nem armazenamento.
 */
import { STATUS_APROVADO_CLIENTE, TEXT_MAX_LENGTH } from './schema.js';
import { parseNumberPtBR } from './formatters.js';

const collator = new Intl.Collator('pt-BR', { sensitivity: 'base', numeric: true });

/** RN-01: todos os BMs, ID decrescente. Não altera a lista recebida. */
export function sortBMsByIdDesc(bms) {
  return [...bms].sort((a, b) => b.id - a.id);
}

/** Modal de entrada: Sort('Lista de Apoio ASAP', Título, Ascending). */
export function sortCentrosByTitulo(centros) {
  return [...centros].sort((a, b) => collator.compare(a.titulo ?? '', b.titulo ?? ''));
}

/** RN-04: busca pelo Cliente (contém, sem diferenciar maiúsculas/acentos). */
export function searchCentrosByCliente(centros, termo) {
  const t = normalize(termo);
  if (!t) return centros;
  return centros.filter((c) => normalize(c.cliente).includes(t));
}

function normalize(s) {
  return String(s ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

/**
 * RN-03 + correção P-01.
 * Inclusão: o CC escolhido no modal de entrada é o padrão.
 * Edição: o CC do próprio registro (o original usava o CC do modal, o que podia reatribuir o BM).
 */
export function defaultCentroCustoId(mode, record, centroSelecionadoId) {
  if (mode === 'edit') return record?.centroCustoId ?? null;
  return centroSelecionadoId ?? null;
}

/** Rascunho vazio do formulário de BM (NewForm). */
export function emptyBMDraft(centroSelecionadoId = null) {
  return {
    centroCustoId: centroSelecionadoId,
    titulo: '',
    ano: '',
    mesReferencia: '',
    status: '',
    valorBM: '',
    valorAprovado: '',
    anexos: [],
    glosa: '',
    observacoes: '',
  };
}

export function emptyCentroCustoDraft() {
  return { titulo: '', cliente: '', inicioMedicao: '', fimMedicao: '', email: '', periodo: '' };
}

const MSG_OBRIGATORIO = 'Campo obrigatório.';
const MSG_NUMERO = 'Informe um número válido (ex.: 1.234,56).';
const MSG_TAMANHO = `Máximo de ${TEXT_MAX_LENGTH} caracteres.`;

function isBlank(v) {
  return v === null || v === undefined || (typeof v === 'string' && v.trim() === '');
}

function checkText(errors, key, value, { required, maxLength }) {
  if (required && isBlank(value)) errors[key] = MSG_OBRIGATORIO;
  else if (maxLength && String(value ?? '').length > maxLength) errors[key] = MSG_TAMANHO;
}

function checkNumber(errors, values, key, raw, { required }) {
  const n = parseNumberPtBR(raw);
  if (n === null) {
    if (required) errors[key] = MSG_OBRIGATORIO;
    values[key] = null;
  } else if (Number.isNaN(n)) {
    errors[key] = MSG_NUMERO;
  } else {
    values[key] = n;
  }
}

/**
 * RN-05: valida o formulário de BM e converte os números.
 * Retorna { ok, errors, values }. `values` só é confiável quando ok = true.
 */
export function validateBMDraft(draft) {
  const errors = {};
  const values = {
    centroCustoId: draft.centroCustoId ?? null,
    titulo: String(draft.titulo ?? '').trim(),
    ano: draft.ano ?? '',
    mesReferencia: draft.mesReferencia ?? '',
    status: draft.status ?? '',
    anexos: Array.isArray(draft.anexos) ? draft.anexos : [],
    observacoes: draft.observacoes ?? '',
  };

  if (values.centroCustoId === null || values.centroCustoId === '') errors.centroCustoId = MSG_OBRIGATORIO;
  checkText(errors, 'titulo', values.titulo, { required: true, maxLength: TEXT_MAX_LENGTH });
  if (isBlank(values.ano)) errors.ano = MSG_OBRIGATORIO;
  if (isBlank(values.mesReferencia)) errors.mesReferencia = MSG_OBRIGATORIO;
  if (isBlank(values.status)) errors.status = MSG_OBRIGATORIO;
  checkNumber(errors, values, 'valorBM', draft.valorBM, { required: true });
  checkNumber(errors, values, 'valorAprovado', draft.valorAprovado, { required: true });
  checkNumber(errors, values, 'glosa', draft.glosa, { required: false });
  if (values.anexos.length === 0) errors.anexos = 'Adicione pelo menos um anexo.';

  return { ok: Object.keys(errors).length === 0, errors, values };
}

/** RN-11: valida o formulário de Cadastro de centro de custo. */
export function validateCentroCustoDraft(draft) {
  const errors = {};
  const values = {
    titulo: String(draft.titulo ?? '').trim(),
    cliente: String(draft.cliente ?? '').trim(),
    email: String(draft.email ?? '').trim(),
    periodo: String(draft.periodo ?? '').trim(),
  };
  checkText(errors, 'titulo', values.titulo, { required: true, maxLength: TEXT_MAX_LENGTH });
  checkText(errors, 'cliente', values.cliente, { required: true, maxLength: TEXT_MAX_LENGTH });
  checkNumber(errors, values, 'inicioMedicao', draft.inicioMedicao, { required: true });
  checkNumber(errors, values, 'fimMedicao', draft.fimMedicao, { required: true });
  // O original não valida o formato do e-mail; mantido assim.
  checkText(errors, 'email', values.email, { required: true });
  checkText(errors, 'periodo', values.periodo, { required: false, maxLength: TEXT_MAX_LENGTH });
  return { ok: Object.keys(errors).length === 0, errors, values };
}

/**
 * RN-07 (Form1.OnSuccess): se o status gravado é "BM Aprovado pelo Cliente"
 * e não há data de aprovação, registra a data/hora atual. Nunca sobrescreve uma data existente.
 */
export function applyApprovalDate(record, now = new Date()) {
  if (record.status === STATUS_APROVADO_CLIENTE && !record.dataAprovacaoCliente) {
    return { ...record, dataAprovacaoCliente: now.toISOString() };
  }
  return record;
}
