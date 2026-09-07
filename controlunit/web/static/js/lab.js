/* The Lab tab: the three services of the ensemble, one press that asks the
 * LAN again, and the disclosures a reader opens.
 *
 * The page is served before the LAN has answered, so a card may arrive
 * saying `checking`. This asks again straight away, then every two seconds
 * while any card is still checking, and settles to every thirty once every
 * state has resolved — the fast rate exists only for the few seconds a first
 * answer takes, not for the hours the tab may be left open. A hidden tab
 * asks nothing at all and asks once the moment it is looked at again: nobody
 * is reading it, and the rig's LAN is not asked on nobody's behalf.
 *
 * **A refresh never closes what the reader opened.** Every Start command a
 * card shows, and whether the rail's More is open, is kept here and mirrored
 * to sessionStorage, and `paint()` re-applies it after every answer. Without
 * that, the two-second poll of a still-checking board would shut a
 * disclosure under the eyes of the person reading it.
 *
 * No framework, nothing fetched from the internet. Every update writes into
 * elements that already exist and already have their room reserved in CSS,
 * so a state changing under the reader never moves anything on the page.
 */
(function () {
    "use strict";

    var REFRESH_MS = 30000;
    var CHECKING_MS = 2000;

    /* Kept for this browser tab only. A disclosure is a reading position,
       not a setting: it should survive a reload of the page it was opened
       on and mean nothing tomorrow. */
    var OPEN_KEY = "controlunit.lab.start-open";
    var MORE_KEY = "controlunit.lab.ensemble-more";

    /* What a card says under Start when the neighbours file gave a command
       and no words for it. The same sentence the server renders. */
    var START_FALLBACK = "Started by a command on its own machine.";

    var timer = null;
    var waiting = false;
    var button = document.querySelector('[data-role="refresh"]');
    var checkedLine = document.querySelector('[data-role="checked"]');
    var moreButton = document.querySelector('[data-role="more"]');
    var morePanel = document.getElementById("ensemble-more");

    /* alias -> true for every Start command the reader has opened. */
    var opened = {};
    var moreOpen = false;

    function remember(key, value) {
        try {
            window.sessionStorage.setItem(key, value);
        } catch (error) { /* a browser that stores nothing still works */ }
    }

    function recalled(key) {
        try {
            return window.sessionStorage.getItem(key);
        } catch (error) {
            return null;
        }
    }

    function readOpened() {
        var raw = recalled(OPEN_KEY);
        if (!raw) return {};
        try {
            var parsed = JSON.parse(raw);
            return (parsed && typeof parsed === "object") ? parsed : {};
        } catch (error) {
            return {};
        }
    }

    function chipClass(state) {
        return "chip chip-" + String(state).replace(/\s+/g, "-");
    }

    /* The words lead; the command sits behind the toggle. A card with no
       command reserves nothing: no toggle, no line, the row ends at the
       words. */
    function applyStart(card, alias, command) {
        var toggle = card.querySelector('[data-role="start-toggle"]');
        var line = card.querySelector('[data-role="start"]');
        var open = Boolean(command) && opened[alias] === true;
        if (toggle) {
            toggle.hidden = !command;
            toggle.textContent = open ? "hide" : "show";
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        }
        if (line) line.hidden = !open;
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

        var command = service.start || "";
        var how = card.querySelector('[data-role="start-how"]');
        if (how) {
            how.textContent = service.start_how
                || (command ? START_FALLBACK : "—");
        }
        var line = card.querySelector('[data-role="start"]');
        if (line) line.textContent = command;
        applyStart(card, service.alias, command);

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

    function applyMore() {
        if (!moreButton || !morePanel) return;
        morePanel.hidden = !moreOpen;
        moreButton.textContent = moreOpen ? "Less" : "More";
        moreButton.setAttribute("aria-expanded", moreOpen ? "true" : "false");
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

    function setupStartToggles() {
        var toggles = document.querySelectorAll('[data-role="start-toggle"]');
        Array.prototype.forEach.call(toggles, function (toggle) {
            var card = toggle.closest(".service");
            if (!card) return;
            var alias = card.getAttribute("data-alias");
            toggle.addEventListener("click", function () {
                opened[alias] = !(opened[alias] === true);
                remember(OPEN_KEY, JSON.stringify(opened));
                var line = card.querySelector('[data-role="start"]');
                applyStart(card, alias, line ? line.textContent : "");
            });
            var line = card.querySelector('[data-role="start"]');
            applyStart(card, alias, line ? line.textContent : "");
        });
    }

    function setup() {
        opened = readOpened();
        moreOpen = recalled(MORE_KEY) === "1";
        setupStartToggles();
        applyMore();
        if (moreButton) {
            moreButton.addEventListener("click", function () {
                moreOpen = !moreOpen;
                remember(MORE_KEY, moreOpen ? "1" : "0");
                applyMore();
            });
        }
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
