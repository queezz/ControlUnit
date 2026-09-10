// Run with: node --test tests/web_live_behavior.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

/* A readout card, as much of one as paintState touches: the three elements
   it writes, and a tag whose box has a width. `room` is how many pixels the
   tag's own track holds — the narrowest card this page makes leaves it about
   50, which is the case the fit-down in paintState exists for. The width
   model is deliberately crude and monotonic in the text's length; what is
   being tested is which words the card ends up carrying, not typography. */
function readoutCard(name, room) {
    const value = {innerHTML: '', textContent: ''};
    const unit = {textContent: ''};
    const note = {
        text: '', below: false,
        classList: {toggle(cls, on) { note.below = !!on; }},
        get textContent() { return note.text; },
        set textContent(next) { note.text = next; },
        get scrollWidth() { return note.text.length * 5; },
        get clientWidth() { return room === undefined ? 200 : room; }
    };
    return {
        dataset: {readout: name},
        classList: {toggle() {}},
        parts: {value, unit, note},
        querySelector(selector) {
            if (selector.indexOf('readout-note') !== -1) return note;
            if (selector.indexOf('value') !== -1) return value;
            if (selector.indexOf('unit') !== -1) return unit;
            return null;
        }
    };
}

/* `cardRoom` is one width for every card, or a width per channel — a card
   whose unit is "Torr" leaves its tag less room than one whose unit is "A",
   in the same strip. */
function instrument(cardRoom) {
    const roomFor = (name) => (cardRoom && typeof cardRoom === 'object') ? cardRoom[name] : cardRoom;
    const cards = Object.fromEntries(['Bu', 'Bd'].map(name => [name, readoutCard(name, roomFor(name))]));
    const buttons = Object.fromEntries(['Bu', 'Bd'].map(name => [name, {
        dataset: {channel: name}, listeners: {},
        setAttribute() {},
        addEventListener(event, fn) { this.listeners[event] = fn; },
        querySelector() { return {textContent: ''}; }
    }]));
    const legend = {
        querySelector(selector) { return buttons[selector.match(/"(.*?)"/)[1]]; },
        querySelectorAll() { return Object.values(buttons); }
    };
    const canvas = {
        dataset: {channels: 'Bu,Bd', height: '220'}, style: {}, clientWidth: 600,
        parentNode: {classList: {toggle() {}}, querySelector() { return legend; }},
        getContext() { return new Proxy({}, {get: () => () => {}}); }
    };
    const root = {
        classList: {toggle() {}},
        dataset: {},
        querySelector(selector) {
            const readout = selector.match(/^\.readout\[data-readout="(.*?)"\]$/);
            return readout ? cards[readout[1]] || null : null;
        },
        querySelectorAll(selector) { return selector === '[data-channel]' ? Object.values(buttons) : []; }
    };
    let saved;
    const context = vm.createContext({
        document: {
            querySelector() { return root; },
            getElementById(id) { return id === 'chart-bar' ? canvas : null; },
            body: {dataset: {}}, documentElement: {}
        },
        URL, URLSearchParams,
        window: {devicePixelRatio: 2, location: {href: 'http://localhost/', search: ''},
            history: {pushState(state, title, url) {
                context.window.location.href = url;
                context.window.location.search = new URL(url).search;
            }}},
        fetch() { throw new Error('Mode changes must not send requests'); },
        getComputedStyle() { return {getPropertyValue() { return ''; }}; },
        localStorage: {setItem(k, v) { saved = v; }, getItem() { return saved; }}
    });
    const source = fs.readFileSync(path.join(__dirname, '../controlunit/web/static/js/live.js'), 'utf8');
    // Exercise production handlers and drawing decisions without starting timers.
    const end = source.indexOf('    if (document.readyState === "loading")');
    vm.runInContext(source.slice(0, end) +
        'globalThis.instrument = {append, draw, drawAll, setupRails, applyPreset, view, recall, remember, setMode, modeInAddress, paintState};\n}());', context);
    const api = context.instrument;
    api.append({to: 4, channels: {Bu: [[1, -0.004], [2, -0.004], [3, -0.004], [4, -0.004]],
        Bd: [[1, 0.001], [2, 0.002], [3, 0.003], [4, 0.004]]}});
    api.setupRails();
    api.drawAll();
    return {api, buttons, canvas, cards};
}

/* One rig reading, shaped as /api/state answers it. The run key never moves
   between calls, so a repaint is a repaint and not a new run. */
function reading(values, zeros) {
    return {
        run: {started_at: 100, file: 'cu.csv'},
        zeros: zeros || {},
        channels: Object.keys(values).map(name => ({name: name, unit: 'Torr', value: values[name]}))
    };
}

test('explicit flat-curve restoration survives polls, off/on and saved preferences', () => {
    const {api, buttons} = instrument();
    assert.equal(buttons.Bu.dataset.curveState, 'flat');
    buttons.Bu.listeners.click();
    assert.equal(buttons.Bu.dataset.curveState, 'drawn');
    api.drawAll();
    assert.equal(buttons.Bu.dataset.curveState, 'drawn');
    api.view.pinned = {};
    api.recall();
    api.drawAll();
    assert.equal(buttons.Bu.dataset.curveState, 'drawn');
    buttons.Bu.listeners.click();
    assert.equal(buttons.Bu.dataset.curveState, 'off');
    buttons.Bu.listeners.click();
    assert.equal(buttons.Bu.dataset.curveState, 'drawn');
});

test('a preset restores automatic suppression; nonpositive log data stays absent', () => {
    const {api, buttons} = instrument();
    buttons.Bu.listeners.click();
    api.applyPreset({dataset: {channels: 'Bu,Bd'}});
    assert.equal(buttons.Bu.dataset.curveState, 'flat');
    buttons.Bu.listeners.click();
    api.view.barLog = true;
    api.drawAll();
    assert.equal(buttons.Bu.dataset.curveState, 'nonpositive');
    assert.equal(buttons.Bd.dataset.curveState, 'drawn');
});


test('modes preserve curve choices and canonical URLs without hardware requests', () => {
    const {api, buttons} = instrument();
    buttons.Bu.listeners.click();
    const choices = JSON.stringify(api.view);
    for (const mode of ['observe', 'monitor', 'operate']) {
        api.setMode(mode);
        assert.equal(api.modeInAddress(), mode);
        assert.equal(JSON.stringify(api.view), choices);
        assert.equal(buttons.Bu.dataset.curveState, 'drawn');
    }
});


test('all-nonpositive log panel distinguishes excluded values from missing data', () => {
    const {api, buttons} = instrument();
    api.view.channels.Bd = false;
    api.view.barLog = true;
    api.drawAll();
    assert.equal(buttons.Bu.dataset.curveState, 'nonpositive');
    api.view.barLog = false;
    api.drawAll();
    assert.equal(buttons.Bu.dataset.curveState, 'drawn');
});


test('vessel overlay retains signed pressures and independent saved axes', () => {
    const {api, canvas} = instrument();
    api.append({to: 8, channels: {Pu: [[5, 0.001], [6, 0.002], [7, 0.003], [8, 0.004]],
        Bu: [[5, -0.001], [6, 0.001], [7, 0.002], [8, 0.003]]}});
    canvas.dataset.channels = 'Pu,Bu';
    const result = api.draw(canvas, false);
    assert.deepEqual(Array.from(result.series, s => s.name), ['Pu', 'Bu']);
    assert.equal(result.series[0].lo, 0.001);
    assert.equal(result.series[1].lo, -0.004);
    api.view.pressureGroup = 'vessel';
    api.view.upstreamLog = false;
    api.view.downstreamLog = true;
    api.remember();
    api.view.pressureGroup = 'gauge';
    api.view.upstreamLog = true;
    api.recall();
    assert.equal(api.view.pressureGroup, 'vessel');
    assert.equal(api.view.upstreamLog, false);
    assert.equal(api.view.downstreamLog, true);
    assert.equal(api.view.barLog, false);
});


test('a readout is a number: the value slot never carries a word', () => {
    const {api, cards} = instrument();
    const Bu = cards.Bu.parts;
    api.paintState(reading({Bu: -0.004, Bd: 0.004}));
    // The signed number and its unit, not "Below zero" where the number goes
    // (queezz, 2026-09-10: "text jumps to numbers and back, terrible").
    assert.equal(Bu.value.innerHTML, '-4.00×10<sup>-3</sup>');
    assert.equal(Bu.unit.textContent, 'Torr');
    api.paintState(reading({Bu: 0.004, Bd: 0.004}));
    assert.equal(Bu.value.innerHTML, '4.00×10<sup>-3</sup>');
    assert.equal(Bu.unit.textContent, 'Torr');
});


test('the state tag says zeroed, below zero, both, or nothing at all', () => {
    const {api, cards} = instrument();
    const note = cards.Bu.parts.note;

    api.paintState(reading({Bu: 0.004, Bd: 0.004}));
    assert.equal(note.textContent, '');
    assert.equal(note.below, false);

    api.paintState(reading({Bu: -0.004, Bd: 0.004}));
    assert.equal(note.textContent, 'below zero');
    assert.equal(note.below, true);

    api.paintState(reading({Bu: 0.004, Bd: 0.004}, {Bu: 0.05, Bd: 0}));
    assert.equal(note.textContent, 'zeroed');
    assert.equal(note.below, false);

    api.paintState(reading({Bu: -0.004, Bd: 0.004}, {Bu: 0.05, Bd: 0}));
    assert.equal(note.textContent, 'zeroed · below zero');
    assert.equal(note.below, true);

    // A baseline of zero is no baseline held, and says nothing.
    api.paintState(reading({Bu: 0.004, Bd: 0.004}, {Bu: 0, Bd: 0}));
    assert.equal(note.textContent, '');
});


test('a tag too wide for its card shortens rather than clips', () => {
    // Five cards across the Operate column leave the tag 55px at 1280 and
    // 39px at 1200. Neither holds both words; the narrow one does not hold
    // "below zero" either. The number is unaffected at every width.
    const inACardOf = (room, expected) => {
        const rig = instrument(room);
        const Bu = rig.cards.Bu.parts;
        rig.api.paintState(reading({Bu: -0.004, Bd: 0.004}, {Bu: 0.05, Bd: 0}));
        assert.equal(Bu.note.textContent, expected);
        assert.equal(Bu.value.innerHTML, '-4.00×10<sup>-3</sup>');
        // A tag that fits is never traded away for a shorter one.
        rig.api.paintState(reading({Bu: 0.004, Bd: 0.004}, {Bu: 0.05, Bd: 0}));
        assert.equal(Bu.note.textContent, 'zeroed');
    };
    inACardOf(200, 'zeroed · below zero');
    inACardOf(55, 'below zero');
    inACardOf(40, 'below 0');
});


test('one strip says the state one way, set by its narrowest card', () => {
    // A row reading "below zero" on one card and "below 0" on the next is
    // sloppiness, not two different facts.
    const {api, cards} = instrument({Bu: 40, Bd: 200});
    api.paintState(reading({Bu: -0.004, Bd: -0.004}));
    assert.equal(cards.Bu.parts.note.textContent, 'below 0');
    assert.equal(cards.Bd.parts.note.textContent, 'below 0');
    // Room enough on both, and both say it the long way.
    const roomy = instrument({Bu: 200, Bd: 200});
    roomy.api.paintState(reading({Bu: -0.004, Bd: -0.004}));
    assert.equal(roomy.cards.Bu.parts.note.textContent, 'below zero');
    assert.equal(roomy.cards.Bd.parts.note.textContent, 'below zero');
});


test('the wording follows the window, never the numbers of the moment', () => {
    // A tag whose length depended on how many cards happened to be zeroed
    // would reword itself while a Baratron wandered across zero, which is
    // the flicker this whole change exists to end.
    const {api, cards} = instrument({Bu: 55, Bd: 55});
    const said = [];
    for (const state of [
        reading({Bu: -0.004, Bd: 0.004}),
        reading({Bu: -0.004, Bd: -0.004}, {Bu: 0.05, Bd: 0.01}),
        reading({Bu: -0.004, Bd: 0.004}, {Bd: 0.01}),
        reading({Bu: -0.004, Bd: 0.004})
    ]) {
        api.paintState(state);
        said.push(cards.Bu.parts.note.textContent);
    }
    // Bu is below zero throughout and says so the same way throughout,
    // whatever the card beside it is doing.
    assert.deepEqual(said, ['below zero', 'below zero', 'below zero', 'below zero']);
});
