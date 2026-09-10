/* The Cathode group: two modes for one filament.
 *
 * Mode is a view choice and never a command — pressing either side of the
 * heading's switch must send nothing at all. From 4.13.0 the two sides are
 * the halves of one segmented pill rather than two buttons standing side by
 * side, and `aria-pressed` is the only state the script writes: the thumb
 * slides under whichever side carries it, in CSS. So what is asserted here
 * is unchanged and deliberately so — the switch's position, the keyboard's
 * reading of it, and which setter row is shown are one fact, not three.
 *
 * The manual drive is a draft row like the gas lines:
 * steps move the box, Set sends it, and a poll arriving mid-edit leaves the
 * reader's typing alone. What is actually driving is read from the rig, so
 * the feedback line is checked against all three of its states.
 */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function el(extra) {
    return Object.assign({
        dataset: {}, hidden: false, attrs: {}, textContent: '',
        classList: {toggle() {}},
        addEventListener(kind, fn) { this.handlers[kind] = fn; },
        setAttribute(name, value) { this.attrs[name] = value; },
        press() { this.handlers.click(); }
    }, {handlers: {}}, extra || {});
}

function numberBox(max) {
    return el({
        value: '0', min: '0', max: String(max), reported: 0,
        checkValidity() {
            return this.value !== '' && Number.isInteger(Number(this.value))
                && +this.value >= 0 && +this.value <= +this.max;
        },
        reportValidity() { this.reported += 1; }
    });
}

function build(storageThrows) {
    const input = numberBox(5000);
    const setButton = el(), offButton = el(), note = el();
    const steps = {};
    for (const size of ['1000', '-1000', '100', '-100', '10', '-10', '1', '-1']) {
        steps[size] = el({dataset: {cathodeStep: size}});
    }
    const manualRow = el({
        querySelector(s) {
            if (s.includes('cathode-input')) return input;
            if (s.includes('cathode-draft-note')) return note;
            if (s.includes('cathode-set')) return setButton;
            return offButton;
        },
        querySelectorAll() { return Object.values(steps); }
    });
    const pidRow = el();
    const modes = [
        el({dataset: {cathodeMode: 'pid'}}),
        el({dataset: {cathodeMode: 'manual'}})
    ];
    const cells = {feedback: el(), ip: el(), applied: el(), measured: el()};
    const root = {
        dataset: {},
        hasAttribute() { return false; },
        querySelector(s) {
            if (s.includes('cathode-manual-row')) return manualRow;
            if (s.includes('cathode-pid-row')) return pidRow;
            if (s.includes('plasma-setpoint')) return cells.feedback;
            if (s.includes('plasma-measured')) return cells.ip;
            if (s.includes('cathode-applied')) return cells.applied;
            if (s.includes('cathode-measured')) return cells.measured;
            return null;
        },
        querySelectorAll(s) {
            return s.includes('cathode-mode') ? modes : [];
        }
    };

    const sent = [];
    const store = {};
    const window = {localStorage: {
        getItem(k) {
            if (storageThrows) throw new Error('storage is blocked here');
            return k in store ? store[k] : null;
        },
        setItem(k, v) {
            if (storageThrows) throw new Error('storage is blocked here');
            store[k] = String(v);
        }
    }};
    const ctx = vm.createContext({
        document: {getElementById(id) { return id === 'control' ? root : null; }},
        window, sent
    });
    const source = fs.readFileSync('controlunit/web/static/js/control.js', 'utf8');
    vm.runInContext(
        source.slice(0, source.indexOf('    if (document.readyState'))
        + 'send = (path, body) => sent.push({path, body});'
        + ' globalThis.api = {setupDraftRow, setupCathodeMode, paintCathode,'
        + ' CATHODE_DRAFT}; }());',
        ctx
    );
    return {api: ctx.api, input, setButton, offButton, note, steps, manualRow,
            pidRow, modes, cells, sent, store};
}

test('mode is a view choice: it shows one setter row and sends nothing', () => {
    const d = build();
    d.api.setupCathodeMode();

    // Default is PID, on a browser that has never chosen. Exactly one side
    // ever holds: the thumb has one place to be.
    assert.equal(d.modes[0].attrs['aria-pressed'], 'true');
    assert.equal(d.modes[1].attrs['aria-pressed'], 'false');
    assert.equal(d.pidRow.hidden, false);
    assert.equal(d.manualRow.hidden, true);

    d.modes[1].press();
    assert.equal(d.modes[0].attrs['aria-pressed'], 'false');
    assert.equal(d.modes[1].attrs['aria-pressed'], 'true');
    assert.equal(d.pidRow.hidden, true);
    assert.equal(d.manualRow.hidden, false);
    assert.equal(d.sent.length, 0, 'choosing a mode must not reach the rig');

    d.modes[0].press();
    assert.equal(d.pidRow.hidden, false);
    assert.equal(d.manualRow.hidden, true);
    assert.equal(d.sent.length, 0);
});

test('the chosen mode is remembered in this browser, and only there', () => {
    const d = build();
    d.api.setupCathodeMode();
    d.modes[1].press();
    assert.equal(d.store['controlunit.cathode.mode'], 'manual');

    // A fresh page against the same store opens on Manual.
    d.pidRow.hidden = false;
    d.manualRow.hidden = false;
    d.api.setupCathodeMode();
    assert.equal(d.manualRow.hidden, false);
    assert.equal(d.pidRow.hidden, true);
    assert.equal(d.sent.length, 0);
});

test('a browser that stores nothing opens on PID and still switches', () => {
    // A private window, or a browser told to block site data: reading and
    // writing both throw, and the group must work anyway.
    const d = build(true);
    assert.doesNotThrow(function () { d.api.setupCathodeMode(); });
    assert.equal(d.pidRow.hidden, false);
    assert.equal(d.manualRow.hidden, true);

    assert.doesNotThrow(function () { d.modes[1].press(); });
    assert.equal(d.manualRow.hidden, false);
    assert.equal(d.sent.length, 0);
});

test('manual steps move only the draft, and clamp to 0..5000', () => {
    const d = build();
    d.api.setupDraftRow(d.manualRow, d.api.CATHODE_DRAFT);

    d.input.value = '1000';
    d.steps['1000'].press();
    assert.equal(+d.input.value, 2000);
    assert.equal(d.sent.length, 0, 'a step is a draft, not a command');

    d.steps['100'].press(); d.steps['10'].press(); d.steps['1'].press();
    assert.equal(+d.input.value, 2111);

    d.input.value = '4900'; d.steps['1000'].press();
    assert.equal(+d.input.value, 5000);
    d.input.value = '0'; d.steps['-1000'].press();
    assert.equal(+d.input.value, 0);
    assert.equal(d.sent.length, 0);
});

test('Set sends whole millivolts; an unusable draft sends nothing', () => {
    const d = build();
    d.api.setupDraftRow(d.manualRow, d.api.CATHODE_DRAFT);

    for (const bad of ['', '-1', '5001', '1.5']) {
        d.input.value = bad;
        d.setButton.press();
        d.steps['1'].press();
    }
    assert.equal(d.sent.length, 0);
    assert.equal(d.input.reported, 8, 'each refusal says so on the field');

    d.input.value = '1900';
    d.setButton.press();
    assert.equal(d.sent.length, 1);
    assert.equal(d.sent[0].path, '/api/cathode');
    assert.equal(d.sent[0].body.mv, 1900);
});

test('Off is its own word to the rig, and drops the draft with it', () => {
    const d = build();
    d.api.setupDraftRow(d.manualRow, d.api.CATHODE_DRAFT);
    d.input.value = '1900';
    d.offButton.press();
    assert.equal(d.sent.length, 1);
    assert.equal(d.sent[0].path, '/api/cathode');
    assert.equal(d.sent[0].body.off, true);
    assert.equal(d.sent[0].body.mv, undefined);
    assert.equal(+d.input.value, 0);
});

test('a poll preserves an edited draft and still shows what is applied', () => {
    const d = build();
    d.api.setupDraftRow(d.manualRow, d.api.CATHODE_DRAFT);
    d.input.value = '1000';
    d.steps['1000'].press();
    assert.equal(+d.input.value, 2000);

    d.api.paintCathode({setpoints: {cathode_mv: 1500}}, {});
    assert.equal(+d.input.value, 2000, 'the rig must not take back the typing');
    assert.equal(d.cells.applied.textContent, '1500 mV');
    assert.equal(d.manualRow.dataset.applied, '1500');
    assert.equal(d.note.textContent, 'Draft · press Set to apply');

    // An untouched box takes the rig's own value on the first paint.
    const fresh = build();
    fresh.api.setupDraftRow(fresh.manualRow, fresh.api.CATHODE_DRAFT);
    fresh.api.paintCathode({setpoints: {cathode_mv: 1500}}, {});
    assert.equal(+fresh.input.value, 1500);
    assert.equal(fresh.note.textContent, 'Draft matches applied');
});

test('the feedback line says what is driving, in all three states', () => {
    const d = build();

    d.api.paintCathode({setpoints: {plasma_a: 0.5, cathode_mv: 1900}}, {});
    assert.equal(d.cells.feedback.textContent, 'Held · PID 0.50 A');

    d.api.paintCathode({setpoints: {plasma_a: 0, cathode_mv: 1900}}, {});
    assert.equal(d.cells.feedback.textContent, 'Held · manual 1900 mV');

    d.api.paintCathode({setpoints: {}}, {});
    assert.equal(d.cells.feedback.textContent, 'off');
});

test('Ip is read beside the drive; the cathode volts only when reported', () => {
    const d = build();
    d.api.paintCathode({setpoints: {}}, {});
    assert.equal(d.cells.ip.textContent, '—');
    assert.equal(d.cells.measured.textContent, '—');

    d.api.paintCathode(
        {setpoints: {}},
        {Ip: {value: 0.421, unit: 'A'}, Cv: {value: 3.1, unit: 'V'}}
    );
    assert.equal(d.cells.ip.textContent, '0.421 A');
    assert.equal(d.cells.measured.textContent, '3.100 V');
});
