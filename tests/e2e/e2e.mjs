/**
 * Teste ponta a ponta das três telas contra o comportamento mapeado.
 * Requer: npm install (instala o Playwright) e npx playwright install chromium.
 * Uso: npm run test:e2e
 */
import { chromium } from 'playwright';
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' };

const server = http.createServer(async (req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^([\\/])+/, '');
  try {
    const file = join(ROOT, path || 'index.html');
    if (!file.startsWith(ROOT)) throw new Error('fora da raiz');
    res.writeHead(200, { 'Content-Type': TYPES[extname(file)] ?? 'application/octet-stream' });
    res.end(await readFile(file));
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise((r) => server.listen(0, r));
const base = `http://localhost:${server.address().port}/`;

const browser = await chromium.launch();
const results = [];
async function step(name, fn) {
  try { await fn(); results.push(['ok', name]); }
  catch (e) { results.push(['FALHOU', `${name}: ${e.message.split('\n')[0]}`]); }
}

async function run(viewport) {
  const page = await browser.newPage({ viewport });
  const erros = [];
  page.on('pageerror', (e) => erros.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') erros.push(m.text()); });
  const tag = `[${viewport.width}px]`;
  const ids = async () => page.$$eval('#bm-tbody tr', (trs) => trs.map((t) => Number(t.dataset.id)));

  await page.goto(base);

  await step(`${tag} Tela Inicial mostra marca, botões e aviso de demonstração`, async () => {
    assert.equal(await page.textContent('.home__wordmark'), 'SIM');
    assert.ok(await page.isVisible('[data-action="ir-bm"]'));
    assert.ok(await page.isVisible('[data-action="ir-cadastro"]'));
    assert.ok(await page.isVisible('#demo-banner'));
  });

  await step(`${tag} BM Mensal abre o diálogo de CC e esconde a lista`, async () => {
    await page.click('[data-action="ir-bm"]');
    await page.waitForSelector('#dlg-cc[open]');
    assert.equal(await page.isVisible('#bm-main'), false);
    const titulos = await page.$$eval('#dlg-cc-combo [role=option] span', (s) => s.map((x) => x.textContent));
    assert.deepEqual(titulos, [...titulos].sort((a, b) => a.localeCompare(b, 'pt-BR')));
  });

  await step(`${tag} OK sem seleção é bloqueado (P-07)`, async () => {
    await page.click('#dlg-cc-ok');
    assert.match(await page.textContent('#err-dlg-cc'), /Escolha/);
    assert.ok(await page.isVisible('#dlg-cc[open]'));
  });

  await step(`${tag} Busca do CC filtra pelo cliente`, async () => {
    await page.fill('#dlg-cc-input', 'beta');
    const n = await page.$$eval('#dlg-cc-combo [role=option]', (o) => o.length);
    assert.equal(n, 1);
    await page.fill('#dlg-cc-input', '102 Cozinha'); // título não é campo de busca
    assert.equal(await page.$$eval('#dlg-cc-combo [role=option]', (o) => o.length), 0);
    await page.fill('#dlg-cc-input', 'beta');
    await page.click('#dlg-cc-combo [role=option]');
    await page.click('#dlg-cc-ok');
    await page.waitForSelector('#bm-main:not([hidden])');
  });

  await step(`${tag} Lista em ID decrescente e valores pt-BR`, async () => {
    const lista = await ids();
    assert.deepEqual(lista, [...lista].sort((a, b) => b - a));
    const valor = await page.textContent('#bm-tbody tr[data-id="1"] td:nth-child(4)');
    assert.equal(valor.trim(), '152.340,50');
    const data = await page.textContent('#bm-tbody tr[data-id="1"] td:nth-child(8)');
    assert.match(data, /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}$/);
  });

  await step(`${tag} Novo BM vem com o CC escolhido no diálogo`, async () => {
    assert.match(await page.inputValue('#bm-cc-input'), /CC-DEMO 102/);
  });

  await step(`${tag} Salvar vazio mostra erros de obrigatoriedade`, async () => {
    await page.click('#bm-salvar');
    for (const k of ['titulo', 'ano', 'mesReferencia', 'status', 'valorBM', 'valorAprovado', 'anexos']) {
      assert.notEqual((await page.textContent(`#err-bm-${k}`)).trim(), '', `sem erro em ${k}`);
    }
    assert.equal((await page.textContent('#err-bm-glosa')).trim(), '');
  });

  await step(`${tag} Criar BM aprovado grava data e aparece no topo`, async () => {
    await page.fill('#bm-titulo', 'BM_TESTE_E2E.pdf');
    await page.selectOption('#bm-ano', '2026');
    await page.selectOption('#bm-mes', 'Outubro');
    await page.selectOption('#bm-status', 'BM Aprovado pelo Cliente');
    await page.fill('#bm-valor', '1.234,56');
    await page.fill('#bm-aprovado', '1200');
    await page.fill('#bm-glosa', '34,56');
    await page.setInputFiles('#bm-anexos-input', { name: 'medicao.pdf', mimeType: 'application/pdf', buffer: Buffer.from('x') });
    await page.click('#bm-salvar');
    await page.waitForSelector('#bm-tbody tr[data-id="7"]');
    assert.equal((await ids())[0], 7);
    assert.equal((await page.textContent('#bm-tbody tr[data-id="7"] td:nth-child(4)')).trim(), '1.234,56');
    assert.match(await page.textContent('#toast-region'), /Data de aprovação do cliente registrada/);
    assert.equal(await page.inputValue('#bm-titulo'), ''); // voltou a novo
  });

  await step(`${tag} Edição carrega o CC do próprio registro (P-01)`, async () => {
    await page.click('#bm-tbody tr[data-id="5"] button[aria-label^="Editar"]');
    assert.match(await page.textContent('#bm-form-titulo'), /Editando BM nº 5/);
    assert.match(await page.inputValue('#bm-cc-input'), /CC-DEMO 105/); // não o 102 do diálogo
    assert.equal(await page.inputValue('#bm-valor'), '210.450,20');
  });

  await step(`${tag} Salvar edição atualiza a linha sem mudar o CC`, async () => {
    await page.fill('#bm-obs', 'Editado no teste');
    await page.fill('#bm-aprovado', '0');
    await page.click('#bm-salvar');
    await page.waitForFunction(() => document.querySelector('#bm-form-titulo').textContent === 'Novo BM');
    assert.match(await page.textContent('#bm-tbody tr[data-id="5"] td:nth-child(1)'), /CC-DEMO 105/);
  });

  await step(`${tag} Cancelar Edição volta ao modo novo sem gravar`, async () => {
    await page.click('#bm-tbody tr[data-id="4"] button[aria-label^="Editar"]');
    await page.fill('#bm-titulo', 'NAO_DEVE_GRAVAR');
    await page.click('#bm-cancelar');
    assert.equal(await page.textContent('#bm-form-titulo'), 'Novo BM');
    assert.notEqual((await page.textContent('#bm-tbody tr[data-id="4"] td:nth-child(2)')).trim(), 'NAO_DEVE_GRAVAR');
  });

  await step(`${tag} Exclusão: Não mantém, Sim remove`, async () => {
    await page.click('#bm-tbody tr[data-id="3"] button[aria-label^="Excluir"]');
    await page.waitForSelector('#dlg-excluir[open]');
    assert.match(await page.textContent('#dlg-excluir'), /Sua ação não terá volta/);
    await page.click('#dlg-excluir-nao');
    assert.ok((await ids()).includes(3));
    await page.click('#bm-tbody tr[data-id="3"] button[aria-label^="Excluir"]');
    await page.click('#dlg-excluir-sim');
    await page.waitForFunction(() => !document.querySelector('#bm-tbody tr[data-id="3"]'));
  });

  await step(`${tag} Anexos abrem lista com aviso de demonstração`, async () => {
    await page.click('#bm-tbody tr[data-id="1"] button[aria-label^="Ver anexos"]');
    await page.waitForSelector('#dlg-anexos[open]');
    assert.match(await page.textContent('#dlg-anexos-lista'), /BM_DEMO_101_2026_07/);
    assert.match(await page.textContent('#dlg-anexos-nota'), /demonstração/);
    await page.click('#dlg-anexos-fechar');
  });

  await step(`${tag} Cadastro valida e inclui; novo CC aparece no BM Mensal`, async () => {
    await page.click('#screen-bm [data-action="ir-home"]');
    await page.click('[data-action="ir-cadastro"]');
    await page.click('#cc-salvar');
    for (const k of ['titulo', 'cliente', 'inicioMedicao', 'fimMedicao', 'email']) {
      assert.notEqual((await page.textContent(`#err-cc-${k}`)).trim(), '', `sem erro em ${k}`);
    }
    await page.fill('#cc-titulo', 'CC-DEMO 200 Teste');
    await page.fill('#cc-cliente', 'Cliente Teste Zeta');
    await page.fill('#cc-inicio', '1');
    await page.fill('#cc-fim', '30');
    await page.fill('#cc-email', 'teste@exemplo.invalid');
    await page.click('#cc-salvar');
    assert.equal(await page.inputValue('#cc-titulo'), '');
    await page.click('#screen-cadastro [data-action="ir-home"]');
    await page.click('[data-action="ir-bm"]');
    await page.fill('#dlg-cc-input', 'zeta');
    assert.match(await page.textContent('#dlg-cc-combo'), /CC-DEMO 200 Teste/);
  });

  await step(`${tag} Sem rolagem horizontal da página`, async () => {
    await page.click('#dlg-cc-combo [role=option]');
    await page.click('#dlg-cc-ok');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert.ok(overflow <= 1, `excesso de ${overflow}px`);
  });

  await page.screenshot({ path: `/tmp/sim-bm-${viewport.width}.png`, fullPage: true });
  await step(`${tag} Sem erros no console`, async () => assert.deepEqual(erros, []));
  await page.close();
}

try {
  await run({ width: 1366, height: 900 });
  await run({ width: 390, height: 844 });
} finally {
  await browser.close();
  server.close();
}

for (const [s, n] of results) console.log(`${s.padEnd(7)} ${n}`);
const falhas = results.filter(([s]) => s !== 'ok').length;
console.log(`\n${results.length - falhas}/${results.length} verificações aprovadas`);
process.exit(falhas ? 1 : 0);
