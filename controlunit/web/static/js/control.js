/* Live operation: what the rig holds, and what a browser may ask it to hold.
 *
 * No framework, nothing fetched from the internet. A press posts a small
 * JSON body and gets back only an acknowledgement; what actually happened is
 * read from the next /api/state, once a second, like every other tab. The
 * page never assumes its own request succeeded.
 *
 * Every update writes into elements that already exist, so a value changing
 * under the reader never moves anything, and the one status line changes in
 * place rather than appearing above the controls it reports on.
 *
 * Who has the rig is the rig's answer too, never this page's guess: the
 * holder line and whether the reader is the holder both arrive in
 * /api/state, so a page whose person lost control learns it within a poll.
 */
(function () {
    "use strict";

    var STATE_MS = 1000;

    /* Stopping ends the run, so it is asked once, here, in the browser's own
       words — the same sentence the group's note carries, because a person
       must not read one thing and be asked another. The rig's own switch
       asks the same question in a Qt popup. */
    var STOP_QUESTION =
        "Stopping closes the data file and turns every output off. " +
        "Stop acquisition?";

    var root = document.getElementById("control");
    if (!root) return;

    var status = root.querySelector('[data-role="status"]');
    var actorInput = document.getElementById("actor-name");
    var actor = (root.dataset.actor || "").trim();
    /* Only on a machine that holds a word of its own; elsewhere the row was
       never rendered and everything below simply finds nothing. */
    var fenceInput = document.getElementById("fence-word");
    var changingWord = false;

    /* The command this browser is waiting to hear about. The rig answers
       through /api/state, so the wait ends when that record names this id. */
    var pending = 0;
    var accessNeedsAttention = null;

    // -- formatting -----------------------------------------------------------

    function fmt(value, unit) {
        if (value === null || value === undefined || !isFinite(value)) return "—";
        var size = Math.abs(value);
        if (unit === "Torr" || (size !== 0 && (size < 0.01 || size >= 1e5))) {
            return value.toExponential(2).replace("e+", "e");
        }
        return value.toFixed(size >= 100 ? 0 : size >= 10 ? 1 : 3);
    }

    function fmtSeconds(seconds) {
        if (seconds === null || seconds === undefined || !isFinite(seconds)) return "";
        if (seconds < 60) return seconds.toFixed(1) + " s";
        var minutes = Math.floor(seconds / 60);
        if (minutes < 60) return minutes + " m " + Math.floor(seconds % 60) + " s";
        return Math.floor(minutes / 60) + " h " + (minutes % 60) + " m";
    }

    function fmtClock(epoch) {
        var d = new Date(epoch * 1000);
        function two(n) { return (n < 10 ? "0" : "") + n; }
        return two(d.getHours()) + ":" + two(d.getMinutes()) + ":" + two(d.getSeconds());
    }

    function facts(name, value) {
        root.querySelectorAll('[data-fact="' + name + '"]').forEach(function (el) {
            el.textContent = value;
        });
    }

    function say(text) {
        if (status) status.textContent = text;
    }

    // -- sending --------------------------------------------------------------

    function post(path, body) {
        return fetch(path, {
            method: "POST",
            headers: {"Content-Type": "application/json", Accept: "application/json"},
            body: JSON.stringify(body || {})
        }).then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (payload) {
                return {ok: response.status === 202, status: response.status, body: payload};
            });
        });
    }

    function send(path, body, what) {
        say("sending " + what + " …");
        post(path, body).then(function (answer) {
            if (answer.ok) {
                pending = answer.body.id || 0;
                say("queued: " + (answer.body.value || what));
            } else {
                pending = 0;
                say("refused: " + (answer.body.reason || "the rig did not accept that"));
            }
            pollState();
        }).catch(function () {
            pending = 0;
            say("the rig did not answer");
        });
    }

    // -- painting -------------------------------------------------------------

    function paintRun(state) {
        var run = state.run || {};
        facts("file", run.file || "—");
        facts("started", run.started_at ? fmtClock(run.started_at) + ", " + fmtSeconds(run.elapsed) + " ago" : "—");
        facts("samples", run.samples !== undefined ? String(run.samples) : "—");
        facts("rate", run.rate || "—");
        facts("hardware", state.dummy ? "dummy" : "real");

        var chip = root.querySelector('[data-role="acq-chip"]');
        if (chip) {
            var word = state.acquiring ? (state.data && state.data.state) || "live" : "idle";
            chip.textContent = word;
            chip.className = "chip chip-" + word;
        }

        /* The sampling time the rig holds, and the rate it works out to —
           the same two facts the right rail carries, said here beside the
           buttons that change them. */
        var sampling = run.sampling === null || run.sampling === undefined
            ? null
            : Number(run.sampling);
        set('[data-role="sampling-now"]',
            sampling === null || !isFinite(sampling)
                ? "—"
                : String(sampling) + " s" + (run.rate ? " · " + run.rate : ""));
        root.querySelectorAll('[data-role="sampling"]').forEach(function (button) {
            var held = sampling !== null && Number(button.dataset.seconds) === sampling;
            button.setAttribute("aria-pressed", held ? "true" : "false");
        });
    }

    function readings(state) {
        var map = {};
        (state.channels || []).forEach(function (channel) { map[channel.name] = channel; });
        return map;
    }

    /* A draft row: a typed value, four sizes of nudge, and a deliberate Set.
       Nothing a step button does leaves the browser — the number in the box
       is a draft until Set is pressed, and a poll that arrives mid-edit must
       not take the reader's typing away.
     *
     * The gas lines and the cathode's manual drive are the same row with
     * different units and a different address, so the logic lives here once
     * and each row brings a small description of itself rather than a copy
     * of this function. */
    var GAS_DRAFT = {
        input: '[data-role="mfc-input"]',
        note: '[data-role="mfc-draft-note"]',
        set: '[data-role="mfc-set"]',
        steps: '[data-mfc-step]',
        stepKey: 'mfcStep',
        /* Zero on a gas line is a setpoint of nought, not a different
           command; the cathode's Off is its own word to the rig. */
        clear: '[data-role="mfc-zero"]',
        clearBody: {mv: 0},
        words: "the flow setpoint",
        path: function (row) { return "/api/mfc/" + row.dataset.mfc; },
        body: function (value) { return {mv: value}; }
    };

    var CATHODE_DRAFT = {
        input: '[data-role="cathode-input"]',
        note: '[data-role="cathode-draft-note"]',
        set: '[data-role="cathode-set"]',
        steps: '[data-cathode-step]',
        stepKey: 'cathodeStep',
        clear: '[data-role="cathode-off"]',
        clearBody: {off: true},
        words: "the cathode drive",
        path: function () { return "/api/cathode"; },
        body: function (value) { return {mv: value}; }
    };

    function draftUsable(input) {
        return input.value !== '' && input.checkValidity();
    }

    /* The presses are in the faceplate and the numbers they move are beside
       it, so a reading is addressed by the line it belongs to rather than
       found inside the row that sets it. */
    function setupDraftRow(row, spec) {
        var input = row.querySelector(spec.input);
        input.addEventListener('input', function () {
            input.dataset.edited = 'true';
            reflectDraft(row, spec);
        });
        row.querySelectorAll(spec.steps).forEach(function (button) {
            button.addEventListener('click', function () {
                if (!draftUsable(input)) { input.reportValidity(); return; }
                input.value = Math.max(Number(input.min), Math.min(Number(input.max), Number(input.value) + Number(button.dataset[spec.stepKey])));
                input.dataset.edited = 'true';
                reflectDraft(row, spec);
            });
        });
        row.querySelector(spec.set).addEventListener("click", function () {
            if (!draftUsable(input)) { input.reportValidity(); return; }
            send(spec.path(row), spec.body(Number(input.value)), spec.words);
        });
        row.querySelector(spec.clear).addEventListener("click", function () {
            input.value = 0;
            input.dataset.edited = 'true';
            reflectDraft(row, spec);
            send(spec.path(row), spec.clearBody, spec.words);
        });
    }

    function setupGasRow(row) { setupDraftRow(row, GAS_DRAFT); }

    function reflectDraft(row, spec) {
        var input = row.querySelector(spec.input);
        var changed = input.value === '' || Number(input.value) !== Number(row.dataset.applied);
        row.classList.toggle('flow-draft-changed', changed);
        var note = row.querySelector(spec.note);
        if (note) note.textContent = changed ? 'Draft · press Set to apply' : 'Draft matches applied';
    }

    function paintGas(state, map) {
        var sp = state.setpoints || {};
        root.querySelectorAll(".frow[data-mfc]").forEach(function (row) {
            var number = row.dataset.mfc;
            var held = Number(sp["mfc" + number + "_v"] || 0);
            row.dataset.applied = String(held);
            var input = row.querySelector('[data-role="mfc-input"]');
            if (!input.dataset.initialized) {
                if (!input.dataset.edited) input.value = Math.round(held);
                input.dataset.initialized = 'true';
            }
            reflectDraft(row, GAS_DRAFT);
            set('[data-role="mfc-setpoint"][data-mfc="' + number + '"]',
                Math.round(held) + " mV");
            var measured = map["MFC" + number];
            set('[data-role="mfc-measured"][data-mfc="' + number + '"]',
                measured && measured.value !== null && measured.value !== undefined
                    ? Math.round(Number(measured.value) * 1000) + " mV"
                    : "—");
        });
    }

    /* Which setter this browser is shown. It is a view choice and never a
       command: pressing PID or Manual sends nothing, and the rig is not told
       about it. Kept per browser, because which knob a person reaches for is
       theirs and not the rig's; a browser that stores nothing simply starts
       on PID every time.

       `aria-pressed` is the only state written: the segmented pill's thumb
       slides under whichever side carries it, derived in CSS from that one
       attribute, so there is no second place for the switch's position to
       drift from what the keyboard and a screen reader are told. */
    var CATHODE_MODE_KEY = "controlunit.cathode.mode";

    function readCathodeMode() {
        try {
            var saved = window.localStorage.getItem(CATHODE_MODE_KEY);
            if (saved === "pid" || saved === "manual") return saved;
        } catch (e) { /* private windows and blocked storage still operate */ }
        return "pid";
    }

    function saveCathodeMode(mode) {
        try { window.localStorage.setItem(CATHODE_MODE_KEY, mode); }
        catch (e) { /* nothing to remember with; the page works regardless */ }
    }

    function showCathodeMode(mode) {
        root.querySelectorAll('[data-role="cathode-mode"]').forEach(function (button) {
            button.setAttribute(
                "aria-pressed", button.dataset.cathodeMode === mode ? "true" : "false"
            );
        });
        var pid = root.querySelector('[data-role="cathode-pid-row"]');
        var manual = root.querySelector('[data-role="cathode-manual-row"]');
        if (pid) pid.hidden = mode !== "pid";
        if (manual) manual.hidden = mode !== "manual";
    }

    /* The right rail's Settings group — QMS sync, sampling, gauges — is the
       one fold on this page whose state is worth keeping. It opens open
       (queezz, 2026-09-10: "I don't like IGs hidden by default. But hiding
       possibility is a right shape, sure."), so nothing a shift may want is
       behind a press it has to discover; folding it is the reader's own act,
       and a browser that has folded it stays folded on the next reload.
       Kept per browser, like the cathode's mode above and for the same
       reason: which drawer a person works with open is theirs, not the
       rig's. Only a browser that has actually chosen overrides the
       template's own `open`, so one that stores nothing — a private window,
       site data blocked — simply starts open every time.

       Read before `revealSection`, so a deep link into a moved section still
       wins and opens the fold on its way in. */
    var SETTINGS_KEY = "controlunit.settings.open";

    function setupSettingsFold() {
        var group = root.querySelector('[data-role="settings-group"]');
        if (!group) return;
        try {
            var chosen = window.localStorage.getItem(SETTINGS_KEY);
            if (chosen !== null) group.open = chosen === "1";
        } catch (e) { /* private windows and blocked storage still operate */ }
        group.addEventListener("toggle", function () {
            try { window.localStorage.setItem(SETTINGS_KEY, group.open ? "1" : "0"); }
            catch (e) { /* nothing to remember with; the page works regardless */ }
        });
    }

    function setupCathodeMode() {
        showCathodeMode(readCathodeMode());
        root.querySelectorAll('[data-role="cathode-mode"]').forEach(function (button) {
            button.addEventListener("click", function () {
                var mode = button.dataset.cathodeMode;
                saveCathodeMode(mode);
                showCathodeMode(mode);
            });
        });
    }

    /* One filament, two ways to drive it, and one line that says which of
       them is actually holding it — read from the rig, never from which
       button this browser last pressed. The PID setpoint wins the sentence
       when it is on, because the loop then owns the DAC; a millivolt value
       with the PID off is the knob held by hand. */
    function paintCathode(state, map) {
        var sp = state.setpoints || {};
        var amperes = Number(sp.plasma_a || 0);
        var millivolts = Number(sp.cathode_mv || 0);
        set('[data-role="plasma-setpoint"]',
            amperes > 0
                ? "Held · PID " + amperes.toFixed(2) + " A"
                : millivolts > 0
                    ? "Held · manual " + Math.round(millivolts) + " mV"
                    : "off");
        var ip = map.Ip;
        set('[data-role="plasma-measured"]', ip ? fmt(ip.value, ip.unit) + " A" : "—");

        var row = root.querySelector('[data-role="cathode-manual-row"]');
        if (row) {
            row.dataset.applied = String(millivolts);
            var input = row.querySelector('[data-role="cathode-input"]');
            if (input && !input.dataset.initialized) {
                if (!input.dataset.edited) input.value = Math.round(millivolts);
                input.dataset.initialized = 'true';
            }
            reflectDraft(row, CATHODE_DRAFT);
        }
        set('[data-role="cathode-applied"]', Math.round(millivolts) + " mV");

        /* The cathode's own voltage is a reading and never a setpoint. The
           channel is prepared and not deployed on this rig, so the cell says
           so plainly rather than showing a number nobody measured. */
        var cathode = map.Cv;
        set('[data-role="cathode-measured"]',
            cathode && cathode.value !== null && cathode.value !== undefined
                ? fmt(cathode.value, cathode.unit) + " " + (cathode.unit || "")
                : "—");
    }

    function paintGauge(state) {
        var sp = state.setpoints || {};
        var mode = sp.ig_mode || null;
        var range = sp.ig_range;
        set('[data-role="gauge-mode-now"]', mode || "—");
        set('[data-role="gauge-range-now"]', range === null || range === undefined ? "—" : "1e" + range);
        set('[data-role="sync-now"]', sp.sync ? "on" : "off");
        var syncCard = root.querySelector('.sync-card');
        if (syncCard) syncCard.classList.toggle('sync-active', Boolean(sp.sync));

        root.querySelectorAll('[data-role="gauge-mode"]').forEach(function (button) {
            button.setAttribute("aria-pressed", button.dataset.mode === mode ? "true" : "false");
        });
        root.querySelectorAll('[data-role="gauge-range"]').forEach(function (button) {
            button.setAttribute("aria-pressed", String(range) === button.dataset.range ? "true" : "false");
        });
        root.querySelectorAll('[data-role="sync"]').forEach(function (button) {
            var on = button.dataset.on === "1";
            button.setAttribute("aria-pressed", Boolean(sp.sync) === on ? "true" : "false");
        });
    }

    function paintBaselines(state, map) {
        var zeros = state.zeros || {};
        root.querySelectorAll('[data-role="zero-value"]').forEach(function (cell) {
            var channel = cell.dataset.zeroRead;
            var unit = (map[channel] && map[channel].unit) || "";
            var zero = zeros[channel];
            cell.textContent =
                zero === undefined || zero === null ? "—" : fmt(Number(zero), unit) + " " + unit;
        });
        root.querySelectorAll('[data-role="zero-measured"]').forEach(function (cell) {
            var reading = map[cell.dataset.zeroRead];
            cell.textContent =
                reading ? fmt(reading.value, reading.unit) + " " + (reading.unit || "") : "—";
        });
    }

    function set(selector, text) {
        var el = root.querySelector(selector);
        if (el) el.textContent = text;
    }

    /* Who has the rig. The sentence is the rig's own — the same one a
       refusal gives as its reason — so this page never words it a second
       way. Whether the reader is the holder is answered by the rig too: a
       browser cannot see its own address, and nothing here carries one
       except this line. */
    /* The lab's word: a fence, not a secret. Where the machine serving this
       page holds one, a browser types it once and carries it after; whether
       this browser is past it is the rig's answer, in /api/state, because a
       page cannot see its own cookies. */
    function fenceClosed(state) {
        var fence = state.fence || {};
        return Boolean(fence.needed) && !fence.passed;
    }

    /* When this machine's copy of the lab's names was last confirmed against
       the journal that keeps them. It rides on the Acting-as heading's own
       line, so it costs the rail no height — which this rail has none of at
       a 700px window — and changing it moves nothing below it. */
    function paintRoster(state) {
        var line = root.querySelector('[data-role="roster-line"]');
        if (!line) return;
        var copy = state.roster;
        line.textContent = copy
            ? "· " + copy.source + " " + copy.at
            : "· names not read yet";
    }

    function paintControl(state) {
        var control = state.control || {};
        set('[data-role="holder"]', control.line || "Nobody has control");

        var take = root.querySelector('[data-role="take-over"]');
        if (take) {
            take.disabled = !(state.remote && !control.mine && !fenceClosed(state));
        }
        return control;
    }

    /* The gate, in one place. Setting needs the switch on the rig's own
       screen, the lab's word where this machine asks for one, workers
       running, and control of the rig; the reason is stated here once and
       never repeated beside a control. */
    function paintGate(state, control) {
        var chip = root.querySelector('[data-role="remote-chip"]');
        if (chip) {
            chip.textContent = state.remote ? "on" : "off";
            chip.className = "chip chip-" + (state.remote ? "live" : "idle");
        }

        /* Control that nobody holds is there for the taking: the first
           setpoint sent claims it. */
        var mine = !control.holder || Boolean(control.mine);
        var fenced = fenceClosed(state);
        /* The field never disappears once the word is in: a word that
           changed has to be typable again. Only what it says changes. */
        if (fenceInput) {
            fenceInput.placeholder = fenced ? "the lab's word, not a secret" : "word saved";
            var editor = root.querySelector('[data-role="fence-editor"]');
            var saved = root.querySelector('[data-role="fence-saved"]');
            if (editor) editor.hidden = !fenced && !changingWord;
            if (saved) saved.hidden = fenced || changingWord;
        }

        var why = "";
        if (!state.remote) why = "Setting is off until the switch on the rig is on.";
        else if (fenced) why = "Setting is off until you type the lab's word below.";
        else if (!state.acquiring) {
            /* Idle is no longer a dead end for the reader who has control:
               it is the one moment Start means something. */
            why = mine
                ? "Nothing is running; you may start acquisition."
                : "Setting is off while no acquisition is running.";
        } else if (!mine) why = "Setting is off until you take control below.";
        else why = "You may set what the rig holds.";
        var line = root.querySelector('[data-role="remote-why"]');
        if (line) line.textContent = why;
        var needsAccess = !state.remote || fenced || !mine;
        var access = root.querySelector(".access-card");
        if (access && needsAccess && accessNeedsAttention !== true) access.open = true;
        accessNeedsAttention = needsAccess;

        /* Everything the gate governs is one block of the faceplate, so the
           blanket names that block rather than the whole column: the name
           field and the lab's word stand outside it deliberately, because
           they are how a person opens the gate and must never be switched
           off by it. */
        var allowed = Boolean(state.remote) && !fenced && Boolean(state.acquiring) && mine;
        root.querySelectorAll(".sets button, .sets input").forEach(function (control) {
            control.disabled = !allowed;
        });

        // Gauge interpretation can be prepared before the ADC starts.
        root.querySelectorAll('[data-role="gauge-mode"], [data-role="gauge-range"]').forEach(function (control) {
            control.disabled = !(Boolean(state.remote) && !fenced && mine);
        });

        /* Start is the one control the run's absence enables rather than
           disables, so it is set after the blanket above rather than being
           an exception written into it. */
        var start = root.querySelector('[data-role="acq-start"]');
        if (start) {
            start.disabled = !(Boolean(state.remote) && !fenced && mine && !state.acquiring);
        }
    }

    function paintOutcome(state) {
        var last = state.last_command;
        if (!last || !pending || last.id < pending) return;
        pending = 0;
        if (last.outcome === "applied") {
            say("done: " + last.value + (last.reason ? " — " + last.reason : ""));
        } else {
            say("refused: " + (last.reason || "the rig did not accept that"));
        }
    }

    function paint(state) {
        var map = readings(state);
        paintRun(state);
        paintGas(state, map);
        paintCathode(state, map);
        paintGauge(state);
        paintBaselines(state, map);
        paintGate(state, paintControl(state));
        paintRoster(state);
        paintOutcome(state);
    }

    function pollState() {
        if (root.hasAttribute("data-live")) {
            root.dispatchEvent(new CustomEvent("controlunit:refresh"));
            return;
        }
        fetch("/api/state", {headers: {Accept: "application/json"}})
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (state) { if (state) paint(state); })
            .catch(function () { /* keep what is on the page */ });
    }

    // -- controls -------------------------------------------------------------

    function wire() {
        /* The field is a text box on a machine with no roster and a list of
           the lab's names on one that has a copy. Both answer to `.value`,
           so the saving is the same either way. */
        var save = root.querySelector('[data-role="save-actor"]');
        if (save && actorInput) save.addEventListener("click", function () {
            var name = (actorInput.value || "").trim();
            say("saving the name …");
            post("/api/identify", {name: name}).then(function (answer) {
                if (answer.status === 200) {
                    actor = answer.body.actor || "";
                    // Option values use the same normalization as the cookie;
                    // their labels retain the roster's full display names.
                    actorInput.value = actor;
                    var label = actorInput.tagName === "SELECT" && actorInput.selectedOptions.length
                        ? actorInput.selectedOptions[0].textContent : actor;
                    set('[data-role="actor-summary"]', label || "Choose operator");
                    say("acting as " + actor);
                } else {
                    say("refused: " + (answer.body.reason || "that name will not do"));
                }
                pollState();
            }).catch(function () { say("the rig did not answer"); });
        });

        /* The lab's word, passed once and carried after. The box is emptied
           on the way out: what is typed here is not a name to keep on the
           page, and the placeholder says whether the fence is behind us. */
        var saveFence = root.querySelector('[data-role="save-fence"]');
        var changeFence = root.querySelector('[data-role="change-fence"]');
        if (changeFence) changeFence.addEventListener("click", function () {
            changingWord = true;
            root.querySelector('[data-role="fence-editor"]').hidden = false;
            root.querySelector('[data-role="fence-saved"]').hidden = true;
            fenceInput.focus();
        });
        if (saveFence && fenceInput) saveFence.addEventListener("click", function () {
            say("saving the word …");
            post("/api/fence", {word: fenceInput.value || ""}).then(function (answer) {
                if (answer.status === 200) {
                    fenceInput.value = "";
                    changingWord = false;
                    say(answer.body.fenced ? "the fence is open" : "this rig asks for no word");
                } else {
                    say("refused: " + (answer.body.reason || "that is not the lab's word"));
                }
                pollState();
            }).catch(function () { say("the rig did not answer"); });
        });

        var take = root.querySelector('[data-role="take-over"]');
        if (take) take.addEventListener("click", function () {
            say("taking control …");
            post("/api/take-over", {}).then(function (answer) {
                if (answer.status === 200) {
                    say(answer.body.changed ? "you have control" : "you already had control");
                } else {
                    say("refused: " + (answer.body.reason || "the rig did not accept that"));
                }
                pollState();
            }).catch(function () { say("the rig did not answer"); });
        });

        var stop = root.querySelector('[data-role="stop-all"]');
        if (stop) stop.addEventListener("click", function () {
            // The rig's own spinboxes go to zero with the outputs; these
            // boxes hold what this reader typed, so they go too rather than
            // sitting there inviting the setpoint to be sent again.
            root.querySelectorAll(".setpoint").forEach(function (box) { box.value = 0; });
            send("/api/stop-all", {}, "stop all outputs");
        });

        var start = root.querySelector('[data-role="acq-start"]');
        if (start) start.addEventListener("click", function () {
            send("/api/acquisition/start", {}, "the start of acquisition");
        });

        var stopRun = root.querySelector('[data-role="acq-stop"]');
        if (stopRun) stopRun.addEventListener("click", function () {
            // Ending a run closes the file and drops every output, so it is
            // asked once here and sent only on yes.
            if (!window.confirm(STOP_QUESTION)) return;
            send("/api/acquisition/stop", {}, "the stop of acquisition");
        });

        root.querySelectorAll('[data-role="sampling"]').forEach(function (button) {
            button.addEventListener("click", function () {
                send(
                    "/api/sampling",
                    {seconds: Number(button.dataset.seconds)},
                    "the sampling time"
                );
            });
        });

        root.querySelectorAll(".frow[data-mfc]").forEach(setupGasRow);

        var plasmaInput = root.querySelector('[data-role="plasma-input"]');
        root.querySelector('[data-role="plasma-set"]').addEventListener("click", function () {
            send("/api/plasma-current", {a: Number(plasmaInput.value)}, "the plasma setpoint");
        });
        root.querySelector('[data-role="plasma-off"]').addEventListener("click", function () {
            send("/api/plasma-current", {off: true}, "the plasma PID off");
        });

        setupSettingsFold();
        setupCathodeMode();
        var manual = root.querySelector('[data-role="cathode-manual-row"]');
        if (manual) setupDraftRow(manual, CATHODE_DRAFT);

        root.querySelectorAll('[data-role="gauge-mode"]').forEach(function (button) {
            button.addEventListener("click", function () {
                send("/api/gauge", {mode: button.dataset.mode}, "the gauge mode");
            });
        });
        root.querySelectorAll('[data-role="gauge-range"]').forEach(function (button) {
            button.addEventListener("click", function () {
                send("/api/gauge", {range: Number(button.dataset.range)}, "the gauge range");
            });
        });
        root.querySelectorAll('[data-role="sync"]').forEach(function (button) {
            button.addEventListener("click", function () {
                send("/api/sync", {on: button.dataset.on === "1"}, "the sync line");
            });
        });
        root.querySelectorAll('[data-role="zero-now"]').forEach(function (button) {
            button.addEventListener("click", function () {
                send("/api/zero", {channel: button.dataset.zero}, "the baseline of " + button.dataset.zero);
            });
        });
    }

    function revealSection() {
        var id;
        try { id = decodeURIComponent(window.location.hash.slice(1)); }
        catch (e) { return; }
        var target = id && document.getElementById(id);
        if (!target || !root.contains(target)) return;
        var parent = target;
        while (parent && parent !== root) {
            if (parent.tagName === "DETAILS") parent.open = true;
            parent = parent.parentElement;
        }
        window.requestAnimationFrame(function () {
            target.scrollIntoView({block: "start"});
        });
    }

    function setup() {
        wire();
        revealSection();
        // Native reload scroll restoration can run after DOMContentLoaded.
        // Land again once the page is laid out, with the heading below chrome.
        window.addEventListener("load", revealSection);
        window.addEventListener("hashchange", revealSection);
        window.addEventListener("popstate", revealSection);
        if (root.hasAttribute("data-live")) {
            root.addEventListener("controlunit:state", function (event) { paint(event.detail); });
            return; // Live owns the single state poll, including fast mode.
        }
        pollState();
        window.setInterval(pollState, STATE_MS);
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup);
    else setup();
}());
