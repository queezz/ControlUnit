/* The Gas flow card: two draft rows, and the one line the card says when it
 * is folded.
 *
 * A step is a draft and never a command; Set sends a validated integer; a
 * poll arriving mid-edit leaves the reader's typing alone. From 4.14.0 the
 * same poll also writes the card's folded line — applied and measured per
 * gas — from the very numbers it writes into the open card, so the two
 * cannot drift.
 */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function build() {
    const events = {};
    const input = {value: '1000', min: '0', max: '5000', dataset: {},
        addEventListener(k,f) { events[k] = f; },
        checkValidity() { return this.value !== '' && Number.isInteger(Number(this.value)) && +this.value >= 0 && +this.value <= 5000; },
        reportValidity() {}};
    const buttons = {};
    for (const name of ['set', 'zero', '1000', '-1000', '100', '-100', '10', '-10', '1', '-1']) {
        buttons[name] = {dataset: {mfcStep: name}, addEventListener(k,f) { this.click = f; }};
    }
    const note = {};
    // The gas's own name is read from the row it names, so the folded line
    // and the open row cannot come to disagree about which gas this is.
    const name = {textContent: 'H₂'};
    const row = {dataset: {mfc: '1', applied: '1000'}, classList: {toggle() {}},
        querySelector(s) { return s.includes('row-name') ? name
            : s.includes('mfc-input') ? input
            : s.includes('draft-note') ? note
            : s.includes('mfc-set') ? buttons.set : buttons.zero; },
        querySelectorAll() { return Object.entries(buttons).filter(([k]) => !['set','zero'].includes(k)).map(([,v]) => v); }};
    const cells = {fold: {textContent: ''}, applied: {textContent: ''}, measured: {textContent: ''}};
    const root = {dataset: {},
        querySelector(s) {
            if (s.includes('fold-gas')) return cells.fold;
            if (s.includes('mfc-setpoint')) return cells.applied;
            if (s.includes('mfc-measured')) return cells.measured;
            return null;
        },
        querySelectorAll(s) { return s === '.frow[data-mfc]' ? [row] : []; }};
    const sent = [];
    const ctx = vm.createContext({document: {getElementById(id) {return id === 'control' ? root : null;}}, sent});
    const source = fs.readFileSync('controlunit/web/static/js/control.js', 'utf8');
    vm.runInContext(source.slice(0, source.indexOf('    if (document.readyState')) + 'send = (path, body) => sent.push({path, body}); globalThis.api = {setupGasRow, paintGas}; }());', ctx);
    return {api: ctx.api, input, buttons, row, cells, sent};
}

test('gas drafts do not send; Set validates, clamps steps and preserves edits on polls', () => {
    const {api, input, buttons, row, sent} = build();
    api.setupGasRow(row);
    buttons['1000'].click(); assert.equal(+input.value, 2000); assert.equal(sent.length, 0);
    buttons['100'].click(); buttons['10'].click(); buttons['1'].click(); assert.equal(+input.value, 2111);
    api.paintGas({setpoints: {mfc1_v: 1500}}, {}); assert.equal(+input.value, 2111);
    buttons.set.click(); assert.equal(sent[0].body.mv, 2111);
    input.value = '4900'; buttons['1000'].click(); assert.equal(+input.value, 5000);
    input.value = '0'; buttons['-1000'].click(); assert.equal(+input.value, 0);
    for (const invalid of ['', '-1', '5001', '1.5']) { input.value = invalid; buttons.set.click(); }
    assert.equal(sent.length, 1);
    buttons.zero.click(); assert.equal(sent[1].body.mv, 0);
    assert.equal(row.dataset.applied, '1500');
});

test('folded, the Gas flow card says applied and measured per gas', () => {
    // queezz, 2026-09-14: "Hide 'any' card then, not all. I need CONTROL and
    // HIDE WHATEVER IN THE WAY." A folded card still has to be readable.
    const {api, cells, row} = build();
    api.setupGasRow(row);

    api.paintGas({setpoints: {mfc1_v: 1500}}, {MFC1: {value: -0.147}});
    assert.equal(cells.fold.textContent, 'H₂ 1500 / -147 mV');
    // The open card's own two cells carry the same two numbers.
    assert.equal(cells.applied.textContent, '1500 mV');
    assert.equal(cells.measured.textContent, '-147 mV');

    // Nothing measured is an em dash on the folded line too, never a zero.
    api.paintGas({setpoints: {mfc1_v: 0}}, {});
    assert.equal(cells.fold.textContent, 'H₂ 0 / — mV');
    assert.equal(cells.measured.textContent, '—');
});

test('folding is a browser-local memory and never a command', () => {
    // One key per card, and nothing leaves the browser when a card is shut.
    const source = fs.readFileSync('controlunit/web/static/js/control.js', 'utf8');
    const folds = source.slice(source.indexOf('function setupFolds'),
                               source.indexOf('function setupCathodeMode'));
    assert.ok(folds.includes('FOLD_KEY + fold.dataset.fold'));
    assert.ok(!folds.includes('send('));
    assert.ok(!folds.includes('fetch('));
});
