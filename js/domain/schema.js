/**
 * Esquema dos registros, espelhando as listas SharePoint do app original.
 * `sp` = nome interno da coluna no SharePoint (referência para a futura migração ao Excel).
 * `ui` = true quando o campo aparece nas telas Tela Inicial / BM Mensal / Cadastro.
 * Campos com ui=false não aparecem nas telas, mas são preservados nos registros.
 */

export const STATUS_APROVADO_CLIENTE = 'BM Aprovado pelo Cliente';

export const TEXT_MAX_LENGTH = 255;

export const BM_FIELDS = [
  { key: 'id', sp: 'ID', label: 'ID', type: 'auto', ui: true },
  { key: 'centroCustoId', sp: 'CentrodeCusto', label: 'Centro de Custo', type: 'lookup', required: true, ui: true },
  { key: 'titulo', sp: 'Title', label: 'Nome do Arquivo', type: 'text', maxLength: TEXT_MAX_LENGTH, required: true, ui: true },
  { key: 'ano', sp: 'Ano', label: 'Ano', type: 'choice', required: true, ui: true },
  { key: 'mesReferencia', sp: 'MêsdeReferência', label: 'Mês de Referência', type: 'choice', required: true, ui: true },
  { key: 'status', sp: 'Status', label: 'Status', type: 'choice', required: true, ui: true },
  { key: 'valorBM', sp: 'ValorBM', label: 'Valor BM', type: 'number', required: true, ui: true },
  { key: 'valorAprovado', sp: 'ValorAprovado', label: 'Valor Aprovado', type: 'number', required: true, ui: true },
  { key: 'anexos', sp: '{Attachments}', label: 'Anexos', type: 'attachments', required: true, ui: true },
  { key: 'glosa', sp: 'Glosa', label: 'Glosa', type: 'number', required: false, ui: true },
  { key: 'observacoes', sp: 'Observações', label: 'Observações', type: 'multiline', required: false, ui: true },
  { key: 'valorEmitido', sp: 'ValorEmitido', label: 'Valor Emitido', type: 'number', readOnly: true, ui: true },
  { key: 'dataAprovacaoCliente', sp: 'DataAprovacaoCliente', label: 'Data de aprovação do cliente', type: 'datetime', readOnly: true, ui: false },
  { key: 'frs', sp: 'FRS', label: 'FRS', type: 'number', ui: false },
  { key: 'valorLiberado', sp: 'ValorLiberado', label: 'Valor Liberado', type: 'number', ui: false },
  { key: 'ultimoAlerta', sp: 'UltimoAlerta', label: 'UltimoAlerta', type: 'datetime', ui: false },
  { key: 'dataCriacao', sp: 'DataCriação', label: 'Data Criação (coluna editável)', type: 'datetime', ui: false },
  { key: 'criado', sp: 'Created', label: 'Criado', type: 'system-datetime', ui: true },
  { key: 'modificado', sp: 'Modified', label: 'Modificado', type: 'system-datetime', ui: false },
];

export const CENTRO_CUSTO_FIELDS = [
  { key: 'id', sp: 'ID', label: 'ID', type: 'auto', ui: false },
  { key: 'titulo', sp: 'Title', label: 'Centro de Custo', type: 'text', maxLength: TEXT_MAX_LENGTH, required: true, ui: true },
  { key: 'cliente', sp: 'Cliente', label: 'Cliente', type: 'text', maxLength: TEXT_MAX_LENGTH, required: true, ui: true },
  { key: 'inicioMedicao', sp: 'IníciodeMedição', label: 'Início de Medição', type: 'number', required: true, ui: true },
  { key: 'fimMedicao', sp: 'FimdeMedição', label: 'Fim de Medição', type: 'number', required: true, ui: true },
  { key: 'email', sp: 'E-mail', label: 'E-mail', type: 'multiline', required: true, ui: true },
  { key: 'periodo', sp: 'p', label: 'Período: Mensal ou Quinzenal', type: 'text', maxLength: TEXT_MAX_LENGTH, required: false, ui: true },
  { key: 'numeroContrato', sp: 'NºdoContrato', label: 'Nº do Contrato', type: 'text', ui: false },
  { key: 'cidade', sp: 'Cidade', label: 'Cidade', type: 'choice', ui: false },
  { key: 'metaBM', sp: 'MetaBM', label: 'Meta BM', type: 'number', ui: false },
  { key: 'criado', sp: 'Created', label: 'Criado', type: 'system-datetime', ui: false },
  { key: 'modificado', sp: 'Modified', label: 'Modificado', type: 'system-datetime', ui: false },
];

export function fieldByKey(fields, key) {
  return fields.find((f) => f.key === key);
}
