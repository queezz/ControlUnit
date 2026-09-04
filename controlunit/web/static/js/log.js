/* The Log tab: the rig's message log, polled every two seconds, with a
 * local Find and an order switch.
 *
 * New lines are inserted at the end the order calls for; nothing that is
 * already on the page is moved or re-rendered when a line arrives.
 */
(function () {
    "use strict";

    var LOG_MS = 2000;
    var STORE_KEY = "controlunit.log";

    var root = document.getElementById("log");
    if (!root) return;

    var list = document.getElementById("log-lines");
    var empty = document.getElementById("log-empty");
    var find = document.getElementById("log-find");
    var count = document.getElementById("log-find-count");

    var last = Number(root.dataset.last || 0);
    var order = "newest";

    try { order = localStorage.getItem(STORE_KEY) === "oldest" ? "oldest" : "newest"; } catch (e) { /* fine */ }

    function lineElement(line) {
        var item = document.createElement("li");
        item.className = "log-line";
        item.dataset.seq = String(line.seq);
        var time = document.createElement("span");
        time.className = "log-time mono";
        time.textContent = line.time || "";
        var text = document.createElement("span");
        text.className = "log-text";
        text.textContent = line.text || "";
        item.appendChild(time);
        item.appendChild(text);
        return item;
    }

    function applyOrder() {
        list.classList.toggle("log-lines--oldest", order === "oldest");
        root.querySelectorAll("[data-order]").forEach(function (button) {
            button.setAttribute("aria-pressed", button.dataset.order === order ? "true" : "false");
        });
    }

    function applyFind() {
        var needle = (find.value || "").trim().toLowerCase();
        var shown = 0, total = 0;
        list.querySelectorAll(".log-line").forEach(function (item) {
            total += 1;
            var hit = !needle || item.textContent.toLowerCase().indexOf(needle) !== -1;
            item.hidden = !hit;
            if (hit) shown += 1;
        });
        count.textContent = needle ? shown + " of " + total + " lines" : "";
        empty.hidden = total > 0;
    }

    function poll() {
        fetch("/api/log?since=" + encodeURIComponent(last), {headers: {Accept: "application/json"}})
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (body) {
                if (!body || !Array.isArray(body.lines)) return;
                body.lines.forEach(function (line) {
                    if (line.seq <= last) return;
                    // The list is rendered newest first in the DOM; the
                    // oldest-first order is a CSS reversal of the same list.
                    list.insertBefore(lineElement(line), list.firstChild);
                    last = line.seq;
                });
                var held = root.querySelector('[data-fact="held"]');
                if (held && body.held !== undefined) held.textContent = String(body.held);
                if (body.lines.length) applyFind();
            })
            .catch(function () { /* keep what is on the page */ });
    }

    function setup() {
        applyOrder();
        applyFind();
        root.querySelectorAll("[data-order]").forEach(function (button) {
            button.addEventListener("click", function () {
                order = button.dataset.order === "oldest" ? "oldest" : "newest";
                try { localStorage.setItem(STORE_KEY, order); } catch (e) { /* fine */ }
                applyOrder();
            });
        });
        find.addEventListener("input", applyFind);
        window.setInterval(poll, LOG_MS);
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup);
    else setup();
}());
