/**
 * Formatação e conversão de valores no padrão pt-BR.
 * Equivalentes às fórmulas originais:
 *   Text(Value(x), "#,##0.00", "pt-BR")  -> formatMoneyPtBR
 *   Text(ThisItem.Criado, "dd/mm/yyyy hh:mm") -> formatDateTimePtBR
 *   Value(DataCardValueN.Text) -> parseNumberPtBR
 */

const moneyFormatter = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Valor vazio gera texto vazio, como Text(Blank()) no Power Fx. */
export function formatMoneyPtBR(value) {
  if (value === null || value === undefined || value === '') return '';
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return '';
  return moneyFormatter.format(n);
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

/** dd/mm/yyyy hh:mm no fuso local do navegador. Vazio ou inválido -> ''. */
export function formatDateTimePtBR(value) {
  if (!value) return '';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/**
 * Converte o texto digitado em número.
 * Aceita "1.234,56", "1234,56", "1234.56", "-10" e "1.234.567".
 * Retorna null para texto vazio e NaN para texto inválido.
 */
export function parseNumberPtBR(text) {
  if (text === null || text === undefined) return null;
  if (typeof text === 'number') return Number.isFinite(text) ? text : NaN;
  let s = String(text).trim().replace(/\s/g, '');
  if (s === '') return null;
  if (!/^-?[\d.,]+$/.test(s)) return NaN;

  if (s.includes(',')) {
    // Padrão pt-BR: ponto = milhar, vírgula = decimal
    if ((s.match(/,/g) || []).length > 1) return NaN;
    const [intPart, decPart] = s.split(',');
    if (intPart.includes('.') && !/^-?\d{1,3}(\.\d{3})+$/.test(intPart)) return NaN;
    s = `${intPart.replace(/\./g, '')}.${decPart}`;
  } else if ((s.match(/\./g) || []).length > 1) {
    // Vários pontos sem vírgula: só pode ser separador de milhar
    if (!/^-?\d{1,3}(\.\d{3})+$/.test(s)) return NaN;
    s = s.replace(/\./g, '');
  }
  if (!/^-?\d*\.?\d+$/.test(s) && !/^-?\d+\.?$/.test(s)) return NaN;
  const n = Number(s);
  return Number.isFinite(n) ? n : NaN;
}

/** Texto para preencher um campo numérico ao editar um registro. */
export function numberToInputText(value) {
  if (value === null || value === undefined || value === '') return '';
  return formatMoneyPtBR(value);
}
