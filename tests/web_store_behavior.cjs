/* The browser's own history of a run: bounded, and never cut short.
 *
 * queezz, 2026-10-02, an hour into an argon plasma at 0.1 s: "1 hour plot
 * cuts of data. Points limit? We need to do better. A bit better. Especially
 * if we are running 1-2 hour plasmas." The store kept its newest 20,000
 * points and dropped the rest, which at 0.1 s is 33 minutes. It now thins
 * the older half instead, so the run stays on the chart from its start.
 */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function history() {
    const source = fs.readFileSync(
        path.join(__dirname, '../controlunit/web/static/js/live.js'), 'utf8');
    const limits = source.slice(source.indexOf('    var STORE_SECONDS'),
        source.indexOf('    var root = document'));
    const body = source.slice(source.indexOf('    var store = {};'),
        source.indexOf('    function ask(query)'));
    const context = vm.createContext({});
    vm.runInContext('(function () {' + limits + body
        + 'globalThis.api = {append, held: function (name) { return store[name]; }};'
        + '}());', context);
    return context.api;
}

function feed(api, seconds, period, start) {
    const total = Math.round(seconds / period);
    const perPoll = Math.max(1, Math.round(2 / period));   // the page asks every 2 s
    for (let first = 0; first < total; first += perPoll) {
        const points = [];
        for (let i = first; i < Math.min(total, first + perPoll); i++) {
            points.push([start + Math.round(i * period * 1000) / 1000, i]);
        }
        api.append({channels: {Ip: points}, to: points[points.length - 1][0]});
    }
}

test('two hours at 0.1 s stay on the chart from the start, under the cap', () => {
    const api = history();
    const start = 1790928106;
    feed(api, 2 * 3600, 0.1, start);
    const kept = api.held('Ip');
    assert.ok(kept.length <= 20000, 'never more points than a browser draws');
    assert.ok(kept.length > 10000);
    assert.ok(kept[0][0] - start < 60, 'the run still begins at its beginning');
    assert.ok(start + 7200 - kept[kept.length - 1][0] < 0.2, 'and ends now');
    assert.equal(kept[kept.length - 1][1], 71999);
    for (let i = 1; i < kept.length; i++) {
        assert.ok(kept[i][0] > kept[i - 1][0], 'oldest first, no point twice');
    }
    // The recent quarter of an hour is whole: every sample, 0.1 s apart.
    for (let i = kept.length - 9000; i < kept.length; i++) {
        assert.ok(Math.abs(kept[i][0] - kept[i - 1][0] - 0.1) < 1e-6);
    }
});

test('a run that fits under the cap is not thinned at all', () => {
    const api = history();
    feed(api, 30 * 60, 0.1, 1790928106);
    assert.equal(api.held('Ip').length, 18000);
});

test('more than a day still falls off the old end', () => {
    const api = history();
    const start = 1790000000;
    feed(api, 26 * 3600, 10, start);                 // the rig's overnight 10 s
    const kept = api.held('Ip');
    assert.ok(kept.length >= 8640 && kept.length <= 8641, 'a day of them');
    assert.ok(kept[0][0] >= start + 2 * 3600 - 10);
});
