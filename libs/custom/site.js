/* All site behaviour. Vanilla: nav docking is a scroll listener, smooth
 * scrolling is a CSS property, and the accordions are a class toggle. */

(function () {
  'use strict';

  /* ---------- Theme ---------- */
  var DARK_META = '#14161a', LIGHT_META = '#ffffff';

  function syncButtons(theme) {
    var btns = document.querySelectorAll('.theme-toggle');
    for (var i = 0; i < btns.length; i++) {
      btns[i].setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    var m = document.getElementById('meta-theme-color');
    if (m) m.setAttribute('content', theme === 'dark' ? DARK_META : LIGHT_META);
    syncButtons(theme);
    try { localStorage.setItem('theme', theme); } catch (e) {}
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('.theme-toggle') : null;
    if (!btn) return;
    var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    var root = document.documentElement;
    root.classList.add('theme-switching');
    var clear = function () { root.classList.remove('theme-switching'); };
    if (document.startViewTransition) {
      document.startViewTransition(function () { applyTheme(next); }).finished.then(clear, clear);
    } else {
      applyTheme(next);
      requestAnimationFrame(function () { requestAnimationFrame(clear); });
    }
  });

  /* ---------- Nav docking ------------------------------------------------- */
  function initNavDock() {
    var nav = document.querySelector('.navbar');
    if (!nav) return;
    var top = nav.getBoundingClientRect().top + window.pageYOffset;
    var body = document.body;
    function onScroll() {
      var docked = window.pageYOffset > top;
      body.classList.toggle('has-docked-nav', docked);
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', function () {
      body.classList.remove('has-docked-nav');
      top = nav.getBoundingClientRect().top + window.pageYOffset;
      onScroll();
    });
    onScroll();
  }

  /* ---------- Talk accordions --------------------------------------------- */
  function initTalks() {
    function setExpanded(talk, expanded) {
      talk.classList.toggle('open', expanded);
      var toggles = talk.querySelectorAll('.talk-title:not(.is-static)');
      for (var i = 0; i < toggles.length; i++) {
        toggles[i].setAttribute('aria-expanded', expanded ? 'true' : 'false');
      }
    }

    document.addEventListener('click', function (e) {
      var title = e.target.closest ? e.target.closest('.talk-title') : null;
      if (!title || title.classList.contains('is-static')) return;
      if (e.target.closest('a')) return;           // let links through
      // A drag that ends inside an element still fires click on it, so selecting
      // a title used to open its abstract -- on /archive/, where finding a talk
      // and copying its title is the whole reason the page exists. Three
      // characters rather than one: a sloppy click can catch a letter or two,
      // and that is a click, not a selection.
      var sel = window.getSelection ? window.getSelection() : null;
      if (sel && !sel.isCollapsed && String(sel).length > 2) return;
      var talk = title.closest('.talk');
      if (!talk || !talk.querySelector('.talk-abstract')) return;
      setExpanded(talk, !talk.classList.contains('open'));
    });

    // The title names the region it opens. There is one handle now, and
    // aria-controls is what states the relationship -- the only part of it the
    // markup never says on its own.
    var rows = document.querySelectorAll('.talk');
    for (var r = 0; r < rows.length; r++) {
      var panel = rows[r].querySelector('.talk-abstract');
      if (!panel) continue;
      if (!panel.id) panel.id = (rows[r].id || 'talk-' + r) + '-abstract';
      var handles = rows[r].querySelectorAll('.talk-title:not(.is-static)');
      for (var h = 0; h < handles.length; h++) {
        handles[h].setAttribute('aria-controls', panel.id);
      }
    }

    // The row is interactive, so it must be focusable.
    var titles = document.querySelectorAll('.talk-title:not(.is-static)');
    for (var i = 0; i < titles.length; i++) {
      titles[i].setAttribute('tabindex', '0');
      titles[i].setAttribute('role', 'button');
      titles[i].setAttribute('aria-expanded', 'false');
      titles[i].addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          this.click();
        }
      });
    }
  }

  /* ---------- Archive search ---------------------------------------------- */
  function initArchiveSearch() {
    var input = document.querySelector('.archive-search');
    if (!input) return;
    var counter = document.querySelector('.archive-count');
    var talks = Array.prototype.slice.call(document.querySelectorAll('.talk[data-search]'));
    var sections = Array.prototype.slice.call(document.querySelectorAll('.term-section'));
    var total = talks.length;

    function run() {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      talks.forEach(function (t) {
        var hit = !q || t.getAttribute('data-search').indexOf(q) !== -1;
        t.classList.toggle('is-hidden', !hit);
        if (hit) shown++;
      });
      // Hide a semester heading once all its talks are filtered out.
      sections.forEach(function (s) {
        var any = s.querySelector('.talk:not(.is-hidden)');
        s.classList.toggle('is-hidden', !any);
      });
      if (counter) {
        counter.textContent = q
          ? shown + ' of ' + total + ' talks'
          : total + ' talks';
      }
      var empty = document.querySelector('.archive-empty');
      if (empty) empty.classList.toggle('is-hidden', shown !== 0);
    }

    input.addEventListener('input', run);
    input.addEventListener('search', run);

    // Deep link: /archive/?q=conformal
    try {
      var q0 = new URLSearchParams(window.location.search).get('q');
      if (q0) { input.value = q0; }
    } catch (e) {}
    run();
  }

  /* ---------- Semester jump ----------------------------------------------- */
  function initTermJump() {
    var sel = document.querySelector('.term-jump');
    if (!sel) return;
    sel.addEventListener('change', function () {
      if (!this.value) return;
      var el = document.getElementById(this.value);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  /* ---------- Nav active state -------------------------------------------- */
  function initNavActive() {
    var path = window.location.pathname.replace(/index\.html$/, '');
    if (path.length > 1) path = path.replace(/\/$/, '');
    var links = document.querySelectorAll('.navbar-link, .navbar-mobile a');
    for (var i = 0; i < links.length; i++) {
      var href = links[i].getAttribute('href') || '';
      href = href.replace(/index\.html$/, '');
      if (href.length > 1) href = href.replace(/\/$/, '');
      if (href === path) links[i].classList.add('active');
    }
  }

  /* ---------- People sort ------------------------------------------------- */
  /* Alphabetical rosters quietly advantage early surnames, so random is the
   * default and it reshuffles on every visit. Nodes are physically reordered
   * rather than given a CSS `order`, which would leave the DOM -- and so the
   * reading and tab order -- disagreeing with what is on screen. */
  function initPeopleSort() {
    var wrap = document.querySelector('.sort-controls');
    if (!wrap) return;
    var groups = Array.prototype.slice.call(
      document.querySelectorAll('.people-grid, .people-list'));
    if (!groups.length) return;

    var buttons = Array.prototype.slice.call(wrap.querySelectorAll('.sort-option'));
    var items = groups.map(function (g) {
      return Array.prototype.slice.call(g.children);
    });

    function key(el) { return el.getAttribute('data-sort') || ''; }
    function full(el) { return el.getAttribute('data-name') || ''; }

    // localeCompare so Slepcev and Varici land where a reader expects.
    function byName(a, b) {
      var c = key(a).localeCompare(key(b), 'en', { sensitivity: 'base' });
      return c !== 0 ? c : full(a).localeCompare(full(b), 'en', { sensitivity: 'base' });
    }

    function shuffle(list) {
      for (var i = list.length - 1; i > 0; i--) {          // Fisher-Yates
        var j = Math.floor(Math.random() * (i + 1));
        var t = list[i]; list[i] = list[j]; list[j] = t;
      }
      return list;
    }

    function apply(mode) {
      groups.forEach(function (g, i) {
        var order = items[i].slice();
        if (mode === 'alpha') order.sort(byName);
        else if (mode === 'reverse') order.sort(byName).reverse();
        else shuffle(order);
        var frag = document.createDocumentFragment();
        order.forEach(function (el) { frag.appendChild(el); });
        g.appendChild(frag);
      });
      buttons.forEach(function (b) {
        var on = b.getAttribute('data-sort-mode') === mode;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    }

    wrap.addEventListener('click', function (e) {
      var btn = e.target.closest ? e.target.closest('.sort-option') : null;
      if (!btn) return;
      apply(btn.getAttribute('data-sort-mode'));   // re-clicking random reshuffles
    });

    // Deliberately not remembered. Alphabetical is a per-visit choice, so the
    // randomised order is what every visitor meets first -- which is the whole
    // point of randomising it.
    apply('random');
  }

  function boot() {
    syncButtons(document.documentElement.getAttribute('data-theme'));
    initNavDock();
    initTalks();
    initArchiveSearch();
    initTermJump();
    initNavActive();
    initPeopleSort();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
