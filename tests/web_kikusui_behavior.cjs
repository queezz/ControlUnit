const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

/* The cathode supply's two readouts, as much of them as `paintKikusui`
   touches: two cards of the one strip, each with a value and a state tag,
   the two cells the strip's own folded line keeps for them, and the output
   lamp on the Cathode card's heading line, which is painted from the very
   same reading so the two can never say different things. */
function display() {
    const cells = {};
    const cell = (selector) => cells[selector] ||= {
        textContent: '', dataset: {}, attrs: {}, disabled: true,
        setAttribute(name, value) { this.attrs[name] = value; },
        querySelector: (inner) => cell(selector + ' ' + inner)
    };
    const card = {querySelector: cell};
    const root = {querySelector(selector) {
        return selector.indexOf('data-cathode-readout') !== -1 ? card : cell(selector);
    }};
    let timeout, delay;
    const context = vm.createContext({root,
        window: {clearTimeout() { timeout = null; }, setTimeout(fn, ms) { timeout = fn; delay = ms; }}});
    const source = fs.readFileSync(path.join(__dirname, '../controlunit/web/static/js/live.js'), 'utf8');
    vm.runInContext(source.slice(source.indexOf('    var CATHODE_TAGS'), source.indexOf('    function pollState()')), context);
    const lamp = cell('[data-role="cathode-output"]');
    return {paint: context.paintKikusui, expire() { timeout(); }, delay: () => delay,
        lamp,
        /* The state's word, written onto the lamp's own title — the heading
           row has no width to print it on, and the readout cards above carry
           it in full. */
        word: () => lamp.title,
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

/* The output lamp: three states, and the press each of them offers.
 *
 * Owner decision 2026-09-15, live: "Kikusui has LAN now, I want the one-off
 * signal button in our control… Then we turn that one off no matter the dac
 * voltage", and "Off and on. Why not? Then we have full cathode control when
 * powered". The lamp is one element for both jobs — it says what the supply
 * answers and pressing it sends the opposite — so what is checked here is the
 * pair: the state shown, and the direction the press would take.
 */
test('the lamp is green with the output on, and would press off', () => {
    const d = display();
    d.paint(fresh);
    assert.equal(d.lamp.dataset.lamp, 'on');
    assert.equal(d.word(), 'output on');
    assert.equal(d.lamp.dataset.next, 'off');
    assert.equal(d.lamp.attrs['aria-label'], "Turn the supply's output off");
    // Never a state display: the colour and the title say the state, and
    // the label says what the press will do.
    assert.equal(d.lamp.attrs['aria-pressed'], 'false');
    // Off is the press no gate stands in front of, and this paint runs on its
    // own timer between polls, so it may never leave that press switched off.
    assert.equal(d.lamp.disabled, false);
});

test('the lamp is grey with the output off, and would press on', () => {
    const d = display();
    d.paint({...fresh, output_on: 0});
    assert.equal(d.lamp.dataset.lamp, 'off');
    assert.equal(d.word(), 'output off');
    assert.equal(d.lamp.dataset.next, 'on');
    assert.equal(d.lamp.attrs['aria-label'], "Turn the supply's output on");
    // On is a setter: whether it may be pressed is the gate's answer, in
    // control.js, and this paint does not touch it.
    assert.equal(d.lamp.disabled, true);
    assert.equal(d.lamp.attrs['aria-pressed'], 'false');
});

test('with no fresh answer the lamp is dim, says why, and presses only off', () => {
    const d = display();
    for (const [status, word] of Object.entries({
        idle: 'not recording', unavailable: 'LAN lost', stale: 'stale',
        disabled: 'not configured', stopped: 'stopped', unreachable: 'unreachable',
        output_off: 'output off sent', output_on_failed: 'output on FAILED'
    })) {
        d.paint(fresh);
        d.paint({...fresh, status});
        // No colour at all: an unmeasured supply is never rendered in one a
        // reader could take for a state.
        assert.equal(d.lamp.dataset.lamp, 'unknown');
        assert.equal(d.word(), word);
        assert.equal(d.lamp.dataset.next, 'off');
        assert.equal(d.lamp.attrs['aria-label'], "Turn the supply's output off");
        assert.equal(d.lamp.disabled, false);
    }
    // An aged answer is no answer: the lamp goes dim with the cards.
    d.paint(fresh);
    assert.equal(d.lamp.dataset.lamp, 'on');
    d.expire();
    assert.equal(d.lamp.dataset.lamp, 'unknown');
    assert.equal(d.lamp.dataset.next, 'off');
});

test('a simulated supply lights the lamp and its word says SIMULATED', () => {
    const d = display();
    d.paint({...fresh, status: 'dummy'});
    assert.equal(d.lamp.dataset.lamp, 'on');
    assert.equal(d.word(), 'SIM · output on');
    assert.equal(d.lamp.dataset.next, 'off');
});
