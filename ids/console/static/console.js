/* IDS Operator Console — Client-side interactions
 * Minimal vanilla JS: sidebar toggle + timestamp formatting.
 * No framework dependencies. Dark mode only.
 */

(function () {
  'use strict';

  // ── Sidebar toggle (mobile) ──────────────────────────────────────────────

  function initSidebarToggle() {
    var toggle = document.getElementById('sidebar-toggle');
    var sidebar = document.getElementById('app-sidebar');

    if (!toggle || !sidebar) {
      return;
    }

    function openSidebar() {
      sidebar.classList.add('shell__sidebar--open');
      toggle.setAttribute('aria-expanded', 'true');
    }

    function closeSidebar() {
      sidebar.classList.remove('shell__sidebar--open');
      toggle.setAttribute('aria-expanded', 'false');
    }

    toggle.addEventListener('click', function () {
      var isOpen = sidebar.classList.contains('shell__sidebar--open');
      if (isOpen) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', function (event) {
      if (
        sidebar.classList.contains('shell__sidebar--open') &&
        !sidebar.contains(event.target) &&
        event.target !== toggle &&
        !toggle.contains(event.target)
      ) {
        closeSidebar();
      }
    });
  }

  // ── Timestamp formatter ──────────────────────────────────────────────────
  // Finds elements with data-client-stamp attribute (ISO 8601 UTC string)
  // and replaces their text content with a human-friendly local time string.

  function formatTimestamps() {
    var elements = document.querySelectorAll('[data-client-stamp]');
    if (!elements.length) {
      return;
    }

    var locale = navigator.language || 'en';
    var dateTimeFormat = new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });

    elements.forEach(function (el) {
      var raw = el.getAttribute('data-client-stamp');
      if (!raw) {
        return;
      }
      try {
        var date = new Date(raw);
        if (isNaN(date.getTime())) {
          return;
        }
        el.textContent = dateTimeFormat.format(date);
        el.setAttribute('title', date.toISOString());
      } catch (e) {
        // Leave original text intact on error
      }
    });
  }

  // ── Init ─────────────────────────────────────────────────────────────────

  function init() {
    initSidebarToggle();
    formatTimestamps();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
