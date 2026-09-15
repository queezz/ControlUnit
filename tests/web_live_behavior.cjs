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

/* The number as the card renders it: mantissa, then `×10-` small, then the
   decade at the mantissa's own size (owner sketch, 2026-09-15: "×10- small,
   the n in ×10-n is BIG"), a minus on a negative and a blank of the same
   width (a figure space) on a positive, so a value crossing zero moves no
   digit sideways and no pressure wears a plus (owner, 2026-09-15: "+ reads
   there as a warning"). */
const MINUS_FOUR_MILLI = '-4.00<span class="readout-times">×10-</span><span class="readout-exp">3</span>';
const PLUS_FOUR_MILLI = ' 4.00<span class="readout-times">×10-</span><span class="readout-exp">3</span>';

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
    assert.equal(Bu.value.innerHTML, MINUS_FOUR_MILLI);
    assert.equal(Bu.unit.textContent, 'Torr');
    api.paintState(reading({Bu: 0.004, Bd: 0.004}));
    assert.equal(Bu.value.innerHTML, PLUS_FOUR_MILLI);
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
    assert.equal(cards.Bu.parts.value.innerHTML, MINUS_FOUR_MILLI);
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
    assert.equal(cards.Bu.parts.value.innerHTML, MINUS_FOUR_MILLI);
    assert.equal(folded.Bu.textContent, '-4.0e-3');
});


test('the state tag says zeroed, or nothing at all', () => {
    // queezz, 2026-09-15: "We have a sign for it… I know the - from +, don't
    // I?" So `below zero` is gone from the card and the sign in the digits
    // is what says it — one copy of the fact, not two. `zeroed` stays,
    // because nothing else on the card says a baseline is held.
    const {api, cards} = instrument();
    const note = cards.Bu.parts.note;

    api.paintState(reading({Bu: 0.004, Bd: 0.004}));
    assert.equal(note.textContent, '');

    api.paintState(reading({Bu: -0.004, Bd: 0.004}));
    assert.equal(note.textContent, '');
    assert.equal(cards.Bu.parts.value.innerHTML, MINUS_FOUR_MILLI);

    api.paintState(reading({Bu: 0.004, Bd: 0.004}, {Bu: 0.05, Bd: 0}));
    assert.equal(note.textContent, 'zeroed');
    assert.equal(cards.Bu.parts.value.innerHTML, PLUS_FOUR_MILLI);

    // Zeroed and negative is still one word, and the sign carries the rest.
    api.paintState(reading({Bu: -0.004, Bd: 0.004}, {Bu: 0.05, Bd: 0}));
    assert.equal(note.textContent, 'zeroed');

    // A baseline of zero is no baseline held, and says nothing.
    api.paintState(reading({Bu: 0.004, Bd: 0.004}, {Bu: 0, Bd: 0}));
    assert.equal(note.textContent, '');
});


test('the sign is written in every state, so a number never jumps', () => {
    // The one thing that now says a reading is negative is the digit column
    // itself, so it must be there whichever side of zero the value is on.
    const {api, cards} = instrument();
    const Bu = cards.Bu.parts;
    api.paintState(reading({Bu: -0.004, Bd: 0.004}));
    assert.match(Bu.value.innerHTML, /^-4\.00/);
    api.paintState(reading({Bu: 0.004, Bd: 0.004}));
    assert.match(Bu.value.innerHTML, /^ 4\.00/);
    // A plain reading — a current in amperes — is signed the same way.
    api.paintState({run: {started_at: 100, file: 'cu.csv'}, zeros: {},
        channels: [{name: 'Bu', unit: 'A', value: 0.308},
                   {name: 'Bd', unit: 'Torr', value: 0.004}]});
    assert.equal(Bu.value.innerHTML, ' 0.308');
    api.paintState({run: {started_at: 100, file: 'cu.csv'}, zeros: {},
        channels: [{name: 'Bu', unit: 'A', value: -0.308},
                   {name: 'Bd', unit: 'Torr', value: 0.004}]});
    assert.equal(Bu.value.innerHTML, '-0.308');
});


/* -- the cathode current on the plasma panel ------------------------------ *
 *
 * queezz, 2026-09-15: "We need to add cathode current to the current plot.
 * So it'll be obvious when plasma is on... Is it the Hall sensor drifting or
 * the plasma died." And, the same evening, about the panel itself: "plasma
 * current when constant shows the noise instead of 0-1 or 0-3 A. Need some
 * axis control, if possible."
 *
 * The panel as the page builds it: two curves, one of them on the panel's
 * own right-hand axis, and the three-way scale choice in the legend row.
 */
function plasmaPanel(saved) {
    const pills = Object.fromEntries(['Ip', 'Ic'].map(name => [name, {
        dataset: {channel: name}, attrs: {}, listeners: {},
        setAttribute(key, value) { this.attrs[key] = value; },
        addEventListener(event, fn) { this.listeners[event] = fn; },
        querySelector() { return {textContent: ''}; }
    }]));
    const legend = {
        querySelector(selector) { return pills[selector.match(/"(.*?)"/)[1]] || null; },
        querySelectorAll() { return Object.values(pills); }
    };
    const scales = ['auto', '0-1', '0-3'].map(value => ({
        dataset: {scalePlasma: value}, attrs: {}, listeners: {},
        setAttribute(key, v) { this.attrs[key] = v; },
        addEventListener(event, fn) { this.listeners[event] = fn; }
    }));
    const canvas = {
        id: 'chart-plasma',
        dataset: {channels: 'Ip,Ic', height: '220', rightAxis: 'Ic'},
        style: {}, clientWidth: 600,
        parentNode: {classList: {toggle() {}}, querySelector() { return legend; }},
        getContext() { return new Proxy({}, {get: () => () => {}}); }
    };
    const span = {textContent: ''};
    const root = {
        classList: {toggle() {}}, dataset: {},
        querySelector(selector) {
            return selector.indexOf('span-plasma') !== -1 ? span : null;
        },
        querySelectorAll(selector) {
            if (selector === '[data-channel]') return Object.values(pills);
            if (selector === '[data-scale-plasma]') return scales;
            return [];
        }
    };
    let kept = saved;
    const context = vm.createContext({
        document: {
            querySelector(selector) { return selector === '[data-live]' ? root : null; },
            getElementById(id) { return id === 'chart-plasma' ? canvas : null; },
            createComment() { return {}; },
            addEventListener() {},
            body: {dataset: {}}, documentElement: {}
        },
        URL, URLSearchParams,
        window: {devicePixelRatio: 1, location: {href: 'http://localhost/', search: ''},
            history: {pushState() {}}, addEventListener() {},
            setInterval() { return 0; }, clearInterval() {},
            setTimeout() { return 0; }, clearTimeout() {}},
        fetch() { throw new Error('a redraw must not reach the rig'); },
        getComputedStyle() { return {getPropertyValue() { return ''; }}; },
        localStorage: {
            setItem(key, value) { kept = value; },
            getItem() { return kept === undefined ? null : kept; }
        }
    });
    const source = fs.readFileSync(
        path.join(__dirname, '../controlunit/web/static/js/live.js'), 'utf8');
    const end = source.indexOf('    if (document.readyState === "loading")');
    vm.runInContext(source.slice(0, end) +
        'globalThis.panel = {append, draw, drawAll, setupRails, view, recall, '
        + 'remember, reflectView};\n}());', context);
    const api = context.panel;
    api.recall();
    /* A steady discharge: 0.79 A with two hundredths of noise on it, and a
       filament held at about 42 A - the two magnitudes that cannot share one
       axis. The cathode readings arrive on their own clock, between the
       samples rather than with them. */
    api.append({to: 8, channels: {
        Ip: [[1, 0.78], [3, 0.80], [5, 0.79], [7, 0.80]],
        Ic: [[1.4, 41.8], [2.4, 42.1], [3.4, 41.9], [4.4, 42.0],
             [5.4, 42.2], [6.4, 41.7], [7.4, 42.0], [8.0, 41.9]]}});
    api.setupRails();
    api.reflectView();
    api.drawAll();
    return {api, canvas, pills, scales, span, saved: () => kept};
}

test('the cathode current is a curve of the plasma panel, on its own axis', () => {
    const {api, canvas, pills} = plasmaPanel();
    const drawn = api.draw(canvas, false, null);
    const [ip, ic] = drawn.series;
    assert.equal(ip.name, 'Ip');
    assert.equal(ic.name, 'Ic');
    assert.equal(ip.right, false);
    assert.equal(ic.right, true);
    assert.equal(ic.state, 'drawn');
    // The left axis is Ip's and nothing else's: tens of amperes of filament
    // current would otherwise leave the plasma current flat on the floor.
    assert.ok(drawn.hi < 1, 'the filament current reached the left axis');
    assert.ok(drawn.lo > 0.7 && drawn.lo < 0.78);
    // And the right axis is the filament's own.
    assert.ok(drawn.rlo < 41.8 && drawn.rhi > 42.2);
    // Both pills are switches like any other curve's.
    assert.equal(pills.Ic.attrs['aria-pressed'], 'true');
    pills.Ic.listeners.click();
    const without = api.draw(canvas, false, null);
    assert.equal(without.series[1].state, 'off');
    assert.equal(pills.Ic.dataset.curveState, 'off');
});

test('a steady filament current is never collapsed as flat', () => {
    // Collapsing exists so one motionless line cannot flatten the others
    // sharing an axis. A curve with an axis to itself shares none - and a
    // filament holding steady is exactly what the reader is looking for.
    const {api, canvas} = plasmaPanel();
    api.append({to: 20, channels: {
        Ip: [[10, 0.2], [12, 0.6], [14, 0.9], [16, 0.4], [18, 0.7], [20, 0.5]],
        Ic: [[10.4, 42], [12.4, 42], [14.4, 42], [16.4, 42], [18.4, 42], [20.4, 42]]}});
    const drawn = api.draw(canvas, false, null);
    assert.equal(drawn.series[1].state, 'drawn');
    assert.ok(drawn.rhi > drawn.rlo, 'a motionless curve still needs a scale');
});

test('cathode readings are never counted as ADC samples', () => {
    // They arrive over a LAN on the recorder's own clock at its own cadence,
    // so the span line's "samples" must not swell with them.
    const {api, canvas, span} = plasmaPanel();
    const drawn = api.draw(canvas, false, null);
    assert.equal(drawn.count, 4, 'four Ip samples');
    assert.equal(drawn.extra, 8, 'eight cathode readings, counted apart');
    assert.match(span.textContent, /4 samples/);
    assert.ok(!/8 samples/.test(span.textContent));
});

test('the plasma axis choice pins the left axis and leaves the right alone', () => {
    const {api, canvas, scales} = plasmaPanel();
    assert.equal(api.view.plasmaScale, 'auto');
    const auto = api.draw(canvas, false, null);

    scales[1].listeners.click();   // 0-1 A
    assert.equal(api.view.plasmaScale, '0-1');
    assert.equal(scales[1].attrs['aria-pressed'], 'true');
    assert.equal(scales[0].attrs['aria-pressed'], 'false');
    const narrow = api.draw(canvas, false, [0, 1]);
    assert.equal(narrow.lo, 0);
    assert.equal(narrow.hi, 1);

    scales[2].listeners.click();   // 0-3 A
    const wide = api.draw(canvas, false, [0, 3]);
    assert.equal(wide.lo, 0);
    assert.equal(wide.hi, 3);

    // The cathode's own axis autoscales through all three.
    for (const drawn of [auto, narrow, wide]) {
        assert.ok(drawn.rlo < 41.8 && drawn.rhi > 42.2);
    }
    // And nothing recorded moved: the choice is the browser's alone.
    assert.deepEqual(Object.keys(api.view.channels).sort(),
        ['Bd', 'Bu', 'Ic', 'Ip', 'Pd', 'Pu', 'Pu2']);
});

test('the plasma axis choice is remembered in this browser and restored', () => {
    const {api, saved} = plasmaPanel();
    api.view.plasmaScale = '0-3';
    api.remember();
    const store = saved();
    assert.match(store, /"plasmaScale":"0-3"/);

    // A reload: a fresh page reading the same store.
    const reloaded = plasmaPanel(store);
    assert.equal(reloaded.api.view.plasmaScale, '0-3');
    assert.equal(reloaded.scales[2].attrs['aria-pressed'], 'true');
    assert.equal(reloaded.scales[0].attrs['aria-pressed'], 'false');

    // Anything the store does not offer falls back to the autoscale.
    const nonsense = plasmaPanel(JSON.stringify({plasmaScale: '0-9'}));
    assert.equal(nonsense.api.view.plasmaScale, 'auto');
});
