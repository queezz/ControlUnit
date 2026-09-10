/* The Live tab: readouts, three strip charts, and the rails that drive them.
 *
 * No framework, nothing fetched from the internet. Every update writes into
 * elements that already exist and already have their room reserved in CSS,
 * so a value changing under the reader never moves anything.
 *
 * This page keeps its own history. It fills once from the rig's ring when it
 * opens (`window=0`), and after that asks only for what it has not seen
 * (`since=<newest stamp held>`), appending into a per-channel store capped at
 * a day. So the Pi is asked for a handful of rows a poll however long the
 * page has been open, and the window buttons cut what is already here rather
 * than sending anything: `Full` is what this browser has seen. A new run —
 * a different start time or a different file — empties the store and refills
 * it from the ring, because the old run's samples are not this run's.
 *
 * Two of the rail's choices are about how the page itself reads rather than
 * about what it draws. Big turns the five readouts into the column's lead,
 * for reading the rig from a metre away, and is remembered. Fast asks four
 * times a second instead of once or twice, for watching a value settle while
 * a gauge is zeroed at the rig, and is deliberately forgotten on reload: it
 * is for a few minutes under the desk, and a page left open overnight must
 * not keep hammering the Pi.
 *
 * The charts are plain <canvas> panels: a faint grid, the rig's own five pen
 * colours, and an emphasised end point. Three panels, because one pressure
 * axis could not serve both kinds of gauge — the ion gauges cross decades
 * and want a log axis, the Baratrons sit in a narrow band around their own
 * offset and want a linear one, and drawn together neither was readable.
 * Nothing animates.
 */
(function () {
    "use strict";

    var STATE_MS = 1000;
    var SERIES_MS = 2000;
    var FAST_MS = 250;
    var STORE_KEY = "controlunit.live";

    /* The one fill on page open asks for the whole ring at this resolution;
       the polls after it ask `since` and are answered with what arrived. */
    var FILL_POINTS = 3000;

    /* How much history this browser keeps, and a hard cap under it. The day
       is the promise; the count is a guard, because a rig configured at
       10 Hz would put nearly a million points a channel behind that promise
       and no browser draws that. At the rig's own 0.1 Hz a day is 8 640. */
    var STORE_SECONDS = 24 * 60 * 60;
    var STORE_MAX = 20000;

    var root = document.querySelector("[data-live]") || document.getElementById("live");
    if (!root) return;

    var pens = {};
    try {
        JSON.parse(root.dataset.pens || "[]").forEach(function (pair) { pens[pair[0]] = pair[1]; });
    } catch (e) { /* the readouts still work without colour */ }

    var view = {
        window: Number(root.dataset.defaultWindow || 300),
        channels: {Ip: true, Pu: true, Pd: true, Bu: true, Bd: true},
        pinned: {},
        igLog: true,
        barLog: false,
        pressureGroup: "gauge",
        upstreamLog: true,
        downstreamLog: true,
        smooth: 0,
        monitorBig: true,
        big: false
    };

    /* The fast poll lives outside `view` on purpose: `view` is what is
       written to the browser's store, and fast is the one choice a reload
       must not bring back. */
    var fast = false;

    var SMOOTHING = [0, 5, 15, 51];

    /* A remembered window, channel set, axes, smoothing and readout size are
       conveniences, never facts: the page renders correctly with none of
       them stored. A store written before the pressure charts were split
       carries one `log` boolean for both; it is simply not read, and the two
       axes start at their own defaults. */
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
            if (kept.pinned) Object.keys(view.channels).forEach(function (name) {
                if (kept.pinned[name] === true) view.pinned[name] = true;
            });
            if (typeof kept.igLog === "boolean") view.igLog = kept.igLog;
            if (kept.pressureGroup === "vessel") view.pressureGroup = "vessel";
            if (typeof kept.upstreamLog === "boolean") view.upstreamLog = kept.upstreamLog;
            if (typeof kept.downstreamLog === "boolean") view.downstreamLog = kept.downstreamLog;
            if (typeof kept.barLog === "boolean") view.barLog = kept.barLog;
            if (SMOOTHING.indexOf(Number(kept.smooth)) > 0) view.smooth = Number(kept.smooth);
            if (typeof kept.monitorBig === "boolean") view.monitorBig = kept.monitorBig;
            if (typeof kept.big === "boolean") view.big = kept.big;
        } catch (e) { /* fine */ }
    }

    // -- the browser's own history ------------------------------------------

    /* name -> [[t, v], ...], oldest first. `newest` is the stamp every poll
       asks from; `run` is which run these samples belong to. */
    var store = {};
    var newest = null;
    var run = null;
    var filling = false;

    function runKey(state) {
        var r = (state && state.run) || {};
        return String(r.started_at) + "|" + String(r.file || "");
    }

    function forget() {
        store = {};
        newest = null;
    }

    function append(body) {
        var channels = body && body.channels;
        if (!channels) return;
        Object.keys(channels).forEach(function (name) {
            var kept = store[name] || (store[name] = []);
            channels[name].forEach(function (point) {
                var t = point[0];
                if (t === null || t === undefined || !isFinite(t)) return;
                if (kept.length && t <= kept[kept.length - 1][0]) return;
                kept.push([t, point[1]]);
            });
        });
        if (body.to !== null && body.to !== undefined && isFinite(body.to)) {
            if (newest === null || body.to > newest) newest = body.to;
        }
        trim();
    }

    /* A day of samples per channel, and never more points than a browser can
       draw. Both cuts take from the oldest end. */
    function trim() {
        if (newest === null) return;
        var oldest = newest - STORE_SECONDS;
        Object.keys(store).forEach(function (name) {
            var kept = store[name];
            var drop = 0;
            while (drop < kept.length && kept[drop][0] < oldest) drop++;
            if (kept.length - drop > STORE_MAX) drop = kept.length - STORE_MAX;
            if (drop > 0) store[name] = kept.slice(drop);
        });
    }

    function ask(query) {
        return fetch("/api/series?" + query, {headers: {Accept: "application/json"}})
            .then(function (r) { return r.ok ? r.json() : null; });
    }

    /* Everything the rig still holds, at full resolution, once. */
    function fillFromRing() {
        if (filling) return;
        filling = true;
        ask("window=0&points=" + FILL_POINTS)
            .then(function (body) {
                filling = false;
                forget();
                if (body) append(body);
                drawAll();
            })
            .catch(function () { filling = false; });
    }

    function pollSeries() {
        if (newest === null) { fillFromRing(); return; }
        ask("since=" + encodeURIComponent(newest) + "&points=" + FILL_POINTS)
            .then(function (body) {
                if (!body) return;
                append(body);
                drawAll();
            })
            .catch(function () { /* keep the last drawing */ });
    }

    // -- smoothing -----------------------------------------------------------

    /* A centred moving median over `size` samples. A median and not a mean
       because the plasma current's fault is spikes: a mean drags the whole
       neighbourhood towards one bad sample and smears a real step, a median
       ignores it and keeps the step square. The window is clipped at the
       ends of the slice rather than padded, so the line still starts and
       ends where the data does. */
    function median(points, size) {
        if (!size || size < 2 || points.length < 2) return points;
        var half = Math.floor(size / 2);
        var out = [];
        for (var i = 0; i < points.length; i++) {
            var from = Math.max(0, i - half);
            var to = Math.min(points.length - 1, i + half);
            var bag = [];
            for (var j = from; j <= to; j++) {
                var v = points[j][1];
                if (v !== null && v !== undefined && isFinite(v)) bag.push(v);
            }
            if (!bag.length) { out.push([points[i][0], null]); continue; }
            bag.sort(function (a, b) { return a - b; });
            out.push([points[i][0], bag[(bag.length - 1) >> 1]]);
        }
        return out;
    }

    /* What a readout shows while smoothing is on: the median of the newest
       `size` samples this browser holds for that channel. */
    function latestMedian(name, size) {
        var kept = store[name];
        if (!kept || !kept.length) return null;
        var bag = [];
        for (var i = Math.max(0, kept.length - size); i < kept.length; i++) {
            var v = kept[i][1];
            if (v !== null && v !== undefined && isFinite(v)) bag.push(v);
        }
        if (!bag.length) return null;
        bag.sort(function (a, b) { return a - b; });
        return bag[(bag.length - 1) >> 1];
    }

    // -- formatting ---------------------------------------------------------

    var SUPERS = {"0": "⁰", "1": "¹", "2": "²", "3": "³",
        "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷",
        "8": "⁸", "9": "⁹", "-": "⁻"};

    /* An exponent in real superscript glyphs, for the canvas, which has no
       markup to lift one with. */
    function superText(exponent) {
        return String(exponent).split("").map(function (c) {
            return SUPERS[c] || c;
        }).join("");
    }

    function exponential(value, digits) {
        var parts = value.toExponential(digits).split("e");
        return {mantissa: parts[0], exponent: Number(parts[1])};
    }

    function wantsExponent(value, unit) {
        var magnitude = Math.abs(value);
        if (magnitude === 0) return false;
        return unit === "Torr" || magnitude < 0.01 || magnitude >= 1e5;
    }

    function plain(value) {
        var magnitude = Math.abs(value);
        return value.toFixed(magnitude >= 100 ? 0 : magnitude >= 10 ? 1 : 3);
    }

    /* A readout, as markup: `1.22×10⁻⁵` with a real superscript rather than
       `1.22e-5`, which the owner called ugly and is. The <sup> is styled with
       a zero line-height, so lifting the exponent cannot make the line box
       taller and a value crossing between the plain and the exponent form
       never changes the card's height. Zero reads `0`, never `0.00×10⁰`.
       Plain values — a current in amperes — stay plain. */
    function valueHtml(value, unit) {
        if (value === null || value === undefined || !isFinite(value)) return "—";
        if (value === 0) return "0";
        if (!wantsExponent(value, unit)) return plain(value);
        var e = exponential(value, 2);
        return e.mantissa + "×10<sup>" + e.exponent + "</sup>";
    }

    /* The same number for the canvas, where the exponent is glyphs. */
    function valueText(value, unit) {
        if (value === null || value === undefined || !isFinite(value)) return "—";
        if (value === 0) return "0";
        if (!wantsExponent(value, unit)) return plain(value);
        var e = exponential(value, 2);
        return e.mantissa + "×10" + superText(e.exponent);
    }

    /* One axis, one kind of number. The readout formatter is not that: below
       0.01 it turns exponential, so a linear pressure axis came out as
       1.00e-4, 2.00e-4 … above a plain 0.000, two notations on one scale.
       The tick step says how many decimals a label needs; only a step finer
       than a millionth falls back to an exponent, where a plain decimal
       would be unreadable anyway — and that exponent is written the way the
       readouts write theirs, 1.2×10⁻⁷, not 1.2e-7. */
    function fmtTick(value, step) {
        if (value === null || value === undefined || !isFinite(value)) return "";
        var size = Math.abs(step) || Math.abs(value) || 1;
        var decimals = -Math.floor(Math.log10(size));
        if (decimals > 6) {
            var e = exponential(value, 1);
            return e.mantissa + "×10" + superText(e.exponent);
        }
        return value.toFixed(Math.max(0, decimals));
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

    /* How a card says the state its number is in, at each of the three
       widths a tag is written for: roomy, tight, and the tightest. Five
       cards across the Operate column leave the tag between 39px and 56px
       depending on the window and on how wide the channel's own unit is, and
       the words do not all fit in the narrow end of that. */
    function tagForms(held, below) {
        if (held && below) return ["zeroed · below zero", "below zero", "below 0"];
        if (below) return ["below zero", "below zero", "below 0"];
        if (held) return ["zeroed", "zeroed", "zeroed"];
        return ["", "", ""];
    }

    /* The strip settles on one wording, and the narrowest card in it decides
       which: a row that says "below zero" on one card and "below 0" on the
       next reads as sloppiness, not as two different facts.

       Which one is chosen is a question about the window, never about
       today's numbers: the longest form this page can ever need is measured
       against the narrowest tag's own box, so a value crossing zero on one
       card cannot reword another, and a card keeps its wording from poll to
       poll. A clipped word is never a form — "below z…" is worse than the
       short sentence — and no form makes a card taller, because a tag's box
       does not grow with its text. That a baseline is held is said again in
       the rail's Data card, so nothing is lost where that is the part that
       has to go. */
    function paintTags(tags) {
        if (!tags.length) return;
        var narrowest = tags[0];
        tags.forEach(function (tag) {
            if (tag.el.clientWidth < narrowest.el.clientWidth) narrowest = tag;
        });
        var widest = tagForms(true, true);
        var step = widest.length - 1;
        for (var i = 0; i < step; i++) {
            narrowest.el.textContent = widest[i];
            if (narrowest.el.scrollWidth <= narrowest.el.clientWidth + 1) { step = i; break; }
        }
        tags.forEach(function (tag) { tag.el.textContent = tag.forms[step]; });
    }

    function paintState(state) {
        var key = runKey(state);
        if (run === null) run = key;
        else if (key !== run) { run = key; forget(); fillFromRing(); }

        var zeros = state.zeros || {};
        var tags = [];
        state.channels.forEach(function (channel) {
            var box = root.querySelector('.readout[data-readout="' + channel.name + '"]');
            if (!box) return;
            /* With smoothing on the readout is the median of the newest N
               samples this browser holds, so the number and the line beneath
               it are the same reading; with it off the readout is the value
               the rig last published, exactly as before. */
            var value = channel.value;
            if (view.smooth) {
                var smoothed = latestMedian(channel.name, view.smooth);
                if (smoothed !== null) value = smoothed;
            }
            /* The signed number and its unit, always, in the value's own
               size — a negative Baratron reads -5.00×10⁻³ Torr, not the word
               "Below zero" where its number should be (owner, 2026-09-10:
               "text jumps to numbers and back, terrible. We should keep that
               as a READOUT"). */
            box.querySelector('[data-role="value"]').innerHTML = valueHtml(value, channel.unit);
            box.querySelector('[data-role="unit"]').textContent = channel.unit || "";

            /* One tag beside the name says what state the number is in: a
               baseline is held for this channel, the value is negative, or
               both. Empty otherwise, and empty it occupies no room, so the
               card is the same height at every poll. */
            var note = box.querySelector('[data-role="readout-note"]');
            if (note) {
                var below = value !== null && value !== undefined && isFinite(value) && value < 0;
                var held = Number(zeros[channel.name] || 0) !== 0;
                note.classList.toggle("readout-note--below", below);
                tags.push({el: note, forms: tagForms(held, below)});
            }
        });
        // Which of those forms every card carries is settled once, for the
        // whole strip, after all five have been written.
        paintTags(tags);

        var runFacts = state.run || {};
        text("file", runFacts.file || "—");
        text("started", fmtStarted(runFacts.started_at, runFacts.elapsed));
        text("samples", runFacts.samples !== undefined ? String(runFacts.samples) : "—");
        text("rate", runFacts.rate || "—");
        text("hardware", state.dummy ? "dummy" : "real");

        var sp = state.setpoints || {};
        text("plasma", sp.plasma_a ? "on, " + Number(sp.plasma_a).toFixed(2) + " A" : "off");
        /* `mfc1_v` and `mfc2_v` are already millivolts, whatever the `_v` in
           their names suggests: the rig's own four spinboxes are read as
           1000/100/10/1 (`gas_flow.get_massflow_from_gui`) and that whole
           number is what the main thread records. The Control tab reads the
           same field as millivolts; this one multiplied by a thousand as
           well, so a 1234 mV setpoint read here as "1234000 mV". */
        var mfc1 = sp.mfc1_v !== undefined ? Math.round(Number(sp.mfc1_v)) : 0;
        var mfc2 = sp.mfc2_v !== undefined ? Math.round(Number(sp.mfc2_v)) : 0;
        text("mfc", "H₂ " + mfc1 + " mV · O₂ " + mfc2 + " mV");

        /* What the rig is doing, which is not what the acquisition flag
           says: gas and cathode can be held with nothing recording. The
           chip's class is the state with its space taken out, so `outputs
           live` wears `chip-outputs`. */
        var operating = state.operating || {};
        var doing = operating.state || "stopped";
        var rig = root.querySelector('[data-role="operating"]');
        if (rig) {
            rig.textContent = doing;
            rig.className = "chip chip-" + doing.split(" ")[0];
        }
        var outputs = root.querySelector('[data-role="operating-outputs"]');
        if (outputs) {
            var named = operating.outputs || [];
            outputs.textContent = named.length ? named.join(" · ") : "";
        }

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
            .then(function (state) {
                if (!state) return;
                paintState(state);
                root.dispatchEvent(new CustomEvent("controlunit:state", {detail: state}));
            })
            .catch(function () { /* keep what is on the page */ });
    }

    // -- charts --------------------------------------------------------------

    var plasma = document.getElementById("chart-plasma");
    var gauges = document.getElementById("chart-ig");
    var baratrons = document.getElementById("chart-bar");

    // Move existing controls, preserving their handlers and channel choices.
    function applyPressureGrouping() {
        if (!gauges || !baratrons) return;
        var vessel = view.pressureGroup === "vessel";
        var upper = gauges.parentNode, lower = baratrons.parentNode;
        var groups = vessel ? [["Pu", "Bu"], ["Pd", "Bd"]] : [["Pu", "Pd"], ["Bu", "Bd"]];
        var titles = vessel ? ["Upstream · Pu + Bu", "Downstream · Pd + Bd"] : ["Ion gauges", "Baratrons"];
        [gauges, baratrons].forEach(function (canvas, i) {
            var section = canvas.parentNode;
            var legend = section.querySelector('.pen-legend');
            var scale = legend.querySelector('.chart-scale');
            groups[i].forEach(function (name) {
                legend.insertBefore(root.querySelector('[data-channel="' + name + '"]'), scale);
            });
            canvas.dataset.channels = groups[i].join(',');
            var heading = section.querySelector('h2');
            if (!heading.dataset.unitSuffix) heading.dataset.unitSuffix = heading.textContent.slice(heading.textContent.lastIndexOf(','));
            var title = titles[i] + heading.dataset.unitSuffix;
            heading.textContent = title;
            section.setAttribute('aria-label', title);
            legend.setAttribute('aria-label', 'Curves in ' + title);
            scale.setAttribute('aria-label', titles[i] + ' axis');
        });
        ['Bu', 'Bd'].forEach(function (name) {
            var button = root.querySelector('[data-zero="' + name + '"]');
            if (button) (vessel && name === 'Bu' ? upper : lower).querySelector('.chart-zero').appendChild(button);
        });
        press('[data-pressure-group]', 'pressureGroup', view.pressureGroup);
        reflectPressureAxes();
    }
    function reflectPressureAxes() {
        press('[data-scale-ig]', 'scaleIg', (view.pressureGroup === 'vessel' ? view.upstreamLog : view.igLog) ? 'log' : 'lin');
        press('[data-scale-bar]', 'scaleBar', (view.pressureGroup === 'vessel' ? view.downstreamLog : view.barLog) ? 'log' : 'lin');
    }

    function channelsOf(canvas) {
        return String((canvas && canvas.dataset.channels) || "").split(",");
    }

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

    /* The most a backing buffer may measure on either side. A browser
       refuses a canvas past a few thousand pixels and hands back a context
       that draws nothing, which a reader sees as a white panel. */
    var MAX_BUFFER = 8192;

    /* How tall a panel stands on the page, in CSS pixels.
     *
     * It is read from `data-height`, which nothing ever writes, and never
     * from the `height` attribute, which *is* the backing buffer: setting
     * `canvas.height` writes that attribute too. The old code read that
     * attribute back as if it were the layout height and multiplied it by
     * the device pixel ratio again on every redraw, so on a Retina Mac
     * (ratio 2) every panel doubled every draw. Measured on the owner's Mac
     * 2026-09-07: the plasma panel's height attribute at 1,802,240 px, the
     * document at 2,540,001 px, doubling once more when he chose the 20 s
     * window, then a white failed plot (PIHTI Log's audit, letter
     * 20260907-023785d0). At ratio 1 the same code was stable, which is why
     * the rig's own screen and every browser on this Windows box were fine.
     */
    var monitorPlotHeight = null;
    function logicalHeight(canvas) {
        if (mode === "monitor" && monitorPlotHeight !== null) return monitorPlotHeight;
        var declared = Number(canvas.dataset.height);
        return (isFinite(declared) && declared > 0) ? declared : 220;
    }

    /* The drawing context and the panel's size in CSS pixels, or null when
       this browser would give no context at all. Every input is layout or
       the device; nothing here reads back a value this function wrote. */
    function prepare(canvas) {
        var ratio = window.devicePixelRatio || 1;
        if (!isFinite(ratio) || ratio <= 0) ratio = 1;
        var width = canvas.clientWidth || canvas.parentNode.clientWidth || 600;
        if (!(width > 0)) width = 600;
        var height = logicalHeight(canvas);
        /* One scale for both sides, so a very wide window that would push
           the buffer past what is allowed shrinks it evenly rather than
           drawing the panel out of shape. */
        var scale = Math.min(ratio, MAX_BUFFER / width, MAX_BUFFER / height);
        if (!(scale > 0)) scale = 1;
        var wanted = {w: Math.max(1, Math.round(width * scale)),
                      h: Math.max(1, Math.round(height * scale))};
        canvas.style.height = height + "px";
        if (canvas.width !== wanted.w || canvas.height !== wanted.h) {
            canvas.width = wanted.w;
            canvas.height = wanted.h;
        }
        var ctx = canvas.getContext("2d");
        if (!ctx) return null;
        ctx.setTransform(scale, 0, 0, scale, 0, 0);
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

    /* The newest and the oldest stamp this browser holds, across every
       channel: the span `Full` means, and what a window is cut back from. */
    function bounds() {
        var first = null, last = null;
        Object.keys(store).forEach(function (name) {
            var kept = store[name];
            if (!kept || !kept.length) return;
            if (first === null || kept[0][0] < first) first = kept[0][0];
            if (last === null || kept[kept.length - 1][0] > last) last = kept[kept.length - 1][0];
        });
        return {first: first, last: last};
    }

    /* The samples of one channel inside [from, to], smoothed if asked. The
       slice is taken first, so the median costs what is on screen. */
    function slice(name, from, to) {
        var kept = store[name] || [];
        var out = [];
        for (var i = 0; i < kept.length; i++) {
            var t = kept[i][0];
            if (t < from) continue;
            if (t > to) break;
            out.push(kept[i]);
        }
        return median(out, view.smooth);
    }

    /* Draw one panel: the canvas's own channels, in their pens, `logScale`
       for the y axis. Each panel scales to the channels it draws and to
       nothing else, which is the whole reason there are three of them. */
    function draw(canvas, logScale) {
        var box = prepare(canvas);
        // No context, no panel. The page keeps working; the chart is blank
        // rather than the whole poll falling over on a thrown error.
        if (!box) return;
        var ctx = box.ctx;
        var st = styles();
        var pad = {left: 64, right: 14, top: 10, bottom: 26};
        var plotW = box.width - pad.left - pad.right;
        var plotH = box.height - pad.top - pad.bottom;

        ctx.clearRect(0, 0, box.width, box.height);

        var held = bounds();
        var to = held.last, from = held.first;
        if (to === null) {
            to = Date.now() / 1000;
            from = to - (view.window || 300);
        }
        if (view.window > 0) from = Math.max(from, to - view.window);
        if (!(to > from)) to = from + 1;

        /* Gather every curve this panel could draw, then decide which of
           them the axis is for. A curve that is switched off, empty in this
           window, or flat is left out of the range as well as off the
           panel: the whole point of leaving it out is that the axis then
           belongs to the curves that are actually moving. */
        var series = [];
        var count = 0;
        channelsOf(canvas).forEach(function (name) {
            if (!name) return;
            var chosen = view.channels[name] !== false;
            var points = chosen ? slice(name, from, to) : [];
            if (points.length > count) count = points.length;
            var kept = [];
            var nonpositive = 0, gap = true;
            var lo = Infinity, hi = -Infinity;
            points.forEach(function (p) {
                var v = p[1];
                if (v === null || v === undefined || !isFinite(v)) { gap = true; return; }
                if (logScale) {
                    if (!(v > 0)) { nonpositive += 1; gap = true; return; }
                    v = Math.log10(v);
                }
                kept.push([p[0], v, gap]);
                gap = false;
                if (v < lo) lo = v;
                if (v > hi) hi = v;
            });
            series.push({name: name, chosen: chosen, points: kept, lo: lo, hi: hi, nonpositive: nonpositive});
        });

        /* Flat is decided against a curve's own size, not against a number
           picked here: a change of less than 2% of the value on a linear
           axis, or less than a twentieth of a decade on a log one. Both are
           far below anything a person would call a trend and far above the
           last digit of an ADC.

           Collapsing only ever happens while another curve on the same
           panel is still moving, so a panel never empties itself, and a
           reader can restore a flat curve explicitly with its own pill. */
        var moving = series.filter(function (s) {
            return s.chosen && s.points.length && !isFlat(s, logScale);
        });
        series.forEach(function (s) {
            s.state = !s.chosen ? "off"
                : !s.points.length ? (s.nonpositive ? "nonpositive" : "absent")
                : (moving.length && !view.pinned[s.name] && isFlat(s, logScale)) ? "flat"
                : "drawn";
        });

        var lines = series.filter(function (s) { return s.state === "drawn"; });
        var lo = Infinity, hi = -Infinity;
        lines.forEach(function (s) {
            if (s.lo < lo) lo = s.lo;
            if (s.hi > hi) hi = s.hi;
        });

        if (logScale && !lines.length && series.some(function (s) { return s.nonpositive; })) {
            ctx.fillStyle = st.axis;
            ctx.textAlign = "center";
            ctx.fillText("No positive values for log scale — use lin", box.width / 2, box.height / 2);
            return {from: from, to: to, count: count, series: series};
        }
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
        var yStep = yTicks.length > 1 ? yTicks[1] - yTicks[0] : 0;
        ctx.textAlign = "right";
        ctx.textBaseline = "middle";
        yTicks.forEach(function (v) {
            var yy = Math.round(y(v)) + 0.5;
            ctx.beginPath(); ctx.moveTo(pad.left, yy); ctx.lineTo(pad.left + plotW, yy); ctx.stroke();
            var label = logScale ? "10" + superText(Math.round(v)) : fmtTick(v, yStep);
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
                if (i === 0 || p[2]) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
            });
            ctx.stroke();
            var last = line.points[line.points.length - 1];
            ctx.beginPath();
            ctx.arc(x(last[0]), y(last[1]), 3, 0, Math.PI * 2);
            ctx.fill();
        });

        return {from: from, to: to, count: count, series: series};
    }

    /* A curve whose whole excursion over the drawn window is smaller than
       its own last digit of interest. On a log axis the points are already
       decades, so the bound is a span; on a linear one it is a fraction of
       the value itself, because 2% means nothing without a magnitude.

       Three points, not two: a pair that happens to be equal is not
       evidence of anything, and a curve that has only just started drawing
       must not be called flat before it has had room to move. */
    var FLAT_DECADES = 0.05;
    var FLAT_FRACTION = 0.02;

    function isFlat(s, logScale) {
        if (s.points.length < 3) return false;
        var span = s.hi - s.lo;
        if (!isFinite(span)) return false;
        if (logScale) return span < FLAT_DECADES;
        var size = Math.max(Math.abs(s.hi), Math.abs(s.lo));
        if (!(size > 0)) return true;
        return span / size < FLAT_FRACTION;
    }

    /* Why a curve is not on its panel, beside its own name. `drawn` says
       nothing: a curve that is there needs no caption. The value is not
       repeated here — it is in that channel's readout card above, which is
       where every number on this page is read. */
    var LEGEND_ASIDE = {off: "off", absent: "no data", nonpositive: "≤0 on log", flat: "flat", drawn: ""};

    function paintLegend(canvas, drawn) {
        if (!canvas || !drawn) return;
        var legend = canvas.parentNode.querySelector(".pen-legend");
        if (!legend) return;
        drawn.series.forEach(function (s) {
            var button = legend.querySelector('[data-channel="' + s.name + '"]');
            if (!button) return;
            button.setAttribute("aria-pressed", s.chosen ? "true" : "false");
            button.dataset.curveState = s.state;
            button.title = s.state === "flat" ? "Show this curve even when flat" : "Show or hide this curve";
            var aside = button.querySelector('[data-role="pen-aside"]');
            if (aside) aside.textContent = s.state === "drawn" && s.nonpositive ? "≤0 omitted" : (LEGEND_ASIDE[s.state] || "");
        });
    }

    /* Whether any of a panel's own curves is switched on. A panel with none
       has nothing to draw and gives up its drawing area, which is what a
       preset that hides a chart actually does. */
    function anyChosen(canvas) {
        return channelsOf(canvas).some(function (name) {
            return name && view.channels[name] !== false;
        });
    }

    /* A collapsed panel's legend still says, per curve, that it is off: the
       switches stay exactly where the reader left them, so the panel comes
       back with the same press that sent it away. */
    function collapsedLegend(canvas) {
        var legend = canvas.parentNode.querySelector(".pen-legend");
        if (!legend) return;
        legend.querySelectorAll("[data-channel]").forEach(function (button) {
            button.setAttribute("aria-pressed", "false");
            button.dataset.curveState = "off";
            var aside = button.querySelector('[data-role="pen-aside"]');
            if (aside) aside.textContent = LEGEND_ASIDE.off;
        });
    }

    function drawAll() {
        monitorPlotHeight = null;
        if (mode === "monitor" && root.querySelector('.page-main')) {
            var main = root.querySelector('.page-main');
            var occupied = 0, active = 0;
            Array.prototype.forEach.call(main.children, function (child) {
                var style = getComputedStyle(child);
                if (style.display === "none" || style.position === "fixed" || style.position === "absolute") return;
                var margins = (parseFloat(style.marginTop) || 0) + (parseFloat(style.marginBottom) || 0);
                if (child.classList.contains('chart')) {
                    var canvas = child.querySelector('canvas');
                    if (canvas && anyChosen(canvas)) active += 1;
                    occupied += (parseFloat(style.paddingTop) || 0) + (parseFloat(style.paddingBottom) || 0) + 2 + margins;
                    Array.prototype.forEach.call(child.children, function (part) {
                        if (part.tagName === 'CANVAS') return;
                        var ps = getComputedStyle(part);
                        if (ps.display !== 'none') occupied += part.getBoundingClientRect().height + (parseFloat(ps.marginTop) || 0) + (parseFloat(ps.marginBottom) || 0);
                    });
                } else occupied += child.getBoundingClientRect().height + margins;
            });
            if (active) monitorPlotHeight = Math.max(140, Math.floor((window.innerHeight - parseFloat(getComputedStyle(document.querySelector(".container")).paddingTop) - 20 - occupied) / active));
        }
        [[plasma, "span-plasma", false],
         [gauges, "span-ig", view.pressureGroup === "vessel" ? view.upstreamLog : view.igLog],
         [baratrons, "span-bar", view.pressureGroup === "vessel" ? view.downstreamLog : view.barLog]].forEach(function (panel) {
            var canvas = panel[0];
            if (!canvas) return;
            var section = canvas.parentNode;
            var shown = anyChosen(canvas);
            if (section) section.classList.toggle("chart--collapsed", !shown);
            if (!shown) {
                collapsedLegend(canvas);
                span(panel[1], null);
                return;
            }
            var drawn = draw(canvas, panel[2]);
            span(panel[1], drawn);
            paintLegend(canvas, drawn);
        });
        reflectPreset();
    }

    function span(role, drawn) {
        var el = root.querySelector('[data-role="' + role + '"]');
        if (el) el.textContent = spanLabel(drawn);
    }

    function spanLabel(drawn) {
        var tail = fast ? " · fast" : "";
        if (view.smooth) tail = " · median " + view.smooth + tail;
        if (!drawn) return "Click a pill to show a curve";
        if (!drawn.count) return "no samples yet" + tail;
        var seconds = Math.max(0, Math.round(drawn.to - drawn.from));
        return "last " + fmtSeconds(seconds) + " · " + drawn.count + " samples" + tail;
    }

    // -- presets -------------------------------------------------------------

    /* A preset is a named set of the per-curve switches and nothing else: it
       changes what this browser draws, never what the rig records, and it is
       remembered exactly the way the switches themselves already are —
       there is no second stored value to drift from them.

       So which preset is pressed is *derived* from the switches rather than
       kept beside them: turn one curve off by hand and the page simply
       stops claiming to be showing a preset, which is the honest answer. */
    function presetChannels(button) {
        return String((button && button.dataset.channels) || "").split(",");
    }

    function matchesPreset(button) {
        var wanted = presetChannels(button);
        return Object.keys(view.channels).every(function (name) {
            return view.channels[name] === (wanted.indexOf(name) >= 0);
        });
    }

    function reflectPreset() {
        root.querySelectorAll("[data-preset]").forEach(function (button) {
            button.setAttribute("aria-pressed", matchesPreset(button) ? "true" : "false");
        });
    }

    function applyPreset(button) {
        var wanted = presetChannels(button);
        Object.keys(view.channels).forEach(function (name) {
            view.channels[name] = wanted.indexOf(name) >= 0;
        });
        view.pinned = {};
        remember();
        reflectChannels();
        drawAll();
    }

    function reflectChannels() {
        Object.keys(view.channels).forEach(function (name) {
            root.querySelectorAll('[data-channel="' + name + '"]').forEach(function (button) {
                button.setAttribute("aria-pressed", view.channels[name] ? "true" : "false");
            });
        });
    }

    // -- modes and the rails as drawers --------------------------------------

    /* The page's shape is in the address, so a laptop propped up beside the
       rig can be bookmarked in the shape it is wanted in. The server renders
       it on the first paint; a press moves the address with `pushState`, so
       Back, Forward and a reload all land on the mode a reader expects and
       the charts keep the history this browser has gathered. */
    function cleanMode(asked) {
        if (asked === "normal") return "observe";
        return asked === "monitor" || asked === "observe" ? asked : "operate";
    }
    var mode = cleanMode(document.body.dataset.mode);

    function modeInAddress() {
        var asked = new URLSearchParams(window.location.search).get("mode");
        return cleanMode(asked);
    }

    function applyMode() {
        document.body.dataset.mode = mode;
        press("[data-mode]", "mode", mode);
        var actions = root.querySelector('[data-role="mode-actions"]');
        if (actions) actions.hidden = mode !== "monitor";
        closeDrawers();
        root.querySelectorAll('[data-monitor-setting]').forEach(function (card) {
            if (!card.originalParent) {
                card.originalParent = card.parentNode;
                card.originalSlot = document.createComment("monitor setting");
                card.parentNode.insertBefore(card.originalSlot, card);
            }
            var dock = root.querySelector('[data-role="monitor-settings"]');
            if (mode === "monitor" && dock) dock.appendChild(card);
            else card.originalParent.insertBefore(card, card.originalSlot.nextSibling);
        });
        applyDisplay();
        drawAll();   // the reading column just changed width
    }

    function setMode(next) {
        next = cleanMode(next);
        if (next === mode) return;
        mode = next;
        var url = new URL(window.location.href);
        url.pathname = "/";
        if (next === "operate") url.searchParams.delete("mode");
        else url.searchParams.set("mode", next);
        window.history.pushState({mode: next}, "", url.toString());
        applyMode();
    }

    function closeDrawers() {
        root.querySelectorAll(".rail.drawer-open").forEach(function (rail) {
            rail.classList.remove("drawer-open");
        });
        root.querySelectorAll("[data-drawer]").forEach(function (button) {
            button.setAttribute("aria-expanded", "false");
        });
        var backdrop = document.querySelector(".drawer-backdrop");
        if (backdrop) backdrop.hidden = true;
    }

    function openDrawer(id) {
        if (mode !== "monitor") return;   // the rails are on the page already
        closeDrawers();
        var rail = document.getElementById(id);
        var backdrop = document.querySelector(".drawer-backdrop");
        if (!rail || !backdrop) return;
        rail.classList.add("drawer-open");
        var button = root.querySelector('[data-drawer="' + id + '"]');
        if (button) button.setAttribute("aria-expanded", "true");
        backdrop.hidden = false;
        rail.setAttribute("tabindex", "-1");
        rail.focus({preventScroll: true});
    }

    /* The browser's own full screen, for the second laptop. It costs one
       call and one event; a browser that refuses is left exactly as it was
       rather than told anything, because nothing about the page depends on
       it. */
    function toggleFullscreen() {
        var page = document.documentElement;
        if (document.fullscreenElement) {
            if (document.exitFullscreen) document.exitFullscreen();
            return;
        }
        if (page.requestFullscreen) {
            var asked = page.requestFullscreen();
            if (asked && asked.catch) asked.catch(function () { /* refused */ });
        }
    }

    function reflectFullscreen() {
        var button = root.querySelector('[data-role="fullscreen"]');
        if (!button) return;
        var on = !!document.fullscreenElement;
        button.setAttribute("aria-pressed", on ? "true" : "false");
        button.textContent = on ? "Leave full screen" : "Full screen";
    }

    function setupModes() {
        root.querySelectorAll("[data-preset]").forEach(function (button) {
            button.addEventListener("click", function () { applyPreset(button); });
        });
        root.querySelectorAll("[data-mode]").forEach(function (button) {
            button.addEventListener("click", function () { setMode(button.dataset.mode); });
        });
        root.querySelectorAll('[data-role="leave-mode"]').forEach(function (button) {
            button.addEventListener("click", function () { setMode("observe"); });
        });
        root.querySelectorAll("[data-drawer]").forEach(function (button) {
            button.addEventListener("click", function () {
                var rail = document.getElementById(button.dataset.drawer);
                if (rail && rail.classList.contains("drawer-open")) closeDrawers();
                else openDrawer(button.dataset.drawer);
            });
        });
        root.querySelectorAll(".drawer-close").forEach(function (button) {
            button.addEventListener("click", closeDrawers);
        });
        var backdrop = document.querySelector(".drawer-backdrop");
        if (backdrop) backdrop.addEventListener("click", closeDrawers);
        var full = root.querySelector('[data-role="fullscreen"]');
        if (full) full.addEventListener("click", toggleFullscreen);
        document.addEventListener("fullscreenchange", reflectFullscreen);

        /* Escape always gets the reader out of wherever they are: out of an
           open drawer first, and out of the mode itself when none is open,
           so a mode is never a room without a door. */
        document.addEventListener("keydown", function (event) {
            if (event.key !== "Escape") return;
            if (root.querySelector(".rail.drawer-open")) { closeDrawers(); return; }
            if (mode === "monitor") setMode("observe");
        });

        window.addEventListener("popstate", function () {
            mode = modeInAddress();
            applyMode();
        });
    }

    // -- rail controls -------------------------------------------------------

    function press(group, attribute, value) {
        root.querySelectorAll(group).forEach(function (button) {
            button.setAttribute("aria-pressed", String(button.dataset[attribute]) === String(value) ? "true" : "false");
        });
    }

    function setupRails() {
        /* The window cuts what this browser already holds. Nothing is asked
           of the rig: the samples are here, and Full is all of them. */
        root.querySelectorAll("[data-window]").forEach(function (button) {
            button.addEventListener("click", function () {
                view.window = Number(button.dataset.window);
                press("[data-window]", "window", view.window);
                remember();
                drawAll();
            });
        });
        root.querySelectorAll("[data-channel]").forEach(function (button) {
            button.addEventListener("click", function () {
                var name = button.dataset.channel;
                // A deliberate restoration wins over automatic suppression.
                // Presets return every channel to its normal automatic policy.
                if (button.dataset.curveState === "flat") {
                    view.channels[name] = true;
                    view.pinned[name] = true;
                } else {
                    view.channels[name] = !view.channels[name];
                    view.pinned[name] = view.channels[name];
                }
                button.setAttribute("aria-pressed", view.channels[name] ? "true" : "false");
                remember();
                drawAll();
            });
        });
        root.querySelectorAll('[data-pressure-group]').forEach(function (button) {
            button.addEventListener('click', function () {
                view.pressureGroup = button.dataset.pressureGroup;
                applyPressureGrouping();
                remember();
                drawAll();
            });
        });
        root.querySelectorAll("[data-scale-ig]").forEach(function (button) {
            button.addEventListener("click", function () {
                view[view.pressureGroup === "vessel" ? "upstreamLog" : "igLog"] = button.dataset.scaleIg === "log";
                reflectPressureAxes();
                remember();
                drawAll();
            });
        });
        root.querySelectorAll("[data-scale-bar]").forEach(function (button) {
            button.addEventListener("click", function () {
                view[view.pressureGroup === "vessel" ? "downstreamLog" : "barLog"] = button.dataset.scaleBar === "log";
                reflectPressureAxes();
                remember();
                drawAll();
            });
        });
        root.querySelectorAll("[data-smooth]").forEach(function (button) {
            button.addEventListener("click", function () {
                view.smooth = Number(button.dataset.smooth);
                press("[data-smooth]", "smooth", view.smooth);
                remember();
                drawAll();
                pollState();   // the readouts follow the lines
            });
        });
        root.querySelectorAll("[data-display]").forEach(function (button) {
            button.addEventListener("click", function () {
                if (mode === "monitor") view.monitorBig = button.dataset.display === "big";
                else view.big = button.dataset.display === "big";
                applyDisplay();
                remember();
                drawAll();
            });
        });
        root.querySelectorAll("[data-poll]").forEach(function (button) {
            button.addEventListener("click", function () {
                fast = button.dataset.poll === "fast";
                applyPoll();
                pollState();
                pollSeries();
                drawAll();   // the span labels say which rate is running
            });
        });
    }

    /* Big is one class on the page: the charts keep their width, so there is
       nothing to redraw, and only the readout row's own height changes. */
    function applyDisplay() {
        var big = mode === "monitor" ? view.monitorBig : view.big;
        root.classList.toggle("live--big", big);
        press("[data-display]", "display", big ? "big" : "normal");
    }

    var stateTimer = null;
    var seriesTimer = null;

    function applyPoll() {
        press("[data-poll]", "poll", fast ? "fast" : "normal");
        if (stateTimer) window.clearInterval(stateTimer);
        if (seriesTimer) window.clearInterval(seriesTimer);
        // The readouts come from /api/state, so both have to speed up for a
        // number under the desk to keep pace with the chart beside it. The
        // series keeps whatever window the reader chose; fast is a rate, not
        // a view.
        stateTimer = window.setInterval(pollState, fast ? FAST_MS : STATE_MS);
        seriesTimer = window.setInterval(pollSeries, fast ? FAST_MS : SERIES_MS);
    }

    function reflectView() {
        press("[data-window]", "window", view.window);
        reflectChannels();
        reflectPreset();
        press("[data-scale-ig]", "scaleIg", view.igLog ? "log" : "lin");
        press("[data-scale-bar]", "scaleBar", view.barLog ? "log" : "lin");
        press("[data-smooth]", "smooth", view.smooth);
        applyDisplay();
    }

    function setup() {
        recall();
        reflectView();
        applyPressureGrouping();
        setupRails();
        setupModes();
        applyMode();
        reflectFullscreen();
        root.addEventListener("controlunit:refresh", pollState);
        drawAll();
        pollState();
        fillFromRing();
        applyPoll();
        var pending = null;
        window.addEventListener("resize", function () {
            if (pending) window.clearTimeout(pending);
            pending = window.setTimeout(drawAll, 80);
        });
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup);
    else setup();
}());
