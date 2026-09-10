/* One navigation for every viewport; the phone disclosure never sets the rig. */
(function () {
    "use strict";
    var button = document.querySelector('.nav-toggle');
    var tabs = document.querySelector('.main-tabs');
    if (!button || !tabs) return;
    function close() {
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-label', 'Open navigation');
    }
    button.addEventListener('click', function () {
        var open = button.getAttribute('aria-expanded') !== 'true';
        button.setAttribute('aria-expanded', String(open));
        button.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    });
    document.addEventListener('click', function (event) {
        if (!button.contains(event.target) && !tabs.contains(event.target)) close();
    });
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') {
            close();
            button.focus();
            event.stopImmediatePropagation();
        }
    });
    tabs.addEventListener('click', close);

    document.querySelectorAll('.frow[data-mfc] .gas-disclosure').forEach(function (fold) {
        var key = 'controlunit.gas-fold.' + fold.closest('[data-mfc]').dataset.mfc;
        try {
            var saved = localStorage.getItem(key);
            if (saved !== null) fold.open = saved !== 'closed';
        } catch (error) { /* Storage is optional. */ }
        fold.addEventListener('toggle', function () {
            try { localStorage.setItem(key, fold.open ? 'open' : 'closed'); }
            catch (error) { /* The disclosure still works without storage. */ }
        });
    });
}());
