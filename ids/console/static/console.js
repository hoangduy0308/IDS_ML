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

  // ── Live Logs Poller ─────────────────────────────────────────────────────
  // Reads data-live-logs-poll from #live-logs-feed and starts a setInterval
  // that fetches /api/v1/alerts and /api/v1/anomalies, then re-renders rows.

  function initLiveLogsPoller() {
    var container = document.getElementById('live-logs-feed');
    if (!container) {
      return;
    }
    var interval = parseInt(container.getAttribute('data-live-logs-poll'), 10) || 7000;

    function renderRows(alerts, anomalies) {
      var rows = [];

      // Build alert rows
      (alerts || []).forEach(function (alert) {
        var ts = (alert.event_ts || '').slice(0, 19).replace('T', ' ');
        var sev = alert.severity || 'unknown';
        var suppressed = alert.is_suppressed ? ' <span class="badge badge--muted">suppressed</span>' : '';
        rows.push(
          '<div class="live-log-row" style="display:flex;align-items:flex-start;padding:8px 20px;border-bottom:1px solid var(--border);gap:12px">' +
          '<span style="color:var(--muted-foreground);flex-shrink:0;min-width:140px">' + ts + '</span>' +
          '<span class="badge badge--warning" style="flex-shrink:0">' + sev + '</span>' +
          '<span class="badge badge--info" style="flex-shrink:0">alert</span>' +
          '<span style="color:var(--foreground);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
          (alert.source_event_id || '') + suppressed +
          '</span>' +
          '</div>'
        );
      });

      // Build anomaly rows
      (anomalies || []).forEach(function (anom) {
        var ts = (anom.event_ts || '').slice(0, 19).replace('T', ' ');
        rows.push(
          '<div class="live-log-row" style="display:flex;align-items:flex-start;padding:8px 20px;border-bottom:1px solid var(--border);gap:12px">' +
          '<span style="color:var(--muted-foreground);flex-shrink:0;min-width:140px">' + ts + '</span>' +
          '<span class="badge badge--muted" style="flex-shrink:0">info</span>' +
          '<span class="badge badge--warning" style="flex-shrink:0">anomaly</span>' +
          '<span style="color:var(--foreground);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
          (anom.source_event_id || '') +
          '</span>' +
          '</div>'
        );
      });

      if (rows.length === 0) {
        container.innerHTML =
          '<div style="padding:48px 20px;text-align:center;color:var(--muted-foreground)">' +
          '<div style="font-size:13px;margin-bottom:6px">No events yet</div>' +
          '</div>';
      } else {
        container.innerHTML = rows.join('');
      }
    }

    function poll() {
      var alertsDone = false;
      var anomsDone = false;
      var fetchedAlerts = [];
      var fetchedAnoms = [];

      function tryRender() {
        if (alertsDone && anomsDone) {
          renderRows(fetchedAlerts, fetchedAnoms);
        }
      }

      fetch('/api/v1/alerts?include_suppressed=true')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          fetchedAlerts = data.alerts || [];
          alertsDone = true;
          tryRender();
        })
        .catch(function () {
          alertsDone = true;
          tryRender();
        });

      fetch('/api/v1/anomalies')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          fetchedAnoms = data.anomalies || [];
          anomsDone = true;
          tryRender();
        })
        .catch(function () {
          anomsDone = true;
          tryRender();
        });
    }

    setInterval(poll, interval);
  }

  // ── Init ─────────────────────────────────────────────────────────────────

  function init() {
    initSidebarToggle();
    formatTimestamps();
    initLiveLogsPoller();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
