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
function readoutCard(name, room, dataset, pen) {
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
    /* The card is also the press that hides it: a `hidden` flag, its
       attributes, its listeners and its pen, read back the way the page
       writes them. */
    return {
        dataset: dataset || {readout: name},
        classList: {toggle() {}},
        hidden: false, tabIndex: 0, attrs: {'aria-pressed': 'true'}, handlers: {},
        style: {getPropertyValue(prop) { return prop === '--pen' ? ' ' + (pen || '#123456') : ''; }},
        setAttribute(key, v) { this.attrs[key] = v; },
        getAttribute(key) { return this.attrs[key]; },
        removeAttribute(key) { delete this.attrs[key]; },
        addEventListener(kind, fn) { this.handlers[kind] = fn; },
        focus() { focused.at = this; },
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
/* Which element last took the focus, across every harness: the hide and
   show presses hand it on, and a test reads where it went. */
const focused = {at: null};

/* A node `document.createElement` hands back: enough for the page to build
   a pill from — a class, a dataset, a pen, children and a listener. */
function made(tagName) {
    const node = el({tagName: tagName.toUpperCase(), textContent: '', focus() { focused.at = node; }});
    node.style = {props: {}, setProperty(key, v) { this.props[key] = v; }};
    return node;
}

/* The row the hidden cards' pills stand in, which the page empties and
   refills on every paint. */
function chipRow() {
    const row = el({hidden: true});
    Object.defineProperty(row, 'firstChild', {get() { return row.children[0] || null; }});
    row.removeChild = function (child) { row.detach(child); child.parentNode = null; return child; };
    return row;
}

function instrument(cardRoom, parts) {
    const roomFor = (name) => (cardRoom && typeof cardRoom === 'object') ? cardRoom[name] : cardRoom;
    const cards = Object.fromEntries(['Bu', 'Bd'].map(name => [name, readoutCard(name, roomFor(name))]));
    /* The cathode supply's two cards, keyed as the template keys them and in
       their own pen. */
    const cathode = Object.fromEntries(['voltage_v', 'current_a'].map(key =>
        [key, readoutCard(key, undefined, {cathodeReadout: key}, '#ff6b35')]));
    const chips = chipRow();
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
            // The rail's own pieces a test brings along: a pulldown, a folded line.
            if (parts && parts[selector]) return parts[selector];
            const chip = selector.match(/^\[data-role="readout-chips"\] \[data-show="(.*?)"\]$/);
            if (chip) return chips.children.find(c => c.dataset.show === chip[1]) || null;
            if (selector === '[data-role="readout-chips"]') return chips;
            const readout = selector.match(/^\.readout\[data-readout="(.*?)"\]$/);
            if (readout) return cards[readout[1]] || null;
            if (selector.indexOf('fold-units') !== -1) return units;
            const fold = selector.match(/\[data-fold-readout="(.*?)"\]/);
            return fold ? folded[fold[1]] || null : null;
        },
        querySelectorAll(selector) {
            if (selector === '.readouts > .readout') return [...Object.values(cards), ...Object.values(cathode)];
            return selector === '[data-channel]' ? Object.values(buttons) : [];
        }
    };
    let saved;
    const context = vm.createContext({
        document: {
            // The page's own root, and the display tools a test brings along:
            // they are looked up from the document, because docked into the
            // tab bar they are outside the page element. Everything else this
            // harness does not model is simply absent, as it is on a page
            // without it.
            querySelector(selector) {
                if (selector === '[data-live]') return root;
                return (parts && parts[selector]) || null;
            },
            getElementById(id) { return id === 'chart-bar' ? canvas : null; },
            querySelectorAll() { return []; },
            createComment() { return {}; },
            createElement: made,
            body: {dataset: {}}, documentElement: {}
        },
        URL, URLSearchParams,
        window: {devicePixelRatio: 2, location: {href: 'http://localhost/', search: ''},
            history: {pushState(state, title, url) {
                context.window.location.href = url;
                context.window.location.search = new URL(url).search;
            }},
            setInterval() { return 1; }, clearInterval() {}},
        fetch() { throw new Error('Mode changes must not send requests'); },
        getComputedStyle() { return {getPropertyValue() { return ''; }}; },
        localStorage: {setItem(k, v) { saved = v; }, getItem() { return saved; }}
    });
    const source = fs.readFileSync(path.join(__dirname, '../controlunit/web/static/js/live.js'), 'utf8');
    // Exercise production handlers and drawing decisions without starting timers.
    const end = source.indexOf('    if (document.readyState === "loading")');
    vm.runInContext(source.slice(0, end) +
        'globalThis.instrument = {append, draw, drawAll, setupRails, applyPreset, view, recall, remember, setMode, modeInAddress, paintState, setupReadouts, paintHidden, applyPoll, isFast() { return fast; }};\n}());', context);
    const api = context.instrument;
    api.append({to: 4, channels: {Bu: [[1, -0.004], [2, -0.004], [3, -0.004], [4, -0.004]],
        Bd: [[1, 0.001], [2, 0.002], [3, 0.003], [4, 0.004]]}});
    api.setupRails();
    api.drawAll();
    return {api, buttons, canvas, cards, cathode, chips, folded, units, context,
            stored() { return saved === undefined ? null : JSON.parse(saved); },
            store(view) { saved = JSON.stringify(view); }};
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

/* The page as a phone sees it: the switch, the two places it can stand —
   its home at the end of the status line, and the Menu — and the ancestors
   whose `display` a mode may take away. Monitor's own Display and Full
   screen strip is modelled too, because it used to be the switch's third
   home and must no longer be one. */
/* `wide` is a desktop: the same page above the phone breakpoint, where the
   tab bar's right-end slot holds the display tools and the switch in
   Operate and Observe. */
function phone(startMode, wide) {
    const buttons = ['operate', 'observe', 'monitor'].map(name =>
        el({dataset: {mode: name}}));
    const toolbar = el({className: 'view-toolbar', dataset: {role: 'mode-switch'},
        querySelectorAll() { return buttons; }});
    const tools = el({className: 'display-tools', dataset: {role: 'display-tools'}});
    const menu = el({id: 'main-tabs', ancestors: ['.tabbar', '#main-tabs']});
    const slot = el({className: 'tab-tools', dataset: {role: 'tab-tools'},
        ancestors: ['.tabbar', '.tab-tools']});
    const actions = el({dataset: {role: 'mode-actions'}, hidden: true,
        ancestors: ['.mode-actions']});
    const stop = el({dataset: {role: 'stop-all'}});
    const home = el({className: 'instrument-header',
        ancestors: ['.page-main', '.instrument-header']});
    home.appendChild(tools);
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
                return toolbar.parentNode === home ? toolbar : null;
            }
            if (selector.indexOf('mode-actions') !== -1) return actions;
            return null;
        },
        querySelectorAll(selector) {
            /* The gauge buttons carry `data-mode="Torr"`; a bare `[data-mode]`
               query from live.js would reach them, so the harness answers
               only the switch's own scoped selector. */
            if (selector === '[data-role="mode-switch"] [data-mode]') return buttons;
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
                if (selector.indexOf('display-tools') !== -1) return tools;
                if (selector.indexOf('tab-tools') !== -1) return slot;
                if (selector.indexOf('stop-all') !== -1) return stop;
                return null;   // no open Menu, no open drawer, no backdrop
            },
            querySelectorAll(selector) {
                if (selector === '[data-role="mode-switch"] [data-mode]') return buttons;
                return [];
            },
            getElementById(id) { return id === 'main-tabs' ? menu : null; },
            createComment() { return el({}); },
            addEventListener(kind, fn) { if (kind === 'keydown') keys.push(fn); },
            body: body, documentElement: {}
        },
        URL, URLSearchParams,
        window: {
            devicePixelRatio: 1,
            matchMedia(query) { return {matches: !wide && query.indexOf('620px') !== -1,
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
    return {api: context.phone, toolbar, tools, slot, menu, actions, home, buttons, body,
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
        const homes = [rig.menu, rig.home, rig.actions];
        const copies = homes.reduce(
            (n, h) => n + h.children.filter(c => c === rig.toolbar).length, 0);
        assert.equal(copies, 1);
        // On a phone Monitor keeps it at home on the status line, and the
        // other two modes put it in the Menu; Display and Full screen are
        // never its host (2026-10-07: the status line is on the screen in
        // Monitor, so the switch needs no strip of its own there).
        assert.equal(rig.toolbar.parentNode, mode === 'monitor' ? rig.home : rig.menu);
        assert.equal(rig.actions.children.length, 0);
    }
    // The status line and the Menu are two homes, not two switches.
    assert.ok(seen.has(rig.menu) && seen.has(rig.home));
    assert.equal(rig.buttons.length, 3);
});

/* -- the four display tools ------------------------------------------------ *
 *
 * queezz, 2026-10-07: "Don't we have space somewhere on the top bar-ish for
 * keeping 4 display pills there permanently?" One group, moved with the
 * switch: into the tab bar's slot before it on a desktop in Operate and
 * Observe, at home on the strip in Monitor and on any phone. */

test('on a desktop the display tools dock into the tab bar before the switch', () => {
    const rig = phone('operate', true);
    for (const mode of ['operate', 'observe', 'monitor', 'operate', 'monitor', 'observe']) {
        rig.api.setMode(mode);
        if (mode === 'monitor') {
            // No tab bar: both at home on the strip, in the strip's order.
            assert.deepEqual(rig.slot.children, []);
            const order = rig.home.children.filter(c => c === rig.tools || c === rig.toolbar);
            assert.deepEqual(order, [rig.tools, rig.toolbar]);
        } else {
            assert.deepEqual(rig.slot.children, [rig.tools, rig.toolbar], mode);
            assert.equal(rig.home.children.indexOf(rig.tools), -1);
        }
        assert.ok(rendered(rig.tools.parentNode, mode), mode + ' hides the display tools');
    }
    // Whichever arrived in the slot first, the tools stand before the switch.
    rig.api.setMode('monitor');
    rig.slot.appendChild(rig.toolbar);
    rig.api.setMode('operate');
    assert.deepEqual(rig.slot.children, [rig.tools, rig.toolbar]);
});

test('on a phone the switch rides in the Menu and the display tools stay on the strip', () => {
    for (const mode of ['operate', 'observe', 'monitor']) {
        const rig = phone(mode);
        assert.equal(rig.tools.parentNode, rig.home, mode);
        assert.equal(rig.toolbar.parentNode, mode === 'monitor' ? rig.home : rig.menu, mode);
        assert.deepEqual(rig.slot.children, [], mode);
        assert.equal(rig.menu.children.indexOf(rig.tools), -1, 'the Menu is navigation');
    }
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

/* A <select> as much as live.js touches: its options, which one is chosen,
   and `value` read and written the way a browser does it. */
function pulldown(options, chosen) {
    const opts = options.map(([value, text, channels]) => ({
        value, textContent: text, dataset: channels ? {channels} : {}}));
    return {
        options: opts, listeners: {},
        selectedIndex: Math.max(0, opts.findIndex(o => o.value === chosen)),
        addEventListener(kind, fn) { this.listeners[kind] = fn; },
        get value() { return this.selectedIndex >= 0 ? opts[this.selectedIndex].value : ''; },
        set value(next) { this.selectedIndex = opts.findIndex(o => o.value === String(next)); }
    };
}

test('the Show pulldown names the preset on the page, and says custom when there is none', () => {
    // queezz, 2026-10-07: "a pulldown selector. So it shows what's selected".
    const preset = pulldown([['', 'custom'], ['all', 'All', 'Ip,Ic,Pu,Pu2,Pd,Bu,Bd'],
        ['vacuum', 'Vacuum', 'Pu,Pu2,Pd,Bu,Bd'], ['plasma', 'Plasma', 'Ip,Ic,Bu,Bd']], '');
    const cut = pulldown([['60', '1 m'], ['300', '5 m'], ['3600', '1 h'], ['0', 'Full']], '300');
    // Handed to the document only, never to `root`: docked into the tab bar
    // the display tools are outside the page element.
    const {api, buttons} = instrument(undefined, {
        'select[data-role="preset"]': preset,
        'select[data-role="window"]': cut
    });
    api.drawAll();
    assert.equal(preset.value, 'all');
    // One curve switched by hand: no named set is on the page any more.
    buttons.Bd.listeners.click();
    assert.equal(preset.value, '');
    // Choosing one from the pulldown is the same press a preset always was.
    api.applyPreset(preset.options[3]);
    assert.equal(preset.value, 'plasma');
    // The window is a change on its pulldown.
    cut.value = '3600';
    cut.listeners.change();
    assert.equal(api.view.window, 3600);
});

test('fast polling is one press: pressed is fast, pressed again is normal', () => {
    // queezz, 2026-10-07: "normal/fast is a toggle".
    const toggle = el({dataset: {poll: ''}, attrs: {'aria-pressed': 'false'}});
    const {api, context} = instrument(undefined, {'[data-poll]': toggle});
    // A press polls at once; the rig is not modelled, so the asks never answer.
    context.fetch = () => new Promise(() => {});
    api.applyPoll();
    assert.equal(api.isFast(), false);
    assert.equal(toggle.attrs['aria-pressed'], 'false');
    toggle.handlers.click();
    assert.equal(api.isFast(), true);
    assert.equal(toggle.attrs['aria-pressed'], 'true');
    toggle.handlers.click();
    assert.equal(api.isFast(), false);
    assert.equal(toggle.attrs['aria-pressed'], 'false');
    // A rate, not a view: nothing about it is written to the store.
    assert.equal(JSON.stringify(api.view).indexOf('fast'), -1);
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
            querySelectorAll() { return []; },
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

/* -- the Sampling pulldown ---------------------------------------------- *
 *
 * queezz, 2026-10-07: "we don't have to make all the buttons for all the
 * samplings. We can use a pulldown selector. So it shows what's selected".
 * It shows the time the rig holds, from every poll; a time the rig holds
 * that is not one of the four on offer is shown as itself in an option that
 * cannot be chosen, so the pulldown never names a time the rig is not using.
 */
function samplingPage() {
    let select;
    function option(value, text) {
        return {
            dataset: {}, value, textContent: text, disabled: false, hidden: false, on: false,
            get selected() { return this.on; },
            set selected(next) {
                if (next) select.options.forEach(o => { o.on = false; });
                this.on = !!next;
            }
        };
    }
    select = {
        options: [],
        querySelector(s) {
            return s === 'option[data-transient]'
                ? this.options.find(o => 'transient' in o.dataset) || null : null;
        },
        removeChild(o) { this.options.splice(this.options.indexOf(o), 1); },
        insertBefore(o, ref) {
            const at = this.options.indexOf(ref);
            this.options.splice(at < 0 ? this.options.length : at, 0, o);
        },
        get firstChild() { return this.options[0] || null; },
        get shown() { return this.options.find(o => o.selected) || null; }
    };
    [['10', '10 s'], ['1', '1 s'], ['0.1', '0.1 s'], ['0.01', '0.01 s']].forEach(
        ([value, text]) => select.options.push(option(value, text)));
    const root = {
        dataset: {},
        querySelector() { return null; },
        querySelectorAll(s) { return s === 'select[data-role="sampling"]' ? [select] : []; }
    };
    const context = vm.createContext({
        document: {
            getElementById(id) { return id === 'control' ? root : null; },
            querySelectorAll() { return []; },
            createElement() { return option('', ''); }
        },
        window: {localStorage: {getItem() { return null; }, setItem() {}}}
    });
    const source = fs.readFileSync(
        path.join(__dirname, '../controlunit/web/static/js/control.js'), 'utf8');
    vm.runInContext(source.slice(0, source.indexOf('    if (document.readyState'))
        + 'globalThis.api = {paintRun}; }());', context);
    return {paint(sampling) { context.api.paintRun({run: {sampling}}); }, select};
}

test('the Sampling pulldown shows the time the rig holds, and only that', () => {
    const {paint, select} = samplingPage();
    paint(0.1);
    assert.equal(select.shown.value, '0.1');
    assert.equal(select.options.length, 4);
    // The rig's own screen can set a time the page does not offer.
    paint(7);
    assert.equal(select.options.length, 5);
    assert.equal(select.shown.textContent, '7 s');
    assert.ok(select.shown.disabled && select.shown.hidden, 'it can be shown, never chosen');
    assert.equal(select.options[0], select.shown);
    // No reading at all is said as no reading, never as the first option.
    paint(null);
    assert.equal(select.shown.textContent, '—');
    // Back on an offered time, the stand-in goes.
    paint(1);
    assert.equal(select.shown.value, '1');
    assert.equal(select.options.length, 4);
});

test('the view-mode switch binds only its own buttons, never the gauge Torr/Pa ones', () => {
    const page = phone('monitor');
    assert.equal(page.buttons.filter(b => b.handlers.click).length, 3);
    assert.equal(page.buttons.find(b => b.dataset.mode === 'monitor').attrs['aria-pressed'], 'true');
    assert.equal(page.buttons.find(b => b.dataset.mode === 'operate').attrs['aria-pressed'], 'false');
    const source = fs.readFileSync(path.join(__dirname, '../controlunit/web/static/js/live.js'), 'utf8');
    assert.equal(source.indexOf('querySelectorAll("[data-mode]")'), -1);
    assert.notEqual(source.indexOf('[data-role="mode-switch"] [data-mode]'), -1);
});

/* -- a press hides a readout card ---------------------------------------- *
 *
 * queezz, 2026-10-07: "when operating, I wanted a click to toggle the big
 * digit screens for gauges and ADC readings. For some regimes I only need
 * 2-3, so others get in the way on mobile." A press on a card hides it in
 * Operate and Observe; it comes back as a pill in its own pen at the grid's
 * end, and a press on the pill shows it again. Monitor shows every card. */

test('a press on a readout card hides it and leaves a pill with its name and pen', () => {
    const {api, cards, chips} = instrument();
    api.setupReadouts();
    api.paintHidden();
    assert.equal(chips.hidden, true);
    assert.equal(chips.children.length, 0);

    cards.Bu.handlers.click();
    assert.equal(cards.Bu.hidden, true);
    assert.equal(cards.Bd.hidden, false);
    assert.deepEqual([...api.view.hiddenReadouts], ['Bu']);
    assert.equal(chips.hidden, false);
    assert.equal(chips.children.length, 1);
    const chip = chips.children[0];
    assert.equal(chip.tagName, 'BUTTON');
    assert.equal(chip.type, 'button');
    assert.equal(chip.className, 'pen readout-chip');
    assert.equal(chip.dataset.show, 'Bu');
    assert.equal(chip.attrs['aria-pressed'], 'false');
    assert.equal(chip.style.props['--pen'], '#123456');
    assert.equal(chip.children[0].className, 'pen-dot');
    assert.equal(chip.children[1].textContent, 'Bu');
    // The keyboard is not dropped: the pill that brings the card back has it.
    assert.equal(focused.at, chip);

    // The pill's press shows the card where it stood, and the pill leaves.
    chip.handlers.click();
    assert.equal(cards.Bu.hidden, false);
    assert.equal(cards.Bu.attrs['aria-pressed'], 'true');
    assert.deepEqual([...api.view.hiddenReadouts], []);
    assert.equal(chips.children.length, 0);
    assert.equal(chips.hidden, true);
    assert.equal(focused.at, cards.Bu);
});

test('Enter and Space press a card as a click does, and Space does not scroll', () => {
    const {api, cards, chips} = instrument();
    api.setupReadouts();
    api.paintHidden();
    let stopped = 0;
    cards.Bd.handlers.keydown({key: 'Tab', preventDefault() { stopped += 1; }});
    assert.equal(cards.Bd.hidden, false);
    cards.Bd.handlers.keydown({key: ' ', preventDefault() { stopped += 1; }});
    assert.equal(cards.Bd.hidden, true);
    assert.equal(stopped, 1);
    cards.Bu.handlers.keydown({key: 'Enter', preventDefault() {}});
    // The pills stand in the cards' own order, whatever order they were hidden in.
    assert.deepEqual(chips.children.map(c => c.dataset.show), ['Bu', 'Bd']);
});

test('the cathode cards hide to pills named as the folded row names them, Uc and Ic', () => {
    const {api, cathode, chips} = instrument();
    api.setupReadouts();
    api.paintHidden();
    cathode.current_a.handlers.click();
    cathode.voltage_v.handlers.click();
    assert.deepEqual(chips.children.map(c => c.dataset.show), ['voltage_v', 'current_a']);
    assert.deepEqual(chips.children.map(c => c.children[1].textContent), ['Uc', 'Ic']);
    assert.deepEqual(chips.children.map(c => c.style.props['--pen']), ['#ff6b35', '#ff6b35']);
});

test('the hidden cards are remembered with the view and restored', () => {
    const first = instrument();
    first.api.setupReadouts();
    first.api.paintHidden();
    first.cards.Bu.handlers.click();
    first.cathode.voltage_v.handlers.click();
    const kept = first.stored();
    assert.deepEqual(kept.hiddenReadouts, ['Bu', 'voltage_v']);
    // Every key the view already kept is still there beside it.
    for (const key of ['window', 'channels', 'igLog', 'barLog', 'plasmaScale', 'smooth', 'big', 'monitorBig'])
        assert.ok(key in kept, key);

    const second = instrument();
    second.store(kept);
    second.api.recall();
    second.api.paintHidden();
    assert.equal(second.cards.Bu.hidden, true);
    assert.equal(second.cathode.voltage_v.hidden, true);
    assert.equal(second.cards.Bd.hidden, false);
    assert.deepEqual(second.chips.children.map(c => c.dataset.show), ['Bu', 'voltage_v']);

    // A view stored before cards could be hidden reads as every card shown,
    // and a list that is not one is not read.
    for (const old of [{window: 300}, {hiddenReadouts: 'Bu'}]) {
        const third = instrument();
        third.store(old);
        third.api.recall();
        third.api.paintHidden();
        assert.deepEqual([...third.api.view.hiddenReadouts], []);
        assert.equal(third.cards.Bu.hidden, false);
        assert.equal(third.chips.hidden, true);
    }
});

test('Monitor shows every card and no pills, and a press there does nothing', () => {
    const {api, cards, cathode, chips} = instrument();
    api.setupReadouts();
    api.paintHidden();
    cards.Bu.handlers.click();
    cathode.current_a.handlers.click();
    api.setMode('monitor');
    for (const card of [cards.Bu, cards.Bd, cathode.voltage_v, cathode.current_a]) {
        assert.equal(card.hidden, false);
        assert.equal(card.attrs['aria-pressed'], 'true');
        assert.equal(card.attrs['aria-disabled'], 'true');
        assert.equal(card.tabIndex, -1);
    }
    assert.equal(chips.hidden, true);
    assert.equal(chips.children.length, 0);
    cards.Bd.handlers.click();
    cards.Bd.handlers.keydown({key: 'Enter', preventDefault() {}});
    assert.equal(cards.Bd.hidden, false);
    assert.deepEqual([...api.view.hiddenReadouts], ['Bu', 'current_a']);

    // Observe shares Operate's set: the same two cards are away again.
    api.setMode('observe');
    assert.equal(cards.Bu.hidden, true);
    assert.equal(cathode.current_a.hidden, true);
    assert.equal(cards.Bd.hidden, false);
    assert.equal(cards.Bd.tabIndex, 0);
    assert.equal(cards.Bd.attrs['aria-disabled'], undefined);
    assert.deepEqual(chips.children.map(c => c.dataset.show), ['Bu', 'current_a']);
});

test('folded, the row still carries a hidden card\'s value', () => {
    const {api, cards, folded} = instrument();
    api.setupReadouts();
    api.paintHidden();
    cards.Bu.handlers.click();
    assert.equal(cards.Bu.hidden, true);
    api.paintState(reading({Bu: -0.004, Bd: 0.004}));
    assert.equal(folded.Bu.textContent, '-4.0e-3');
    assert.equal(folded.Bd.textContent, '4.0e-3');
    // The hidden card is still written, so it comes back current.
    assert.equal(cards.Bu.parts.value.innerHTML, MINUS_FOUR_MILLI);
});
