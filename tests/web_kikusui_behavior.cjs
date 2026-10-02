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
    const card = {querySelector: cell, dataset: {}};
    const root = {querySelector(selector) {
        return selector.indexOf('data-cathode-readout') !== -1 ? card : cell(selector);
    }};
    let timeout, delay;
    const context = vm.createContext({root,
        window: {clearTimeout() { timeout = null; }, setTimeout(fn, ms) { timeout = fn; delay = ms; }}});
    const source = fs.readFileSync(path.join(__dirname, '../controlunit/web/static/js/live.js'), 'utf8');
    vm.runInContext(source.slice(source.indexOf('    var CATHODE_TAGS'), source.indexOf('    function pollState()')), context);
    /* The page's clock, in this test's hands: a reading that goes missing
       is held for ten seconds, and the tests walk through them. */
    let now = 1000000;
    context.kikusuiNow = () => now;
    const lamp = cell('[data-role="cathode-output"]');
    return {paint: context.paintKikusui, expire() { timeout(); }, delay: () => delay,
        wait(ms) { now += ms; },
        lost: () => card.dataset.lost,
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

/* queezz, 2026-10-02, after a run in which the supply answered every one of
 * the recorder's 5,150 polls and the cards blinked all the same: "We should
 * not blink, and we shouldn't change state. But we can gray those Kikusui
 * panels when there is no response for a reasonable time." The page polls
 * once a second and used to give a reading up 1.5 s after it arrived. */
test('a reading that goes missing is held, unchanged, and greys only after ten seconds', () => {
    const d = display();
    d.paint(fresh);
    // Both cards share one stub, so the last write — the current — is what
    // the value cell holds; the point of the check is the number, not which.
    // Signed always, like every other number on the strip.
    assert.equal(d.current(), ' 12.000');
    assert.equal(d.folded('voltage_v'), '2.40 V');
    assert.equal(d.folded('current_a'), '12.00 A');
    assert.equal(d.status(), 'output on');
    assert.equal(d.lost(), 'false');
    assert.equal(d.delay(), 1500);

    // The reading's own two seconds run out with no new answer: nothing on
    // the page moves, and the page looks again when the hold ends.
    d.wait(1500);
    d.expire();
    assert.equal(d.current(), ' 12.000');
    assert.equal(d.folded('voltage_v'), '2.40 V');
    assert.equal(d.status(), 'output on');
    assert.equal(d.lost(), 'false');
    assert.equal(d.lamp.dataset.lamp, 'on');
    assert.equal(d.delay(), 8501);

    // Still nothing after ten seconds: grey, a dash, and the word for why.
    d.wait(8501);
    d.expire();
    assert.equal(d.voltage(), '—');
    assert.equal(d.folded('voltage_v'), '—');
    assert.equal(d.status(), 'stale');
    assert.equal(d.lost(), 'true');
    assert.equal(d.lamp.dataset.lamp, 'unknown');

    // An answer brings everything back at once.
    d.paint({...fresh, status: 'dummy'});
    assert.equal(d.current(), ' 12.000');
    assert.match(d.status(), /SIM/);
    assert.equal(d.lost(), 'false');
});

test('late, lost and unreachable are held; each is named once the hold is over', () => {
    const words = {unavailable: 'LAN lost', unreachable: 'unreachable',
        connecting: 'connecting', stale: 'stale'};
    for (const [status, word] of Object.entries(words)) {
        const d = display();
        d.paint(fresh);
        d.wait(3000);
        d.paint({...fresh, status});
        assert.equal(d.current(), ' 12.000');
        assert.equal(d.status(), 'output on');
        assert.equal(d.lamp.dataset.lamp, 'on');
        d.wait(7001);
        d.paint({...fresh, status});
        assert.equal(d.current(), '—');
        assert.equal(d.folded('current_a'), '—');
        // Different facts about the supply, each named in its own word and
        // never rendered as a number (WEBUI.md's honesty rule).
        assert.equal(d.status(), word);
        assert.equal(d.lost(), 'true');
    }
    // An aged answer is a late one, and is held like one.
    const d = display();
    d.paint(fresh);
    d.wait(1000);
    d.paint({...fresh, age_s: 3});
    assert.equal(d.status(), 'output on');
});

test('a state the rig names outright is painted at once and is not grey', () => {
    const words = {idle: 'not recording', disabled: 'not configured',
        stopped: 'stopped', error: 'see Log', output_off: 'output off sent'};
    for (const [status, word] of Object.entries(words)) {
        const d = display();
        d.paint(fresh);
        d.paint({...fresh, status});
        assert.equal(d.current(), '—');
        assert.equal(d.folded('current_a'), '—');
        assert.equal(d.status(), word);
        // News, not a missing reading: the card is not greyed for it.
        assert.equal(d.lost(), 'false');
        // And nothing is held across it: a gap right after is a gap.
        d.paint({...fresh, status: 'stale'});
        assert.equal(d.current(), '—');
    }
});

test('with nothing ever read there is nothing to hold', () => {
    const d = display();
    d.paint({status: 'unavailable'});
    assert.equal(d.current(), '—');
    assert.equal(d.status(), 'LAN lost');
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
        d.wait(10001);                      // past the hold a missing reading gets
        d.paint({...fresh, status});
        // No colour at all: an unmeasured supply is never rendered in one a
        // reader could take for a state.
        assert.equal(d.lamp.dataset.lamp, 'unknown');
        assert.equal(d.word(), word);
        assert.equal(d.lamp.dataset.next, 'off');
        assert.equal(d.lamp.attrs['aria-label'], "Turn the supply's output off");
        assert.equal(d.lamp.disabled, false);
    }
    // An answer that stays away is no answer: the lamp goes dim with the
    // cards, once the hold is over.
    d.paint(fresh);
    assert.equal(d.lamp.dataset.lamp, 'on');
    d.wait(1500);
    d.expire();
    assert.equal(d.lamp.dataset.lamp, 'on');
    d.wait(8501);
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
