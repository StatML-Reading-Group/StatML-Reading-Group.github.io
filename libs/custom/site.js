/* StatML Reading Group -- all site behaviour, vanilla.
 *
 * The reference site loads jQuery 3.1.1 + skeleton-tabs.js and then immediately
 * .off('click')s skeleton-tabs' only handler. None of that is needed here:
 * nav docking is 6 lines of vanilla, smooth scrolling is a CSS property, and
 * the accordions are a class toggle. */

(function () {
  'use strict';

  /* ---------- Theme toggle (verbatim behaviour from the reference site) ---- */
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
    document.addEventListener('click', function (e) {
      var title = e.target.closest ? e.target.closest('.talk-title') : null;
      if (!title || title.classList.contains('is-static')) return;
      if (e.target.closest('a')) return;           // let real links through
      var talk = title.closest('.talk');
      if (!talk || !talk.querySelector('.talk-abstract')) return;
      talk.classList.toggle('open');
    });

    // Keyboard support: the row is interactive, so it must be focusable.
    var titles = document.querySelectorAll('.talk-title:not(.is-static)');
    for (var i = 0; i < titles.length; i++) {
      titles[i].setAttribute('tabindex', '0');
      titles[i].setAttribute('role', 'button');
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
      // Hide a semester heading once every talk under it is filtered out.
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

  function boot() {
    syncButtons(document.documentElement.getAttribute('data-theme'));
    initNavDock();
    initTalks();
    initArchiveSearch();
    initTermJump();
    initNavActive();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
