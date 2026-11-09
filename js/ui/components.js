/** Utilitários de interface: criação segura de elementos, avisos e ícones. */

/** Cria um elemento. Textos sempre via textContent (nunca innerHTML com dados). */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k === 'dataset') Object.assign(node.dataset, v);
    else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? '' : String(v));
  }
  for (const c of [].concat(children)) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

export function toast(message, { error = false } = {}) {
  const region = document.getElementById('toast-region');
  const t = el('div', { class: `toast${error ? ' toast--error' : ''}`, text: message });
  region.append(t);
  setTimeout(() => t.remove(), error ? 6000 : 3200);
}

export function showFatal(message) {
  const banner = document.getElementById('error-banner');
  banner.textContent = message;
  banner.hidden = false;
}

export function clearFatal() {
  const banner = document.getElementById('error-banner');
  banner.textContent = '';
  banner.hidden = true;
}

/** Mostra os erros de validação nos campos (prefixo = 'bm' ou 'cc'). */
export function renderFieldErrors(form, prefix, errors) {
  form.querySelectorAll('.field__error').forEach((p) => { p.textContent = ''; });
  form.querySelectorAll('.has-error').forEach((f) => f.classList.remove('has-error'));
  form.querySelectorAll('[aria-invalid]').forEach((i) => i.removeAttribute('aria-invalid'));
  let first = null;
  for (const [key, msg] of Object.entries(errors)) {
    const p = document.getElementById(`err-${prefix}-${key}`);
    if (!p) continue;
    p.textContent = msg;
    const field = p.closest('.field');
    field?.classList.add('has-error');
    const input = field?.querySelector('input:not([type=file]), select, textarea');
    input?.setAttribute('aria-invalid', 'true');
    if (!first) first = field?.querySelector('input, select, textarea');
  }
  return first;
}

const ICONS = {
  edit: 'M4 20h4L19 9l-4-4L4 16v4zM14 6l4 4',
  trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
  clip: 'M8 12.5l6.5-6.5a3 3 0 0 1 4.2 4.2l-8 8a5 5 0 0 1-7-7l7.5-7.5',
};

export function icon(name) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.8');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(ns, 'path');
  path.setAttribute('d', ICONS[name]);
  svg.append(path);
  return svg;
}

export function fillSelect(select, options, value = '') {
  select.replaceChildren(el('option', { value: '', text: 'Selecione…' }));
  for (const o of options) select.append(el('option', { value: o, text: o }));
  // Valor gravado que não está mais entre as escolhas continua visível
  if (value && !options.includes(value)) select.append(el('option', { value, text: `${value} (fora da lista)` }));
  select.value = value ?? '';
}
