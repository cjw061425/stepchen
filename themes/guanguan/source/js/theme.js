/* =========================================================
   Dark mode toggle — self-contained, no dependencies.
   Loaded independently of app.js so that any error in other
   scripts can never break the theme switch.
   ========================================================= */
(function () {
  'use strict';

  var STORAGE_KEY = 'theme';
  var root = document.documentElement;

  function current() {
    return root.getAttribute('data-theme');
  }

  function apply(theme) {
    root.setAttribute('data-theme', theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {}
    syncIcon(theme);
  }

  function syncIcon(theme) {
    var toggle = document.querySelector('.theme-toggle');
    if (!toggle) return;
    var icon = toggle.querySelector('i');
    var isDark = theme === 'dark';
    if (icon) {
      icon.className = isDark ? 'fa fa-sun-o' : 'fa fa-moon-o';
    }
    var label = isDark ? '切换到浅色模式' : '切换到深色模式';
    toggle.setAttribute('aria-label', label);
    toggle.title = label;
  }

  // Apply the saved/preferred theme on load (head script already did this,
  // but re-sync the icon in case the icon markup rendered after head ran).
  syncIcon(current());

  var toggle = document.querySelector('.theme-toggle');
  if (!toggle) return;

  // Avoid binding twice if the script is somehow executed more than once.
  if (toggle.dataset.themeBound) return;
  toggle.dataset.themeBound = '1';

  toggle.addEventListener('click', function () {
    apply(current() === 'dark' ? 'light' : 'dark');
  });
})();
