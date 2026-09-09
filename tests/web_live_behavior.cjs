// Run with: node --test tests/web_live_behavior.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function instrument() {
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
        dataset: {}, querySelector() { return null; },
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
        'globalThis.instrument = {append, draw, drawAll, setupRails, applyPreset, view, recall, remember, setMode, modeInAddress};\n}());', context);
    const api = context.instrument;
    api.append({to: 4, channels: {Bu: [[1, -0.004], [2, -0.004], [3, -0.004], [4, -0.004]],
        Bd: [[1, 0.001], [2, 0.002], [3, 0.003], [4, 0.004]]}});
    api.setupRails();
    api.drawAll();
    return {api, buttons, canvas};
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
