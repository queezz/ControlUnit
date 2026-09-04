/* The Live tab: readouts, two strip charts, and the rails that drive them.
 *
 * No framework, nothing fetched from the internet. The page polls the state
 * once a second and the series every two seconds, and every update writes
 * into elements that already exist and already have their room reserved in
 * CSS, so a value changing under the reader never moves anything.
 *
 * The charts are plain <canvas> panels: a faint grid, a log axis for
 * pressure, the rig's own five pen colours, and an emphasised end point.
 * Nothing animates.
 */
(function () {
    "use strict";

    var STATE_MS = 1000;
    var SERIES_MS = 2000;
    var STORE_KEY = "controlunit.live";

    var root = document.getElementById("live");
    if (!root) return;

    var pens = {};
    try {
        JSON.parse(root.dataset.pens || "[]").forEach(function (pair) { pens[pair[0]] = pair[1]; });
    } catch (e) { /* the readouts still work without colour */ }

    var PRESSURE = ["Pu", "Pd", "Bu", "Bd"];

    var view = {
        window: Number(root.dataset.defaultWindow || 300),
        channels: {Ip: true, Pu: true, Pd: true, Bu: true, Bd: true},
        log: true
    };

    /* A remembered window, channel set and axis choice are conveniences,
       never facts: the page renders correctly with none of them stored. */
    function remember() {
        try { localStorage.setItem(STORE_KEY, JSON.stringify(view)); } catch (e) { /* fine */ }
    }
    function recall() {
        try {
            var kept = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
            if (!kept) return;
            if (typeof kept.window === "number") view.window = kept.window;
            if (kept.channels) Object.keys(view.channels).forEach(function (name) {
                if (typeof kept.channels[name] === "boolean") view.channels[name] = kept.channels[name];
            });
            if (typeof kept.log === "boolean") view.log = kept.log;
        } catch (e) { /* fine */ }
    }

    var series = {channels: {}, from: null, to: null};

    // -- formatting ---------------------------------------------------------

    function fmtValue(value, unit) {
        if (value === null || value === undefined || !isFinite(value)) return "—";
        var magnitude = Math.abs(value);
        if (unit === "Torr" || (magnitude !== 0 && (magnitude < 0.01 || magnitude >= 1e5))) {
            return value.toExponential(2).replace("e-", "e-").replace("e+", "e");
        }
        return value.toFixed(magnitude >= 100 ? 0 : magnitude >= 10 ? 1 : 3);
    }

    function fmtSeconds(seconds) {
        if (seconds === null || seconds === undefined || !isFinite(seconds)) return "";
        if (seconds < 60) return seconds.toFixed(1) + " s";
        var minutes = Math.floor(seconds / 60);
        if (minutes < 60) return minutes + " m " + Math.floor(seconds % 60) + " s";
        var hours = Math.floor(minutes / 60);
        return hours + " h " + (minutes % 60) + " m";
    }

    function fmtClock(epoch) {
        var d = new Date(epoch * 1000);
        function two(n) { return (n < 10 ? "0" : "") + n; }
        return two(d.getHours()) + ":" + two(d.getMinutes()) + ":" + two(d.getSeconds());
    }

    function fmtStarted(epoch, elapsed) {
        if (!epoch) return "—";
        return fmtClock(epoch) + ", " + fmtSeconds(elapsed) + " ago";
    }

    // -- state ---------------------------------------------------------------

    function paintState(state) {
        state.channels.forEach(function (channel) {
            var box = root.querySelector('.readout[data-readout="' + channel.name + '"]');
            if (!box) return;
            box.querySelector('[data-role="value"]').textContent = fmtValue(channel.value, channel.unit);
            box.querySelector('[data-role="unit"]').textContent = channel.unit || "";
        });

        var run = state.run || {};
        text("file", run.file || "—");
        text("started", fmtStarted(run.started_at, run.elapsed));
        text("samples", run.samples !== undefined ? String(run.samples) : "—");
        text("rate", run.rate || "—");
        text("hardware", state.dummy ? "dummy" : "real");

        var sp = state.setpoints || {};
        text("plasma", sp.plasma_a ? "on, " + Number(sp.plasma_a).toFixed(2) + " A" : "off");
        var mfc1 = sp.mfc1_v !== undefined ? Math.round(Number(sp.mfc1_v) * 1000) : 0;
        var mfc2 = sp.mfc2_v !== undefined ? Math.round(Number(sp.mfc2_v) * 1000) : 0;
        text("mfc", "H₂ " + mfc1 + " mV · O₂ " + mfc2 + " mV");

        var data = state.data || {};
        var chip = root.querySelector('[data-role="data-state"]');
        if (chip) {
            chip.textContent = data.state || "idle";
            chip.className = "chip chip-" + (data.state || "idle");
        }
        var age = root.querySelector('[data-role="data-age"]');
        if (age) age.textContent = data.age === null || data.age === undefined ? "" : fmtSeconds(data.age) + " ago";
        var after = root.querySelector('[data-role="stale-after"]');
        if (after && data.stale_after) after.textContent = String(Number(data.stale_after));
    }

    function text(fact, value) {
        var el = root.querySelector('[data-fact="' + fact + '"]');
        if (el) el.textContent = value;
    }

    function pollState() {
        fetch("/api/state", {headers: {Accept: "application/json"}})
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (state) { if (state) paintState(state); })
            .catch(function () { /* keep what is on the page */ });
    }

    function pollSeries() {
        fetch("/api/series?window=" + encodeURIComponent(view.window), {headers: {Accept: "application/json"}})
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (body) {
                if (!body || !body.channels) return;
                series = body;
                drawAll();
            })
            .catch(function () { /* keep the last drawing */ });
    }

    // -- charts --------------------------------------------------------------

    var plasma = document.getElementById("chart-plasma");
    var pressure = document.getElementById("chart-pressure");

    function niceTicks(lo, hi, count) {
        if (!(hi > lo)) { hi = lo + 1; lo = lo - 1; }
        var span = hi - lo;
        var rough = span / Math.max(1, count);
        var power = Math.pow(10, Math.floor(Math.log10(rough)));
        var candidates = [1, 2, 5, 10];
        var step = candidates[0] * power;
        for (var i = 0; i < candidates.length; i++) {
            if (candidates[i] * power >= rough) { step = candidates[i] * power; break; }
        }
        var ticks = [];
        for (var v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) ticks.push(v);
        return ticks;
    }

    function timeTicks(from, to, count) {
        var span = Math.max(1, to - from);
        var steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200];
        var step = steps[steps.length - 1];
        for (var i = 0; i < steps.length; i++) {
            if (span / steps[i] <= count) { step = steps[i]; break; }
        }
        var ticks = [];
        for (var t = Math.ceil(from / step) * step; t <= to; t += step) ticks.push(t);
        return ticks;
    }

    function prepare(canvas) {
        var ratio = window.devicePixelRatio || 1;
        var width = canvas.clientWidth || canvas.parentNode.clientWidth || 600;
        var height = Number(canvas.getAttribute("height")) || 220;
        canvas.style.height = height + "px";
        if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
            canvas.width = Math.round(width * ratio);
            canvas.height = Math.round(height * ratio);
        }
        var ctx = canvas.getContext("2d");
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        return {ctx: ctx, width: width, height: height};
    }

    function styles() {
        var cs = getComputedStyle(document.documentElement);
        return {
            grid: cs.getPropertyValue("--line-soft").trim() || "rgba(255,255,255,0.06)",
            axis: cs.getPropertyValue("--line").trim() || "rgba(255,255,255,0.11)",
            text: cs.getPropertyValue("--dim").trim() || "rgba(236,233,226,0.42)",
            mono: cs.getPropertyValue("--mono").trim() || "monospace"
        };
    }

    /* Draw one panel: `names` in the given pens, `logScale` for the y axis. */
    function draw(canvas, names, logScale) {
        var box = prepare(canvas);
        var ctx = box.ctx;
        var st = styles();
        var pad = {left: 64, right: 14, top: 10, bottom: 26};
        var plotW = box.width - pad.left - pad.right;
        var plotH = box.height - pad.top - pad.bottom;

        ctx.clearRect(0, 0, box.width, box.height);

        // Gather the points to draw and the y range they need.
        var lines = [];
        var lo = Infinity, hi = -Infinity;
        names.forEach(function (name) {
            if (!view.channels[name]) return;
            var points = (series.channels && series.channels[name]) || [];
            var kept = [];
            points.forEach(function (p) {
                var v = p[1];
                if (v === null || v === undefined || !isFinite(v)) return;
                if (logScale) {
                    if (!(v > 0)) return;
                    v = Math.log10(v);
                }
                kept.push([p[0], v]);
                if (v < lo) lo = v;
                if (v > hi) hi = v;
            });
            lines.push({name: name, points: kept});
        });

        var from = series.from, to = series.to;
        if (from === null || from === undefined || to === null || to === undefined) {
            from = Date.now() / 1000 - (view.window || 300);
            to = Date.now() / 1000;
        }
        if (view.window > 0) from = Math.max(from, to - view.window);
        if (!(to > from)) to = from + 1;

        if (!isFinite(lo)) { lo = logScale ? -8 : 0; hi = logScale ? 0 : 1; }
        if (hi - lo < 1e-12) { lo -= logScale ? 0.5 : (Math.abs(lo) * 0.05 || 0.5); hi += logScale ? 0.5 : (Math.abs(hi) * 0.05 || 0.5); }
        if (logScale) { lo = Math.floor(lo); hi = Math.ceil(hi); if (hi === lo) hi = lo + 1; }
        else { var margin = (hi - lo) * 0.08; lo -= margin; hi += margin; }

        function x(t) { return pad.left + (t - from) / (to - from) * plotW; }
        function y(v) { return pad.top + (hi - v) / (hi - lo) * plotH; }

        // Grid and axes.
        ctx.font = "11px " + st.mono;
        ctx.fillStyle = st.text;
        ctx.strokeStyle = st.grid;
        ctx.lineWidth = 1;

        var yTicks = logScale ? niceTicks(lo, hi, 6).filter(function (v) { return Math.abs(v - Math.round(v)) < 1e-9; }) : niceTicks(lo, hi, 5);
        if (logScale && yTicks.length < 2) yTicks = niceTicks(lo, hi, 6);
        ctx.textAlign = "right";
        ctx.textBaseline = "middle";
        yTicks.forEach(function (v) {
            var yy = Math.round(y(v)) + 0.5;
            ctx.beginPath(); ctx.moveTo(pad.left, yy); ctx.lineTo(pad.left + plotW, yy); ctx.stroke();
            var label = logScale ? "1e" + Math.round(v) : fmtValue(v, "");
            ctx.fillText(label, pad.left - 8, yy);
        });

        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        timeTicks(from, to, Math.max(2, Math.floor(plotW / 90))).forEach(function (t) {
            var xx = Math.round(x(t)) + 0.5;
            ctx.beginPath(); ctx.moveTo(xx, pad.top); ctx.lineTo(xx, pad.top + plotH); ctx.stroke();
            ctx.fillText(fmtClock(t), xx, pad.top + plotH + 6);
        });

        ctx.strokeStyle = st.axis;
        ctx.beginPath();
        ctx.moveTo(pad.left + 0.5, pad.top); ctx.lineTo(pad.left + 0.5, pad.top + plotH + 0.5);
        ctx.lineTo(pad.left + plotW, pad.top + plotH + 0.5);
        ctx.stroke();

        // The lines, and an emphasised end point on each.
        lines.forEach(function (line) {
            if (!line.points.length) return;
            ctx.strokeStyle = pens[line.name] || "#ffffff";
            ctx.fillStyle = ctx.strokeStyle;
            ctx.lineWidth = 1.5;
            ctx.lineJoin = "round";
            ctx.beginPath();
            line.points.forEach(function (p, i) {
                var xx = x(p[0]), yy = y(p[1]);
                if (i === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
            });
            ctx.stroke();
            var last = line.points[line.points.length - 1];
            ctx.beginPath();
            ctx.arc(x(last[0]), y(last[1]), 3, 0, Math.PI * 2);
            ctx.fill();
        });

        return {from: from, to: to, count: series.count || 0};
    }

    function drawAll() {
        var a = draw(plasma, ["Ip"], false);
        var b = draw(pressure, PRESSURE, view.log);
        var span = root.querySelector('[data-role="span-plasma"]');
        var label = spanLabel(a);
        if (span) span.textContent = label;
        var span2 = root.querySelector('[data-role="span-pressure"]');
        if (span2) span2.textContent = spanLabel(b);
    }

    function spanLabel(drawn) {
        if (!drawn || !drawn.count) return "no samples yet";
        var seconds = Math.max(0, Math.round(drawn.to - drawn.from));
        return "last " + fmtSeconds(seconds) + " · " + drawn.count + " samples";
    }

    // -- rail controls -------------------------------------------------------

    function press(group, attribute, value) {
        root.querySelectorAll(group).forEach(function (button) {
            button.setAttribute("aria-pressed", String(button.dataset[attribute]) === String(value) ? "true" : "false");
        });
    }

    function setupRails() {
        root.querySelectorAll("[data-window]").forEach(function (button) {
            button.addEventListener("click", function () {
                view.window = Number(button.dataset.window);
                press("[data-window]", "window", view.window);
                remember();
                pollSeries();
            });
        });
        root.querySelectorAll("[data-channel]").forEach(function (button) {
            button.addEventListener("click", function () {
                var name = button.dataset.channel;
                view.channels[name] = !view.channels[name];
                button.setAttribute("aria-pressed", view.channels[name] ? "true" : "false");
                remember();
                drawAll();
            });
        });
        root.querySelectorAll("[data-scale]").forEach(function (button) {
            button.addEventListener("click", function () {
                view.log = button.dataset.scale === "log";
                press("[data-scale]", "scale", view.log ? "log" : "lin");
                remember();
                drawAll();
            });
        });
    }

    function reflectView() {
        press("[data-window]", "window", view.window);
        Object.keys(view.channels).forEach(function (name) {
            var button = root.querySelector('[data-channel="' + name + '"]');
            if (button) button.setAttribute("aria-pressed", view.channels[name] ? "true" : "false");
        });
        press("[data-scale]", "scale", view.log ? "log" : "lin");
    }

    function setup() {
        recall();
        reflectView();
        setupRails();
        drawAll();
        pollState();
        pollSeries();
        window.setInterval(pollState, STATE_MS);
        window.setInterval(pollSeries, SERIES_MS);
        var pending = null;
        window.addEventListener("resize", function () {
            if (pending) window.clearTimeout(pending);
            pending = window.setTimeout(drawAll, 80);
        });
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup);
    else setup();
}());
