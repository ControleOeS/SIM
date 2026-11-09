/**
 * Combobox de centro de custo: exibe o Título e busca pelo Cliente,
 * como os ComboBox originais (DisplayFields = Title, SearchFields = Cliente).
 * `alwaysOpen` mantém a lista visível (usado no diálogo de entrada).
 */
import { el } from './components.js';
import { searchCentrosByCliente } from '../domain/rules.js';

let seq = 0;

export class CentroCustoCombo {
  constructor(container, { inputId, alwaysOpen = false, onChange = () => {} } = {}) {
    this.items = [];
    this.selectedId = null;
    this.alwaysOpen = alwaysOpen;
    this.onChange = onChange;
    this.activeIndex = -1;
    const listId = `combo-list-${++seq}`;

    this.input = el('input', {
      id: inputId, class: 'combo__input', type: 'text', role: 'combobox', autocomplete: 'off',
      'aria-autocomplete': 'list', 'aria-controls': listId, 'aria-expanded': alwaysOpen ? 'true' : 'false',
      placeholder: 'Buscar por cliente',
    });
    this.list = el('ul', { id: listId, class: 'combo__list', role: 'listbox' });
    this.list.hidden = !alwaysOpen;
    container.replaceChildren(this.input, this.list);

    this.input.addEventListener('input', () => { this.#open(); this.#render(); });
    this.input.addEventListener('focus', () => { if (!alwaysOpen) this.input.select(); });
    this.input.addEventListener('click', () => { this.#open(); this.#render(); });
    this.input.addEventListener('keydown', (e) => this.#onKey(e));
    this.input.addEventListener('blur', () => setTimeout(() => this.#closeAndRestore(), 150));
  }

  setItems(items) {
    this.items = items;
    this.#render();
  }

  setValue(id) {
    this.selectedId = id ?? null;
    this.input.value = this.alwaysOpen ? '' : (this.#selected()?.titulo ?? '');
    this.#render();
  }

  get value() { return this.selectedId; }

  #selected() { return this.items.find((c) => c.id === this.selectedId); }

  #filtered() {
    const termo = this.alwaysOpen || this.input.value !== (this.#selected()?.titulo ?? '') ? this.input.value : '';
    return searchCentrosByCliente(this.items, termo);
  }

  #open() {
    if (this.alwaysOpen) return;
    this.list.hidden = false;
    this.input.setAttribute('aria-expanded', 'true');
  }

  #closeAndRestore() {
    if (this.alwaysOpen) return;
    this.list.hidden = true;
    this.input.setAttribute('aria-expanded', 'false');
    this.input.value = this.#selected()?.titulo ?? '';
    this.input.removeAttribute('aria-activedescendant');
    this.activeIndex = -1;
  }

  #choose(id) {
    this.selectedId = id;
    if (!this.alwaysOpen) {
      this.input.value = this.#selected()?.titulo ?? '';
      this.#closeAndRestore();
    }
    this.#render();
    this.onChange(id);
  }

  #onKey(e) {
    const opts = [...this.list.querySelectorAll('[role=option]')];
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      this.#open();
      if (!opts.length) return;
      const d = e.key === 'ArrowDown' ? 1 : -1;
      this.activeIndex = (this.activeIndex + d + opts.length) % opts.length;
      this.#highlight(opts);
    } else if (e.key === 'Enter') {
      if (this.activeIndex >= 0 && opts[this.activeIndex]) {
        e.preventDefault();
        this.#choose(Number(opts[this.activeIndex].dataset.id));
      }
    } else if (e.key === 'Escape' && !this.alwaysOpen) {
      e.preventDefault();
      e.stopPropagation();
      this.#closeAndRestore();
    }
  }

  #highlight(opts) {
    opts.forEach((o, i) => o.classList.toggle('is-active', i === this.activeIndex));
    const active = opts[this.activeIndex];
    if (active) {
      this.input.setAttribute('aria-activedescendant', active.id);
      active.scrollIntoView({ block: 'nearest' });
    }
  }

  #render() {
    const items = this.#filtered();
    this.activeIndex = -1;
    if (!items.length) {
      this.list.replaceChildren(el('li', { class: 'combo__empty', text: 'Nenhum centro de custo para esse cliente.' }));
      return;
    }
    this.list.replaceChildren(...items.map((c) => el('li', {
      id: `${this.list.id}-${c.id}`, class: 'combo__option', role: 'option',
      'aria-selected': String(c.id === this.selectedId), dataset: { id: c.id },
      onmousedown: (e) => { e.preventDefault(); this.#choose(c.id); },
    }, [el('span', { text: c.titulo }), el('small', { text: c.cliente })])));
  }
}
