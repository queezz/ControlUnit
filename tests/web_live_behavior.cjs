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
    /* The strip's own folded line: one cell per channel and one trailing
       unit, written by the same paint that writes the cards. */
    const folded = Object.fromEntries(['Bu', 'Bd'].map(name => [name, {textContent: ''}]));
    const units = {textContent: ''};
    const root = {
        classList: {toggle() {}},
        dataset: {},
        querySelector(selector) {
            const readout = selector.match(/^\.readout\[data-readout="(.*?)"\]$/);
            if (readout) return cards[readout[1]] || null;
            if (selector.indexOf('fold-units') !== -1) return units;
            const fold = selector.match(/\[data-fold-readout="(.*?)"\]/);
            return fold ? folded[fold[1]] || null : null;
        },
        querySelectorAll(selector) { return selector === '[data-channel]' ? Object.values(buttons) : []; }
    };
    let saved;
    const context = vm.createContext({
        document: {
            // Only the page's own root; everything else this harness does not
            // model is simply absent, as it is on a page without it.
            querySelector(selector) { return selector === '[data-live]' ? root : null; },
            getElementById(id) { return id === 'chart-bar' ? canvas : null; },
            createComment() { return {}; },
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
    return {api, buttons, canvas, cards, folded, units};
}

/* -- the phone, and the one way out of a mode ---------------------------- *
 *
 * queezz, 2026-09-14, on his phone at the rig: "Observe trapped me. No
 * tri-state toggle anywhere." 4.14.0 had moved the mode switch into the ☰
 * Menu, which lives in the tab bar — and Monitor removes the tab bar, so the
 * switch went with it and the mode's only door was the Escape key.
 *
 * What is asserted below is the general claim, not that one mode: in every
 * mode, at phone width, the switch stands somewhere that mode actually
 * renders. "Renders" is read from the page's own two answers — the `hidden`
 * flag live.js writes, and the `display: none` rules the stylesheet carries
 * for that mode — so the test fails the moment either of them moves under it.
 */
const CSS = fs.readFileSync(
    path.join(__dirname, '../controlunit/web/static/css/controlunit.css'), 'utf8');

function el(spec) {
    const node = Object.assign({
        dataset: {}, className: '', id: '', hidden: false, children: [],
        parentNode: null, attrs: {}, handlers: {},
        classList: {contains() { return false; }, add() {}, remove() {}, toggle() {}},
        setAttribute(name, value) { this.attrs[name] = value; },
        getAttribute(name) { return this.attrs[name]; },
        addEventListener(kind, fn) { this.handlers[kind] = fn; },
        focus() {},
        detach(child) { const i = this.children.indexOf(child); if (i >= 0) this.children.splice(i, 1); },
        appendChild(child) {
            if (child.parentNode) child.parentNode.detach(child);
            child.parentNode = this; this.children.push(child); return child;
        },
        insertBefore(child, ref) {
            if (child.parentNode) child.parentNode.detach(child);
            child.parentNode = this;
            const at = ref ? this.children.indexOf(ref) : -1;
            if (at >= 0) this.children.splice(at, 0, child); else this.children.push(child);
            return child;
        },
        querySelector() { return null; },
        querySelectorAll() { return []; }
    }, spec || {});
    Object.defineProperty(node, 'nextSibling', {
        get() {
            if (!this.parentNode) return null;
            const at = this.parentNode.children.indexOf(this);
            return at >= 0 ? this.parentNode.children[at + 1] || null : null;
        }
    });
    return node;
}

/* The page as a phone sees it: the switch, the two places it can stand, and
   the ancestors whose `display` a mode may take away. */
function phone(startMode) {
    const buttons = ['operate', 'observe', 'monitor'].map(name =>
        el({dataset: {mode: name}}));
    const toolbar = el({className: 'view-toolbar', dataset: {role: 'mode-switch'},
        querySelectorAll() { return buttons; }});
    const menu = el({id: 'main-tabs', ancestors: ['.tabbar', '#main-tabs']});
    const actions = el({dataset: {role: 'mode-actions'}, hidden: true,
        ancestors: ['.mode-actions']});
    const stop = el({dataset: {role: 'stop-all'}});
    const home = el({className: 'control-workspace'});
    home.appendChild(toolbar);
    const away = el({className: 'rail-card'});
    away.appendChild(stop);

    const root = el({
        className: 'page control-workspace', dataset: {live: '', defaultWindow: '300'},
        /* A root-scoped query answers only for what is still inside root.
           The Menu is in the tab bar, outside it — so a control docked there
           is no longer root's to find, and code that looks for it with
           `root.querySelector` can never bring it back. */
        querySelector(selector) {
            if (selector.indexOf('mode-switch') !== -1) {
                return (toolbar.parentNode === home || toolbar.parentNode === actions)
                    ? toolbar : null;
            }
            if (selector.indexOf('mode-actions') !== -1) return actions;
            return null;
        },
        querySelectorAll(selector) {
            if (selector === '[data-mode]') return buttons;
            return [];
        }
    });

    const keys = [];
    const body = {dataset: {mode: startMode || 'operate'}};
    const context = vm.createContext({
        document: {
            querySelector(selector) {
                if (selector === '[data-live]') return root;
                if (selector.indexOf('mode-switch') !== -1) return toolbar;
                if (selector.indexOf('stop-all') !== -1) return stop;
                return null;   // no open Menu, no open drawer, no backdrop
            },
            getElementById(id) { return id === 'main-tabs' ? menu : null; },
            createComment() { return el({}); },
            addEventListener(kind, fn) { if (kind === 'keydown') keys.push(fn); },
            body: body, documentElement: {}
        },
        URL, URLSearchParams,
        window: {
            devicePixelRatio: 1,
            matchMedia(query) { return {matches: query.indexOf('620px') !== -1,
                addEventListener() {}, addListener() {}}; },
            location: {href: 'http://localhost/', search: startMode && startMode !== 'operate'
                ? '?mode=' + startMode : ''},
            history: {pushState(state, title, url) {
                context.window.location.href = url;
                context.window.location.search = new URL(url).search;
            }},
            addEventListener() {}, setInterval() { return 0; }, clearInterval() {},
            setTimeout() { return 0; }, clearTimeout() {}
        },
        fetch() { throw new Error('a mode change must not reach the rig'); },
        getComputedStyle() { return {getPropertyValue() { return ''; }}; },
        localStorage: {setItem() {}, getItem() { return null; }}
    });
    const source = fs.readFileSync(
        path.join(__dirname, '../controlunit/web/static/js/live.js'), 'utf8');
    const end = source.indexOf('    if (document.readyState === "loading")');
    vm.runInContext(source.slice(0, end) +
        'globalThis.phone = {setupModes, applyMode, setMode, modeInAddress};\n}());', context);
    context.phone.setupModes();
    context.phone.applyMode();
    return {api: context.phone, toolbar, menu, actions, buttons, body,
            escape() { keys.forEach(fn => fn({key: 'Escape'})); }};
}

/* Does this mode take the element away? Both answers the page itself gives:
   the flag live.js writes, and the stylesheet's own rule for that mode. */
function rendered(host, mode) {
    if (!host || host.hidden) return false;
    return !(host.ancestors || []).some(selector =>
        CSS.indexOf('body[data-mode="' + mode + '"] ' + selector + ' { display: none') !== -1);
}

test('at phone width every mode keeps the one mode switch on the screen', () => {
    for (const mode of ['operate', 'observe', 'monitor']) {
        const rig = phone();
        rig.api.setMode(mode);
        const host = rig.toolbar.parentNode;
        assert.ok(host, mode + ': the switch has nowhere to stand');
        assert.ok(rendered(host, mode),
            mode + ' renders no mode switch: it is docked in something this '
            + 'mode hides');
        // Reached by a bookmark rather than by a press, the same must hold.
        const direct = phone(mode);
        assert.ok(rendered(direct.toolbar.parentNode, mode),
            mode + ' opened directly renders no mode switch');
    }
});

test('the switch is moved between its homes and never copied', () => {
    const rig = phone();
    const seen = new Set();
    for (const mode of ['observe', 'monitor', 'operate', 'monitor', 'observe']) {
        rig.api.setMode(mode);
        seen.add(rig.toolbar.parentNode);
        // Wherever it stands, it stands there once.
        const homes = [rig.menu, rig.actions];
        const copies = homes.reduce(
            (n, h) => n + h.children.filter(c => c === rig.toolbar).length, 0);
        assert.equal(copies, rig.toolbar.parentNode === rig.menu
            || rig.toolbar.parentNode === rig.actions ? 1 : 0);
    }
    // Monitor's strip and the Menu are two homes, not two switches.
    assert.ok(seen.has(rig.menu) && seen.has(rig.actions));
    assert.equal(rig.buttons.length, 3);
});

test('Escape walks one mode back towards Operate, and stops there', () => {
    // A second, harmless way out beside the switch itself.
    const rig = phone('monitor');
    assert.equal(rig.api.modeInAddress(), 'monitor');
    rig.escape();
    assert.equal(rig.api.modeInAddress(), 'observe');
    rig.escape();
    assert.equal(rig.api.modeInAddress(), 'operate');
    rig.escape();
    assert.equal(rig.api.modeInAddress(), 'operate', 'Operate is the ground floor');

    // And straight out of Observe, which is the mode that trapped him.
    const observing = phone('observe');
    assert.equal(observing.api.modeInAddress(), 'observe');
    observing.escape();
    assert.equal(observing.api.modeInAddress(), 'operate');
});

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


test('folded, the readouts strip carries the same five numbers', () => {
    // queezz, 2026-09-14: "Don't spell readouts. SHOW THEM small in a line
    // with colors." Five values have to stand on one row of a 390px phone,
    // so the folded line writes two significant figures and a plain
    // exponent, and says the unit they share once at its end. Every poll
    // writes it from the same value the card gets.
    const {api, cards, folded, units} = instrument();
    api.paintState(reading({Bu: -0.004, Bd: 0.004}));
    assert.equal(cards.Bu.parts.value.innerHTML, '-4.00×10<sup>-3</sup>');
    assert.equal(folded.Bu.textContent, '-4.0e-3');
    assert.equal(folded.Bd.textContent, '4.0e-3');
    // Said once for the strip, never four times along it.
    assert.equal(units.textContent, 'Torr');

    api.paintState(reading({Bu: 0, Bd: 0.004}));
    assert.equal(folded.Bu.textContent, '0');

    // A channel whose unit the line does not carry keeps its own.
    api.paintState({
        run: {started_at: 100, file: 'cu.csv'}, zeros: {},
        channels: [{name: 'Bu', unit: 'A', value: -0.308},
                   {name: 'Bd', unit: 'Torr', value: 0.004}]
    });
    assert.equal(folded.Bu.textContent, '-0.31 A');
    assert.equal(units.textContent, '');

    // Smoothing moves both together: the card and the folded line read the
    // median of what this browser holds, not the raw value just published.
    api.view.smooth = 5;
    api.paintState(reading({Bu: 9, Bd: 0.004}));
    assert.equal(cards.Bu.parts.value.innerHTML, '-4.00×10<sup>-3</sup>');
    assert.equal(folded.Bu.textContent, '-4.0e-3');
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
