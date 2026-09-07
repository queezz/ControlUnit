/* The Lab tab: one show/hide toggle per service, and a refresh that updates
 * the three states in place.
 *
 * The page is served before the LAN has answered, so a card may arrive
 * saying `checking`. This asks again straight away, then every two seconds
 * while any card is still checking, and settles to every thirty once every
 * state has resolved — the fast rate exists only for the few seconds a first
 * answer takes, not for the hours the tab may be left open.
 *
 * No framework, nothing fetched from the internet. Every update writes into
 * elements that already exist and already have their room reserved in CSS,
 * so a state changing under the reader never moves anything on the page.
 */
(function () {
    "use strict";

    var REFRESH_MS = 30000;
    var CHECKING_MS = 2000;

    var timer = null;
    var waiting = false;

    /* Meaning stays visible; only the line to type appears and disappears,
       beneath a toggle that never changes position. */
    function setupToggles() {
        document.querySelectorAll(".howto .toggle").forEach(function (button) {
            button.addEventListener("click", function () {
                var target = document.getElementById(button.dataset.shows);
                if (!target) return;
                var showing = target.hidden;
                target.hidden = !showing;
                button.setAttribute("aria-expanded", showing ? "true" : "false");
                button.textContent = showing ? "hide" : "show";
            });
        });
    }

    function chipClass(state) {
        return "chip chip-" + String(state).replace(/\s+/g, "-");
    }

    function paint(service) {
        var card = document.querySelector('.service[data-alias="' + service.alias + '"]');
        if (card) {
            var chip = card.querySelector('[data-role="state"]');
            if (chip) {
                chip.textContent = service.state;
                chip.className = chipClass(service.state);
            }
            var detail = card.querySelector('[data-role="detail"]');
            if (detail) detail.textContent = service.detail || "";
            var version = card.querySelector('[data-role="version"]');
            if (version) version.textContent = service.version || "—";
            var open = card.querySelector('[data-role="open"]');
            if (open) {
                open.href = service.url || "";
                if (service.url) open.removeAttribute("aria-disabled");
                else open.setAttribute("aria-disabled", "true");
            }
            var where = card.querySelector('[data-role="where"]');
            if (where) where.textContent = service.where ? "Runs " + service.where + "." : "";
            var start = card.querySelector('[data-role="start"]');
            if (start) start.textContent = service.start || "";
            var toggle = card.querySelector(".howto .toggle");
            if (toggle) toggle.hidden = !service.start;
            var howto = card.querySelector(".howto");
            if (howto) howto.hidden = !(service.where || service.start);
        }
        var address = document.querySelector('[data-address="' + service.alias + '"]');
        if (address) address.textContent = service.url || "not configured";
    }

    function again() {
        if (timer) window.clearTimeout(timer);
        timer = window.setTimeout(refresh, waiting ? CHECKING_MS : REFRESH_MS);
    }

    /* A failed refresh leaves the last answer standing rather than blanking
       the page: the reader is told nothing new, not told something false. */
    function refresh() {
        fetch("/api/neighbours", {headers: {Accept: "application/json"}})
            .then(function (response) { return response.ok ? response.json() : null; })
            .then(function (payload) {
                if (!payload || !Array.isArray(payload.services)) return;
                payload.services.forEach(paint);
                waiting = payload.services.some(function (service) {
                    return service.state === "checking";
                });
            })
            .catch(function () { /* keep what is on the page */ })
            .then(again);
    }

    function setup() {
        setupToggles();
        waiting = document.querySelector('[data-role="state"].chip-checking') !== null;
        refresh();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup);
    else setup();
}());
