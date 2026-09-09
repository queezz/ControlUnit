const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('gas drafts do not send; Set validates, clamps steps and preserves edits on polls', () => {
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
    const row = {dataset: {mfc: '1', applied: '1000'}, classList: {toggle() {}},
        querySelector(s) { return s.includes('mfc-input') ? input : s.includes('draft-note') ? note : s.includes('mfc-set') ? buttons.set : buttons.zero; },
        querySelectorAll() { return Object.entries(buttons).filter(([k]) => !['set','zero'].includes(k)).map(([,v]) => v); }};
    const root = {dataset: {}, querySelector() {return null;}, querySelectorAll(s) {return s === '.frow[data-mfc]' ? [row] : [];}};
    const sent = [];
    const ctx = vm.createContext({document: {getElementById(id) {return id === 'control' ? root : null;}}, sent});
    const source = fs.readFileSync('controlunit/web/static/js/control.js', 'utf8');
    vm.runInContext(source.slice(0, source.indexOf('    if (document.readyState')) + 'send = (path, body) => sent.push({path, body}); globalThis.api = {setupGasRow, paintGas}; }());', ctx);
    ctx.api.setupGasRow(row);
    buttons['1000'].click(); assert.equal(+input.value, 2000); assert.equal(sent.length, 0);
    buttons['100'].click(); buttons['10'].click(); buttons['1'].click(); assert.equal(+input.value, 2111);
    ctx.api.paintGas({setpoints: {mfc1_v: 1500}}, {}); assert.equal(+input.value, 2111);
    buttons.set.click(); assert.equal(sent[0].body.mv, 2111);
    input.value = '4900'; buttons['1000'].click(); assert.equal(+input.value, 5000);
    input.value = '0'; buttons['-1000'].click(); assert.equal(+input.value, 0);
    for (const invalid of ['', '-1', '5001', '1.5']) { input.value = invalid; buttons.set.click(); }
    assert.equal(sent.length, 1);
    buttons.zero.click(); assert.equal(sent[1].body.mv, 0);
    assert.equal(row.dataset.applied, '1500');
});
