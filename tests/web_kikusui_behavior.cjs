const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function display() {
    const cells = {};
    const panel = {querySelector(s) { return cells[s] ||= {textContent: ''}; }};
    let timeout, delay;
    const context = vm.createContext({root: {querySelector() { return panel; }},
        window: {clearTimeout() { timeout = null; }, setTimeout(fn, ms) { timeout = fn; delay = ms; }}});
    const source = fs.readFileSync(path.join(__dirname, '../controlunit/web/static/js/live.js'), 'utf8');
    vm.runInContext(source.slice(source.indexOf('    var kikusuiExpiry'), source.indexOf('    function pollState()')), context);
    return {paint: context.paintKikusui, expire() { timeout(); }, delay: () => delay,
        voltage: () => cells['[data-kikusui-readout="voltage_v"] [data-role="value"]'].textContent,
        current: () => cells['[data-kikusui-readout="current_a"] [data-role="value"]'].textContent,
        status: () => cells['[data-role="kikusui-status"]'].textContent};
}
const fresh = {status: 'ok', voltage_v: 2.4, current_a: 12.0, output_on: 1, age_s: 0.5, stale_after_s: 2};

test('full readouts expire without another response and recover with fresh telemetry', () => {
    const d = display();
    d.paint(fresh);
    assert.equal(d.voltage(), '2.400');
    assert.equal(d.current(), '12.000');
    assert.equal(d.delay(), 1500);
    d.expire();
    assert.equal(d.voltage(), '—');
    assert.equal(d.status(), 'Telemetry stale');
    d.paint({...fresh, status: 'dummy'});
    assert.equal(d.current(), '12.000');
    assert.match(d.status(), /SIMULATED/);
});

test('loss, stop, missing configuration and aged responses never retain old numbers', () => {
    const d = display();
    for (const status of ['unavailable', 'unreachable', 'idle', 'disabled', 'stopped']) {
        d.paint(fresh);
        d.paint({...fresh, status});
        assert.equal(d.current(), '—');
    }
    d.paint({...fresh, age_s: 3});
    assert.equal(d.status(), 'Telemetry stale');
    d.paint({...fresh, current_a: null});
    assert.equal(d.current(), '—');
});
