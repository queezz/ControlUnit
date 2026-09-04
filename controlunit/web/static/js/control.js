/* The Control tab: what the rig holds, and what a browser may ask it to hold.
 *
 * No framework, nothing fetched from the internet. A press posts a small
 * JSON body and gets back only an acknowledgement; what actually happened is
 * read from the next /api/state, once a second, like every other tab. The
 * page never assumes its own request succeeded.
 *
 * Every update writes into elements that already exist, so a value changing
 * under the reader never moves anything, and the one status line changes in
 * place rather than appearing above the controls it reports on.
 */
(function () {
    "use strict";

    var STATE_MS = 1000;

    var root = document.getElementById("control");
    if (!root) return;

    var status = root.querySelector('[data-role="status"]');
    var actorInput = document.getElementById("actor-name");
    var actor = (root.dataset.actor || "").trim();

    /* The command this browser is waiting to hear about. The rig answers
       through /api/state, so the wait ends when that record names this id. */
    var pending = 0;

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
    }

    function readings(state) {
        var map = {};
        (state.channels || []).forEach(function (channel) { map[channel.name] = channel; });
        return map;
    }

    function paintGas(state, map) {
        var sp = state.setpoints || {};
        root.querySelectorAll("[data-mfc]").forEach(function (row) {
            var number = row.dataset.mfc;
            var held = Number(sp["mfc" + number + "_v"] || 0);
            row.querySelector('[data-role="mfc-setpoint"]').textContent =
                Math.round(held) + " mV";
            var measured = map["MFC" + number];
            row.querySelector('[data-role="mfc-measured"]').textContent =
                measured && measured.value !== null && measured.value !== undefined
                    ? Math.round(Number(measured.value) * 1000) + " mV"
                    : "—";
        });
    }

    function paintPlasma(state, map) {
        var sp = state.setpoints || {};
        var held = Number(sp.plasma_a || 0);
        set('[data-role="plasma-setpoint"]', held ? held.toFixed(2) + " A" : "off");
        var ip = map.Ip;
        set('[data-role="plasma-measured"]', ip ? fmt(ip.value, ip.unit) + " A" : "—");

        var row = root.querySelector('[data-role="cathode-row"]');
        var cathode = map.Cv;
        if (row) {
            row.hidden = !cathode;
            if (cathode) {
                set('[data-role="cathode-measured"]', fmt(cathode.value, cathode.unit) + " " + (cathode.unit || ""));
            }
        }
    }

    function paintGauge(state) {
        var sp = state.setpoints || {};
        var mode = sp.ig_mode || null;
        var range = sp.ig_range;
        set('[data-role="gauge-mode-now"]', mode || "—");
        set('[data-role="gauge-range-now"]', range === null || range === undefined ? "—" : "1e" + range);
        set('[data-role="sync-now"]', sp.sync ? "on" : "off");

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
        root.querySelectorAll("[data-zero]").forEach(function (row) {
            var channel = row.dataset.zero;
            var unit = (map[channel] && map[channel].unit) || "";
            var zero = zeros[channel];
            row.querySelector('[data-role="zero-value"]').textContent =
                zero === undefined || zero === null ? "—" : fmt(Number(zero), unit) + " " + unit;
            var reading = map[channel];
            row.querySelector('[data-role="zero-measured"]').textContent =
                reading ? fmt(reading.value, reading.unit) + " " + (reading.unit || "") : "—";
        });
    }

    function set(selector, text) {
        var el = root.querySelector(selector);
        if (el) el.textContent = text;
    }

    /* The gate, in one place. Setting needs the switch on the rig's own
       screen, a name in this browser, and workers running; the reason is
       stated here once and never repeated beside a control. */
    function paintGate(state) {
        var chip = root.querySelector('[data-role="remote-chip"]');
        if (chip) {
            chip.textContent = state.remote ? "on" : "off";
            chip.className = "chip chip-" + (state.remote ? "live" : "idle");
        }

        var why = "";
        if (!state.remote) why = "Setting is off until the switch on the rig is on.";
        else if (!actor) why = "Setting is off until you save a name below.";
        else if (!state.acquiring) why = "Setting is off while no acquisition is running.";
        else why = "You may set what the rig holds.";
        var line = root.querySelector('[data-role="remote-why"]');
        if (line) line.textContent = why;

        var allowed = Boolean(state.remote) && Boolean(actor) && Boolean(state.acquiring);
        root.querySelectorAll(".page-main button, .page-main input").forEach(function (control) {
            control.disabled = !allowed;
        });
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
        paintPlasma(state, map);
        paintGauge(state);
        paintBaselines(state, map);
        paintGate(state);
        paintOutcome(state);
    }

    function pollState() {
        fetch("/api/state", {headers: {Accept: "application/json"}})
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (state) { if (state) paint(state); })
            .catch(function () { /* keep what is on the page */ });
    }

    // -- controls -------------------------------------------------------------

    function wire() {
        var save = root.querySelector('[data-role="save-actor"]');
        if (save) save.addEventListener("click", function () {
            var name = (actorInput.value || "").trim();
            say("saving the name …");
            post("/api/identify", {name: name}).then(function (answer) {
                if (answer.status === 200) {
                    actor = answer.body.actor || "";
                    actorInput.value = actor;
                    say("acting as " + actor);
                } else {
                    say("refused: " + (answer.body.reason || "that name will not do"));
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

        root.querySelectorAll("[data-mfc]").forEach(function (row) {
            var number = row.dataset.mfc;
            var input = row.querySelector('[data-role="mfc-input"]');
            row.querySelector('[data-role="mfc-set"]').addEventListener("click", function () {
                send("/api/mfc/" + number, {mv: Number(input.value)}, "the flow setpoint");
            });
            row.querySelector('[data-role="mfc-zero"]').addEventListener("click", function () {
                input.value = 0;
                send("/api/mfc/" + number, {mv: 0}, "the flow setpoint");
            });
        });

        var plasmaInput = root.querySelector('[data-role="plasma-input"]');
        root.querySelector('[data-role="plasma-set"]').addEventListener("click", function () {
            send("/api/plasma-current", {a: Number(plasmaInput.value)}, "the plasma setpoint");
        });
        root.querySelector('[data-role="plasma-off"]').addEventListener("click", function () {
            send("/api/plasma-current", {off: true}, "the plasma PID off");
        });

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
        root.querySelectorAll("[data-zero]").forEach(function (row) {
            row.querySelector('[data-role="zero-now"]').addEventListener("click", function () {
                send("/api/zero", {channel: row.dataset.zero}, "the baseline of " + row.dataset.zero);
            });
        });
    }

    function setup() {
        wire();
        pollState();
        window.setInterval(pollState, STATE_MS);
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup);
    else setup();
}());
