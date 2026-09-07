/* The Lab tab: the three services of the ensemble, and one press that asks
 * the LAN again.
 *
 * The page is served before the LAN has answered, so a card may arrive
 * saying `checking`. This asks again straight away, then every two seconds
 * while any card is still checking, and settles to every thirty once every
 * state has resolved — the fast rate exists only for the few seconds a first
 * answer takes, not for the hours the tab may be left open. A hidden tab
 * asks nothing at all and asks once the moment it is looked at again: nobody
 * is reading it, and the rig's LAN is not asked on nobody's behalf.
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
    var button = document.querySelector('[data-role="refresh"]');
    var checkedLine = document.querySelector('[data-role="checked"]');

    function chipClass(state) {
        return "chip chip-" + String(state).replace(/\s+/g, "-");
    }

    function paint(service) {
        var card = document.querySelector('.service[data-alias="' + service.alias + '"]');
        if (!card) return;
        var chip = card.querySelector('[data-role="state"]');
        if (chip) {
            chip.textContent = service.state;
            chip.className = chipClass(service.state);
        }
        var version = card.querySelector('[data-role="version"]');
        if (version) version.textContent = service.version || "—";
        var detail = card.querySelector('[data-role="detail"]');
        if (detail) detail.textContent = service.detail || "—";
        var where = card.querySelector('[data-role="where"]');
        if (where) where.textContent = service.where || "—";
        var start = card.querySelector('[data-role="start"]');
        if (start) start.textContent = service.start || "—";

        /* An address this machine does not have is said in words, not by a
           link that goes nowhere. One of the two is always hidden, so the
           actions line keeps its height either way. */
        var open = card.querySelector('[data-role="open"]');
        if (open) {
            open.href = service.url || "";
            open.hidden = !service.url;
        }
        var missing = card.querySelector('[data-role="no-address"]');
        if (missing) missing.hidden = Boolean(service.url);
    }

    /* When this machine last heard back — not how old the rows are, which
       the chips say for themselves. Null means no answer has ever landed. */
    function setChecked(stamp) {
        if (!checkedLine) return;
        checkedLine.textContent = stamp ? "Checked " + stamp + "." : "Not checked yet.";
    }

    function again() {
        if (timer) window.clearTimeout(timer);
        timer = window.setTimeout(tick, waiting ? CHECKING_MS : REFRESH_MS);
    }

    function tick() {
        if (document.hidden) { again(); return; }
        load(false);
    }

    /* A failed refresh leaves the last answer standing rather than blanking
       the page: the reader is told nothing new, not told something false. */
    function load(fresh) {
        if (button) button.disabled = true;
        fetch(fresh ? "/api/neighbours?fresh=1" : "/api/neighbours",
              {headers: {Accept: "application/json"}})
            .then(function (response) { return response.ok ? response.json() : null; })
            .then(function (payload) {
                if (!payload || !Array.isArray(payload.services)) return;
                payload.services.forEach(paint);
                waiting = payload.services.some(function (service) {
                    return service.state === "checking";
                });
                setChecked(payload.checked_at);
            })
            .catch(function () { /* keep what is on the page */ })
            .then(function () {
                if (button) button.disabled = false;
                again();
            });
    }

    function setup() {
        waiting = document.querySelector('[data-role="state"].chip-checking') !== null;
        if (button) button.addEventListener("click", function () { load(true); });
        document.addEventListener("visibilitychange", function () {
            if (!document.hidden) load(false);
        });
        load(false);
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup);
    else setup();
}());
