/**
 * Tela BM Mensal: diálogo de escolha do CC, lista (galeria), formulário e exclusão.
 * Só cuida de interface; regras ficam em domain/ e services/.
 */
import { el, toast, icon, renderFieldErrors, fillSelect, showFatal, clearFatal } from './components.js';
import { CentroCustoCombo } from './combobox.js';
import { formatMoneyPtBR, formatDateTimePtBR, numberToInputText } from '../domain/formatters.js';
import { defaultCentroCustoId, emptyBMDraft } from '../domain/rules.js';
import { STATUS_APROVADO_CLIENTE } from '../domain/schema.js';
import { carregarTelaBM, salvarBM, excluirBM } from '../services/bm-service.js';

export function createBMScreen({ repo, go }) {
  const $ = (id) => document.getElementById(id);
  const root = $('screen-bm');
  const form = $('bm-form');
  const dlgCC = $('dlg-cc');
  const dlgExcluir = $('dlg-excluir');
  const dlgAnexos = $('dlg-anexos');
  const fields = {
    titulo: $('bm-titulo'), ano: $('bm-ano'), mesReferencia: $('bm-mes'), status: $('bm-status'),
    valorBM: $('bm-valor'), valorAprovado: $('bm-aprovado'), glosa: $('bm-glosa'), observacoes: $('bm-obs'),
  };

  const state = {
    bms: [], centros: [], escolhas: { ano: [], mesReferencia: [], status: [] },
    ccSelecionadoId: null,   // varObraAtual
    selectedId: null,        // Gallery1.Selected
    mode: 'new',             // Form1.Mode
    editingId: null,
    anexos: [],
    busy: false,
  };

  const comboForm = new CentroCustoCombo($('bm-cc-combo'), { inputId: 'bm-cc-input' });
  const comboEntrada = new CentroCustoCombo($('dlg-cc-combo'), {
    inputId: 'dlg-cc-input', alwaysOpen: true, onChange: () => { $('err-dlg-cc').textContent = ''; },
  });

  // ---------- Navegação ----------
  root.querySelectorAll('[data-action="ir-home"]').forEach((b) => b.addEventListener('click', () => go('home')));
  dlgCC.querySelector('[data-action="ir-home"]').addEventListener('click', () => { dlgCC.close(); go('home'); });
  dlgCC.addEventListener('cancel', (e) => e.preventDefault()); // é preciso escolher ou voltar

  // ---------- Diálogo de entrada (Escolha CC) ----------
  $('dlg-cc-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (comboEntrada.value === null) { // P-07: seleção obrigatória
      $('err-dlg-cc').textContent = 'Escolha um centro de custo para continuar.';
      return;
    }
    state.ccSelecionadoId = comboEntrada.value;
    dlgCC.close();
    $('bm-main').hidden = false; // varFim = true
    renderContexto();
    novoFormulario();
    $('bm-tbody').querySelector('tr')?.focus();
  });

  // ---------- Formulário ----------
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (state.busy) return;
    setBusy(true);
    const dataAnterior = state.mode === 'edit'
      ? state.bms.find((b) => b.id === state.editingId)?.dataAprovacaoCliente ?? null
      : null;
    try {
      const r = await salvarBM(repo, { mode: state.mode, id: state.editingId, draft: lerRascunho() });
      if (!r.ok) {
        renderFieldErrors(form, 'bm', r.errors)?.focus();
        toast('Revise os campos destacados.', { error: true });
        return;
      }
      const aprovadoAgora = !dataAnterior && Boolean(r.registro.dataAprovacaoCliente);
      toast(state.mode === 'edit' ? `BM nº ${r.registro.id} atualizado.` : `BM nº ${r.registro.id} salvo.`);
      if (aprovadoAgora) toast(`Data de aprovação do cliente registrada: ${formatDateTimePtBR(r.registro.dataAprovacaoCliente)}.`);
      await recarregar();
      novoFormulario();
    } catch (err) {
      toast(err.message, { error: true });
      await recarregar();
    } finally {
      setBusy(false);
    }
  });

  $('bm-cancelar').addEventListener('click', () => novoFormulario());

  $('bm-anexos-input').addEventListener('change', (e) => {
    for (const f of e.target.files) state.anexos.push({ nome: f.name, tamanho: f.size });
    e.target.value = '';
    renderAnexosForm();
  });

  // ---------- Exclusão ----------
  $('dlg-excluir-nao').addEventListener('click', () => dlgExcluir.close());
  $('dlg-excluir-sim').addEventListener('click', async () => {
    const id = state.selectedId;
    dlgExcluir.close();
    try {
      await excluirBM(repo, id);
      toast(`BM nº ${id} excluído.`);
      state.selectedId = null;
      await recarregar();
      novoFormulario();
    } catch (err) {
      toast(err.message, { error: true });
    }
  });

  $('dlg-anexos-fechar').addEventListener('click', () => dlgAnexos.close());

  // ---------- Entrada na tela (Refresh + NewForm + OnVisible) ----------
  async function enter() {
    $('bm-main').hidden = true;
    clearFatal();
    try {
      await recarregar();
    } catch (err) {
      showFatal(`Não foi possível carregar os dados: ${err.message}`);
      return;
    }
    state.selectedId = null;
    novoFormulario();
    comboEntrada.setItems(state.centros); // já em ordem de Título
    comboEntrada.setValue(state.ccSelecionadoId);
    $('err-dlg-cc').textContent = '';
    if (!dlgCC.open) dlgCC.showModal();
    $('dlg-cc-input').focus();
  }

  async function recarregar() {
    const dados = await carregarTelaBM(repo);
    Object.assign(state, dados);
    comboForm.setItems(state.centros);
    renderTabela();
  }

  // ---------- Formulário: modos ----------
  function novoFormulario() {
    state.mode = 'new';
    state.editingId = null;
    preencherFormulario(emptyBMDraft(defaultCentroCustoId('new', null, state.ccSelecionadoId)));
    $('bm-form-titulo').textContent = 'Novo BM';
    form.closest('.panel').classList.remove('is-editing');
    renderTabela();
  }

  function editar(id) {
    const bm = state.bms.find((b) => b.id === id);
    if (!bm) return;
    state.selectedId = id;
    state.mode = 'edit';
    state.editingId = id;
    preencherFormulario({
      ...bm,
      centroCustoId: defaultCentroCustoId('edit', bm, state.ccSelecionadoId), // P-01
      valorBM: numberToInputText(bm.valorBM),
      valorAprovado: numberToInputText(bm.valorAprovado),
      glosa: numberToInputText(bm.glosa),
    });
    $('bm-form-titulo').textContent = `Editando BM nº ${id}`;
    form.closest('.panel').classList.add('is-editing');
    renderTabela();
    form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    fields.titulo.focus({ preventScroll: true });
  }

  function preencherFormulario(d) {
    renderFieldErrors(form, 'bm', {});
    comboForm.setValue(d.centroCustoId ?? null);
    fields.titulo.value = d.titulo ?? '';
    fillSelect(fields.ano, state.escolhas.ano, d.ano ?? '');
    fillSelect(fields.mesReferencia, state.escolhas.mesReferencia, d.mesReferencia ?? '');
    fillSelect(fields.status, state.escolhas.status, d.status ?? '');
    fields.valorBM.value = d.valorBM ?? '';
    fields.valorAprovado.value = d.valorAprovado ?? '';
    fields.glosa.value = d.glosa ?? '';
    fields.observacoes.value = d.observacoes ?? '';
    state.anexos = structuredClone(d.anexos ?? []);
    renderAnexosForm();
  }

  function lerRascunho() {
    return {
      centroCustoId: comboForm.value,
      titulo: fields.titulo.value,
      ano: fields.ano.value,
      mesReferencia: fields.mesReferencia.value,
      status: fields.status.value,
      valorBM: fields.valorBM.value,
      valorAprovado: fields.valorAprovado.value,
      glosa: fields.glosa.value,
      observacoes: fields.observacoes.value,
      anexos: structuredClone(state.anexos),
    };
  }

  function setBusy(b) {
    state.busy = b;
    $('bm-salvar').disabled = b;
    $('bm-salvar').textContent = b ? 'Salvando…' : 'Salvar';
  }

  // ---------- Renderização ----------
  function renderContexto() {
    const cc = state.centros.find((c) => c.id === state.ccSelecionadoId);
    $('bm-cc-atual').replaceChildren('Centro de custo padrão para novos BMs: ', el('strong', { text: cc?.titulo ?? '—' }));
  }

  function nomeCC(id) {
    return state.centros.find((c) => c.id === id)?.titulo ?? `(CC ${id} não encontrado)`;
  }

  function renderTabela() {
    const tbody = $('bm-tbody');
    $('bm-vazio').hidden = state.bms.length > 0;
    $('bm-contagem').textContent = `${state.bms.length} ${state.bms.length === 1 ? 'registro' : 'registros'}, do mais recente para o mais antigo`;
    tbody.replaceChildren(...state.bms.map((bm) => {
      const selected = bm.id === state.selectedId;
      const aprovado = bm.status === STATUS_APROVADO_CLIENTE;
      const td = (label, content, cls) => el('td', { 'data-label': label, class: cls }, content);
      const tr = el('tr', {
        tabindex: '0', 'aria-selected': String(selected), dataset: { id: bm.id },
        class: bm.id === state.editingId ? 'is-editing' : null,
        onclick: () => selecionar(bm.id),
        onkeydown: (e) => {
          if (e.target !== tr) return;
          if (e.key === 'Enter') editar(bm.id);
          else if (e.key === ' ') { e.preventDefault(); selecionar(bm.id); }
          else if (e.key === 'ArrowDown') { e.preventDefault(); tr.nextElementSibling?.focus(); }
          else if (e.key === 'ArrowUp') { e.preventDefault(); tr.previousElementSibling?.focus(); }
        },
      }, [
        td('Centro de Custo', nomeCC(bm.centroCustoId), 'cell-cc'),
        td('Nome do Arquivo', bm.titulo, 'cell-file'),
        td('Mês do BM', bm.mesReferencia),
        td('Valor do BM', formatMoneyPtBR(bm.valorBM), 'num'),
        td('Valor Emitido', formatMoneyPtBR(bm.valorEmitido), 'num'),
        td('Valor Aprovado', formatMoneyPtBR(bm.valorAprovado), 'num'),
        td('Status', el('span', { class: `status${aprovado ? ' status--aprovado' : ''}`, text: bm.status })),
        td('Data Criação', formatDateTimePtBR(bm.criado), 'cell-date'),
        el('td', { class: 'actions-cell' }, el('div', { class: 'row-actions' }, [
          iconButton('edit', `Editar BM nº ${bm.id}`, () => editar(bm.id)),
          iconButton('clip', `Ver anexos do BM nº ${bm.id}`, () => verAnexos(bm), { disabled: !bm.anexos?.length }),
          iconButton('trash', `Excluir BM nº ${bm.id}`, () => confirmarExclusao(bm), { danger: true }),
        ])),
      ]);
      return tr;
    }));
  }

  function iconButton(name, label, onClick, { danger = false, disabled = false } = {}) {
    return el('button', {
      type: 'button', class: `icon-btn${danger ? ' icon-btn--danger' : ''}`,
      'aria-label': label, title: label, disabled,
      onclick: (e) => { e.stopPropagation(); onClick(); },
    }, icon(name));
  }

  function selecionar(id) {
    state.selectedId = id;
    renderTabela();
    $('bm-tbody').querySelector(`tr[data-id="${id}"]`)?.focus();
  }

  function confirmarExclusao(bm) {
    selecionar(bm.id);
    $('dlg-excluir-item').textContent = `BM nº ${bm.id} · ${bm.titulo}`;
    dlgExcluir.showModal();
    $('dlg-excluir-nao').focus();
  }

  function verAnexos(bm) {
    selecionar(bm.id);
    $('dlg-anexos-titulo').textContent = `Anexos do BM nº ${bm.id}`;
    $('dlg-anexos-lista').replaceChildren(...(bm.anexos ?? []).map((a) => el('li', { text: a.nome })));
    $('dlg-anexos-nota').textContent = repo.isDemo
      ? 'Na demonstração só os nomes dos arquivos são guardados; não há arquivo para abrir.'
      : '';
    dlgAnexos.showModal();
  }

  function renderAnexosForm() {
    const lista = $('bm-anexos-lista');
    lista.replaceChildren(...state.anexos.map((a, i) => el('li', {}, [
      el('span', { text: a.nome }),
      el('button', {
        type: 'button', class: 'btn btn--outline btn--small', text: 'Remover', 'aria-label': `Remover ${a.nome}`,
        onclick: () => { state.anexos.splice(i, 1); renderAnexosForm(); },
      }),
    ])));
  }

  return { enter };
}
