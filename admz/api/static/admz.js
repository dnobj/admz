/* =========================================================================
   ADMZ "Axis Signal" shell behavior — theme, site switcher, console dock,
   diff accordions, keyboard shortcuts. Vanilla JS, progressive enhancement:
   every screen is server-rendered HTML; this just adds the interactive bits
   the design calls for.
   ========================================================================= */
(function () {
  "use strict";

  var root = document.documentElement;

  // ── Theme ──────────────────────────────────────────────────────────────
  // Persisted in localStorage. On switch, kill transitions for one frame so
  // every themed property snaps to its new token value instead of getting
  // stuck mid-transition (mirrors the prototype's toggleTheme technique).
  var THEME_KEY = "admz-theme";

  function applyTheme(mode) {
    root.setAttribute("data-theme", mode);
    document.querySelectorAll("[data-theme-icon]").forEach(function (el) {
      // dark → show "eye" (switch to light); light → show "power"
      el.setAttribute("data-lucide", mode === "dark" ? "sun" : "moon");
    });
    if (window.lucide) window.lucide.createIcons();
  }

  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem(THEME_KEY); } catch (e) {}
    applyTheme(saved === "light" ? "light" : "dark");
  }

  function toggleTheme() {
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.classList.add("admz-no-transition");
    applyTheme(next);
    try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { root.classList.remove("admz-no-transition"); });
    });
    // Notify the docked console iframe so it re-themes in lockstep.
    var dockFrame = document.querySelector(".console-dock iframe");
    if (dockFrame && dockFrame.contentWindow) {
      try { dockFrame.contentWindow.postMessage({ admzTheme: next }, "*"); } catch (e) {}
    }
  }

  // Allow the parent shell to push theme into an embedded console iframe.
  window.addEventListener("message", function (e) {
    if (e.data && e.data.admzTheme) {
      try { localStorage.setItem(THEME_KEY, e.data.admzTheme); } catch (err) {}
      root.classList.add("admz-no-transition");
      applyTheme(e.data.admzTheme);
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { root.classList.remove("admz-no-transition"); });
      });
    }
  });

  // ── Generic dropdowns (site switcher, etc.) ─────────────────────────────
  function closeAllDropdowns() {
    document.querySelectorAll(".dropdown-menu").forEach(function (m) { m.remove(); });
    document.querySelectorAll(".site-switcher-btn.open").forEach(function (b) { b.classList.remove("open"); });
    document.querySelectorAll(".scrim-click").forEach(function (s) { s.remove(); });
  }

  function initSiteSwitcher() {
    var btn = document.getElementById("site-switcher-btn");
    var tpl = document.getElementById("site-switcher-menu");
    if (!btn || !tpl) return;
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (btn.classList.contains("open")) { closeAllDropdowns(); return; }
      closeAllDropdowns();
      btn.classList.add("open");
      var scrim = document.createElement("div");
      scrim.className = "scrim-click";
      scrim.addEventListener("click", closeAllDropdowns);
      document.body.appendChild(scrim);
      var menu = tpl.content.cloneNode(true);
      btn.parentNode.appendChild(menu);
      if (window.lucide) window.lucide.createIcons();
    });
  }

  // ── Console dock ─────────────────────────────────────────────────────────
  // The dock is a right-hand panel embedding /chat?embed=1. State (open width)
  // persists in localStorage so it survives navigation across server-rendered
  // pages.
  var DOCK_KEY = "admz-console-dock";

  function dockState() {
    try { return localStorage.getItem(DOCK_KEY) || "closed"; } catch (e) { return "closed"; }
  }
  function setDockState(s) { try { localStorage.setItem(DOCK_KEY, s); } catch (e) {} }

  function applyDock() {
    var dock = document.getElementById("console-dock");
    var btn = document.getElementById("console-toggle");
    if (!dock) return;
    var open = dockState() === "open";
    dock.classList.toggle("open", open);
    if (open && !dock.querySelector("iframe")) {
      var iframe = document.createElement("iframe");
      iframe.src = "/chat?embed=1";
      iframe.title = "ADMZ Console";
      dock.appendChild(iframe);
    }
    if (btn) btn.classList.toggle("active", open);
  }

  function toggleDock() {
    setDockState(dockState() === "open" ? "closed" : "open");
    applyDock();
  }
  // Exposed so the embedded console's close button can collapse the dock.
  window.admzCloseDock = function () { setDockState("closed"); applyDock(); };

  // ── Diff accordions ─────────────────────────────────────────────────────
  function initAccordions() {
    document.querySelectorAll(".facet-head").forEach(function (head) {
      head.addEventListener("click", function () {
        var facet = head.closest(".facet");
        if (!facet) return;
        var open = facet.getAttribute("data-open") !== "false";
        facet.setAttribute("data-open", open ? "false" : "true");
        var chev = head.querySelector(".chev [data-lucide]");
        if (chev) { chev.setAttribute("data-lucide", open ? "chevron-right" : "chevron-down"); if (window.lucide) window.lucide.createIcons(); }
      });
    });
  }

  // ── Collapsible panels (branch panel, etc.) ──────────────────────────────
  function initCollapsibles() {
    document.querySelectorAll("[data-collapse-toggle]").forEach(function (head) {
      head.addEventListener("click", function () {
        var target = document.getElementById(head.getAttribute("data-collapse-toggle"));
        if (target) target.classList.toggle("hidden");
      });
    });
  }

  // ── Theme toggle button + ⌘K ──────────────────────────────────────────────
  function initShellControls() {
    var themeBtn = document.getElementById("theme-toggle");
    if (themeBtn) themeBtn.addEventListener("click", toggleTheme);

    var consoleBtn = document.getElementById("console-toggle");
    if (consoleBtn) consoleBtn.addEventListener("click", toggleDock);

    document.addEventListener("keydown", function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        window.location.href = "/chat";
      }
      if (e.key === "/" && document.activeElement === document.body) {
        var search = document.getElementById("topbar-search");
        if (search) { e.preventDefault(); search.focus(); }
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSiteSwitcher();
    applyDock();
    initAccordions();
    initCollapsibles();
    initShellControls();
    if (window.lucide) window.lucide.createIcons();
  });

  // Apply theme immediately (before DOMContentLoaded) to avoid a flash.
  initTheme();
})();
