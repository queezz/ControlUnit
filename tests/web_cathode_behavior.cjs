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
    const cells = {feedback: el(), ip: el(), applied: el(), measured: el(), fold: el()};
    /* The output lamp, as control.js sees it: the direction is written onto
       it by live.js, from the telemetry, and read back here. */
    const lamp = el({dataset: {next: 'off'}, disabled: false});
    const gated = [el({disabled: false}), el({disabled: false})];
    const root = {
        dataset: {},
        hasAttribute() { return false; },
        querySelector(s) {
            if (s.includes('cathode-manual-row')) return manualRow;
            if (s.includes('cathode-pid-row')) return pidRow;
            if (s.includes('cathode-output')) return lamp;
            if (s.includes('fold-plasma')) return cells.fold;
            if (s.includes('plasma-setpoint')) return cells.feedback;
            if (s.includes('plasma-measured')) return cells.ip;
            if (s.includes('cathode-applied')) return cells.applied;
            if (s.includes('cathode-measured')) return cells.measured;
            return null;
        },
        querySelectorAll(s) {
            if (s.includes('cathode-mode')) return modes;
            if (s.includes('.sets button')) return gated;
            if (s.includes('cathode-input')) return [input];
            return [];
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
        + ' globalThis.api = {setupDraftRow, setupCathodeMode, setupFolds,'
        + ' paintCathode, setupOutputLamp, paintGate, noteControl, CATHODE_DRAFT,'
        + ' paintOutcome, hold(id) { pending = id; }, listen(cell) { status = cell; }}; }());',
        ctx
    );
    return {api: ctx.api, input, setButton, offButton, note, steps, manualRow,
            pidRow, modes, cells, sent, store, root, lamp, gated};
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
    // The loop's command stands beside its setpoint (queezz, 2026-10-02).
    assert.equal(d.cells.feedback.textContent, 'Held · PID 0.50 A · 1900 mV');

    d.api.paintCathode({setpoints: {plasma_a: 0, cathode_mv: 1900}}, {});
    assert.equal(d.cells.feedback.textContent, 'Held · manual 1900 mV');

    d.api.paintCathode({setpoints: {}}, {});
    assert.equal(d.cells.feedback.textContent, 'off');
});

test('folded, the Cathode card says what is driving and what Ip reads', () => {
    // queezz, 2026-09-14: a folded card is one row that still answers the
    // question the card exists for. The same poll writes both lines, from
    // the same two values, so the folded card cannot drift from the open one.
    const d = build();

    d.api.paintCathode({setpoints: {}}, {Ip: {value: -0.308, unit: 'A'}});
    assert.equal(d.cells.fold.textContent, 'off · read -0.308 A');
    assert.equal(d.cells.feedback.textContent, 'off');
    assert.equal(d.cells.ip.textContent, '-0.308 A');

    d.api.paintCathode({setpoints: {plasma_a: 0.5}}, {Ip: {value: 0.421, unit: 'A'}});
    assert.equal(d.cells.feedback.textContent, 'Held · PID 0.50 A');
    // The card's own name already says "Cathode", so the folded line does
    // not spend a word of a narrow row repeating "Held".
    assert.equal(d.cells.fold.textContent, 'PID 0.50 A · read 0.421 A');

    d.api.paintCathode({setpoints: {cathode_mv: 1900}}, {});
    assert.equal(d.cells.fold.textContent, 'manual 1900 mV · read —');
});

test('a fold is remembered per card and pressing one sends nothing', () => {
    // One code path, one key per card: `controlunit.fold.<card>`.
    const d = build();
    const folds = {};
    const card = function (name, open) {
        return {
            dataset: {fold: name}, open: open, handlers: {},
            addEventListener(kind, fn) { this.handlers[kind] = fn; },
            querySelector() { return null; }
        };
    };
    const gas = card('gas', true), stop = card('stop', true);
    d.root.querySelectorAll = function (s) {
        return s === '[data-fold]' ? [gas, stop] : [];
    };
    d.store['controlunit.fold.gas'] = '0';
    d.api.setupFolds();
    assert.equal(gas.open, false, 'a browser that folded this card keeps it folded');
    assert.equal(stop.open, true, 'a card never chosen ships as the page shipped it');

    stop.open = false;
    stop.handlers.toggle();
    assert.equal(d.store['controlunit.fold.stop'], '0');
    stop.open = true;
    stop.handlers.toggle();
    assert.equal(d.store['controlunit.fold.stop'], '1');
    assert.equal(d.sent.length, 0, 'folding must not reach the rig');
});

test('a browser that stores nothing still folds every card', () => {
    const d = build(true);
    const shut = {
        dataset: {fold: 'gas'}, open: true, handlers: {},
        addEventListener(kind, fn) { this.handlers[kind] = fn; },
        querySelector() { return null; }
    };
    d.root.querySelectorAll = function (s) { return s === '[data-fold]' ? [shut] : []; };
    assert.doesNotThrow(function () { d.api.setupFolds(); });
    assert.equal(shut.open, true);
    shut.open = false;
    assert.doesNotThrow(function () { shut.handlers.toggle(); });
});

/* The supply's own output, which the drive above it does not reach.
 *
 * Owner decision 2026-09-15, live. Two directions, two different presses:
 * off is a safety press of the shape Stop all outputs has, and on is a
 * setter. The lamp shows what the supply answers and sends the opposite;
 * which way that is has been written onto it by live.js, from the telemetry,
 * so this half only has to press it and gate it.
 */
test('the lamp sends the opposite of what the supply answers', () => {
    const d = build();
    d.api.setupOutputLamp();

    d.lamp.dataset.next = 'off';
    d.lamp.press();
    assert.equal(d.sent[0].path, '/api/cathode-output');
    assert.equal(d.sent[0].body.on, false);

    d.lamp.dataset.next = 'on';
    d.lamp.press();
    assert.equal(d.sent[1].path, '/api/cathode-output');
    assert.equal(d.sent[1].body.on, true);
    assert.equal(d.sent.length, 2);
});

test('the gate never switches off the press that opens the output', () => {
    // The lamp rides inside `.sets`, which the gate covers with one blanket;
    // off escapes it the way Stop all outputs does, by standing outside.
    const d = build();
    const shut = {remote: false, acquiring: false, fence: {}};
    d.lamp.dataset.next = 'off';
    d.api.paintGate(shut, {});
    assert.equal(d.lamp.disabled, false, 'a safety press is never gated');
    assert.ok(d.gated.every((c) => c.disabled), 'everything else is');

    d.api.paintGate({remote: true, acquiring: true, fence: {}}, {mine: true});
    assert.equal(d.lamp.disabled, false);
});

test('closing the output is a setter and wears every gate one wears', () => {
    const d = build();
    d.lamp.dataset.next = 'on';

    d.api.paintGate({remote: false, acquiring: true, fence: {}}, {mine: true});
    assert.equal(d.lamp.disabled, true, 'the switch on the rig is off');

    d.api.paintGate({remote: true, acquiring: true, fence: {needed: true, passed: false}},
                    {mine: true});
    assert.equal(d.lamp.disabled, true, "the lab's word has not been typed");

    d.api.paintGate({remote: true, acquiring: true, fence: {}},
                    {holder: 'Ivan', mine: false});
    assert.equal(d.lamp.disabled, true, 'somebody else has control');

    // No run needed: the supply can be switched on before the first sample.
    d.api.paintGate({remote: true, acquiring: false, fence: {}}, {mine: true});
    assert.equal(d.lamp.disabled, false);
});

test('Ip is read beside the drive; an analog placeholder cannot pose as Kikusui volts', () => {
    const d = build();
    d.api.paintCathode({setpoints: {}}, {});
    assert.equal(d.cells.ip.textContent, '—');
    assert.equal(d.cells.measured.textContent, '');

    d.api.paintCathode(
        {setpoints: {}},
        {Ip: {value: 0.421, unit: 'A'}, Cv: {value: 3.1, unit: 'V'}}
    );
    assert.equal(d.cells.ip.textContent, '0.421 A');
    assert.equal(d.cells.measured.textContent, '');
});

/* queezz, 2026-10-07: "Kikusui output button in WebUI not working". The press
 * is handed to the supply's own thread and answered `applied` at once; when
 * the LAN then stays silent the rig marks the same command `failed`, and the
 * page says the rig's sentence in place of "done". */
test('a press that fails after its answer says why, in the words of the rig', () => {
    const d = build();
    const status = el();
    d.api.listen(status);
    d.api.hold(7);
    const press = {id: 7, kind: 'cathode_output', value: 'cathode output off', outcome: 'applied', reason: ''};
    d.api.paintOutcome({last_command: press});
    assert.equal(status.textContent, 'done: cathode output off');
    const why = "Kikusui output OFF FAILED: the supply's LAN did not answer (lost since 17:08). "
        + 'Press OUTPUT on the supply, or power-cycle it to bring its LAN back; the DAC drive is unchanged.';
    d.api.paintOutcome({last_command: {...press, outcome: 'failed', reason: why}});
    assert.equal(status.textContent, why);
    // Said once: a later poll of the same record changes nothing.
    status.textContent = 'something since';
    d.api.paintOutcome({last_command: {...press, outcome: 'failed', reason: why}});
    assert.equal(status.textContent, 'something since');
    // Another browser's failed press is not this page's to announce.
    d.api.paintOutcome({last_command: {...press, id: 8, outcome: 'failed', reason: why}});
    assert.equal(status.textContent, 'something since');
});

/* queezz, 2026-10-07: "The current card keeps changing width. Due to current
 * readouts, no doubt." Ip is read to the milliampere in fixed notation, so a
 * reading hovering about zero keeps the line's length steady. */
test('Ip is read to the milliampere in fixed notation, so the line keeps its length', () => {
    const d = build();
    const read = value => {
        d.api.paintCathode({setpoints: {cathode_mv: 1780}}, {Ip: {value, unit: 'A'}});
        return d.cells.ip.textContent;
    };
    assert.equal(read(0.4163), '0.416 A');
    assert.equal(read(-0.00472), '-0.005 A');
    assert.equal(read(0.012), '0.012 A');
    assert.equal(read(1.2345), '1.234 A');
    // No negative zero, and the general format past 10 A.
    assert.equal(read(-0.0001), '0.000 A');
    assert.equal(read(12.5), '12.5 A');
    // Every reading below 1 A is the same length.
    assert.equal(new Set([0.4163, -0.00472, 0.012, -0.3].map(v => read(v).replace('-', '').length)).size, 1);
    assert.equal(d.cells.fold.textContent, 'manual 1780 mV · read -0.300 A');
});

/* 2026-10-02, 17:23:44. A laptop's page had been open since before a phone
 * set the cathode to 1800 mV. The laptop took control, its Drive field still
 * read the 0 it was loaded with, one step-down press sent 0 mV three seconds
 * later, and the plasma went out. The field was filled once, at page load. */
test('a field nobody is editing reads the rig, so a step starts from what is held', () => {
    const d = build();
    d.api.setupDraftRow(d.manualRow, d.api.CATHODE_DRAFT);
    d.api.paintCathode({setpoints: {cathode_mv: 0}}, {});
    assert.equal(+d.input.value, 0);

    // Somebody else sets the drive; this page is only watching.
    d.api.paintCathode({setpoints: {cathode_mv: 1800}}, {});
    assert.equal(+d.input.value, 1800);
    assert.equal(d.note.textContent, 'Draft matches applied');

    d.steps['-10'].press();
    assert.equal(+d.input.value, 1790, 'ten down from what the rig holds, not from the page load');
    d.setButton.press();
    assert.deepEqual(JSON.parse(JSON.stringify(d.sent[0].body)), {mv: 1790});
});

test('once a draft is what the rig holds, the field follows the rig again', () => {
    const d = build();
    d.api.setupDraftRow(d.manualRow, d.api.CATHODE_DRAFT);
    d.api.paintCathode({setpoints: {cathode_mv: 1800}}, {});
    d.steps['-10'].press();
    d.api.paintCathode({setpoints: {cathode_mv: 1800}}, {});
    assert.equal(+d.input.value, 1790, 'an unsent draft is the reader\'s');
    d.api.paintCathode({setpoints: {cathode_mv: 1790}}, {});     // Set was applied
    d.api.paintCathode({setpoints: {cathode_mv: 1700}}, {});     // then it moved again
    assert.equal(+d.input.value, 1700);
});

test('control changing hands drops whatever was half-typed', () => {
    const d = build();
    d.api.setupDraftRow(d.manualRow, d.api.CATHODE_DRAFT);
    d.api.noteControl({control: {mine: false}});
    d.api.paintCathode({setpoints: {cathode_mv: 1800}}, {});
    d.input.value = '250';
    d.input.handlers.input();
    d.api.paintCathode({setpoints: {cathode_mv: 1800}}, {});
    assert.equal(+d.input.value, 250);

    d.api.noteControl({control: {mine: true}});                  // Take over
    d.api.paintCathode({setpoints: {cathode_mv: 1800}}, {});
    assert.equal(+d.input.value, 1800);
    // Holding control steadily is not a change of hands.
    d.input.value = '1810';
    d.input.handlers.input();
    d.api.noteControl({control: {mine: true}});
    d.api.paintCathode({setpoints: {cathode_mv: 1800}}, {});
    assert.equal(+d.input.value, 1810);
});

test('with the loop on, the manual field reads the loop\'s command', () => {
    // "There is no signal voltage exposed from PID run, so I can use that to
    // start the manual emission" (queezz, 2026-10-02).
    const d = build();
    d.api.setupDraftRow(d.manualRow, d.api.CATHODE_DRAFT);
    d.api.paintCathode({setpoints: {plasma_a: 0.5, cathode_mv: 1773.4}}, {Ip: {value: 0.505, unit: 'A'}});
    assert.equal(d.cells.feedback.textContent, 'Held · PID 0.50 A · 1773 mV');
    assert.equal(+d.input.value, 1773);
    // The folded row keeps its two facts and does not grow.
    assert.equal(d.cells.fold.textContent, 'PID 0.50 A · read 0.505 A');
    // Before the loop's first command is recorded there is no number to show.
    d.api.paintCathode({setpoints: {plasma_a: 0.5, cathode_mv: 0}}, {});
    assert.equal(d.cells.feedback.textContent, 'Held · PID 0.50 A');
});
