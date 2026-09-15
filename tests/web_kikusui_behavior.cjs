const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

/* The cathode supply's two readouts, as much of them as `paintKikusui`
   touches: two cards of the one strip, each with a value and a state tag,
   and the two cells the strip's own folded line keeps for them. */
function display() {
    const cells = {};
    const cell = (selector) => cells[selector] ||= {textContent: ''};
    const card = {querySelector: cell};
    const root = {querySelector(selector) {
        return selector.indexOf('data-cathode-readout') !== -1 ? card : cell(selector);
    }};
    let timeout, delay;
    const context = vm.createContext({root,
        window: {clearTimeout() { timeout = null; }, setTimeout(fn, ms) { timeout = fn; delay = ms; }}});
    const source = fs.readFileSync(path.join(__dirname, '../controlunit/web/static/js/live.js'), 'utf8');
    vm.runInContext(source.slice(source.indexOf('    var CATHODE_TAGS'), source.indexOf('    function pollState()')), context);
    return {paint: context.paintKikusui, expire() { timeout(); }, delay: () => delay,
        voltage: () => cells['[data-role="value"]'].textContent,
        current: () => cells['[data-role="value"]'].textContent,
        folded: (key) => cells['[data-fold-cathode="' + key + '"] [data-role="fold-value"]'].textContent,
        status: () => cells['[data-role="readout-note"]'].textContent};
}
const fresh = {status: 'ok', voltage_v: 2.4, current_a: 12.0, output_on: 1, age_s: 0.5, stale_after_s: 2};

test('full readouts expire without another response and recover with fresh telemetry', () => {
    const d = display();
    d.paint(fresh);
    // Both cards share one stub, so the last write — the current — is what
    // the value cell holds; the point of the check is the number, not which.
    // Signed always, like every other number on the strip.
    assert.equal(d.current(), ' 12.000');
    assert.equal(d.folded('voltage_v'), '2.40 V');
    assert.equal(d.folded('current_a'), '12.00 A');
    assert.equal(d.status(), 'output on');
    assert.equal(d.delay(), 1500);
    d.expire();
    assert.equal(d.voltage(), '—');
    assert.equal(d.folded('voltage_v'), '—');
    assert.equal(d.status(), 'stale');
    d.paint({...fresh, status: 'dummy'});
    assert.equal(d.current(), ' 12.000');
    assert.match(d.status(), /SIM/);
});

test('loss, stop, missing configuration and aged responses never retain old numbers', () => {
    const d = display();
    const words = {unavailable: 'LAN lost', unreachable: 'unreachable',
        idle: 'not recording', disabled: 'not configured', stopped: 'stopped',
        connecting: 'connecting', error: 'see Log'};
    for (const [status, word] of Object.entries(words)) {
        d.paint(fresh);
        d.paint({...fresh, status});
        assert.equal(d.current(), '—');
        assert.equal(d.folded('current_a'), '—');
        // Four different facts about the supply, each named in its own word
        // and never rendered as a number (WEBUI.md's honesty rule).
        assert.equal(d.status(), word);
    }
    d.paint({...fresh, age_s: 3});
    assert.equal(d.status(), 'stale');
    d.paint({...fresh, current_a: null});
    assert.equal(d.current(), '—');
});
