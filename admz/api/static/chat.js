// ADMZ Console streaming client ("Axis Signal" styling).
//
// Intercepts the chat form's submit, POSTs to /chat/stream, and reads
// the SSE response chunk-by-chunk. Renders the design's component kit:
//   - text         → assistant-turn text block
//   - tool_call    → .tool-card ("Calling <op>")
//   - tool_result  → updates the previous card status/result
//   - done         → token-usage footer
//   - error        → .result-row red
//   - /confirm/{t} → inline .approval-card (two-gate) + pinned action
//   - /capture/{t} → inline capture card + pinned action
//
// Falls back gracefully: with JS off, the form posts to /chat and the
// server renders the response inside _console.html.

(function () {
  "use strict";

  var lucide = window.lucide;
  function icons() { if (window.lucide) window.lucide.createIcons(); }
  function ico(name, cls) {
    return '<i data-lucide="' + name + '"' + (cls ? ' class="' + cls + '"' : "") + "></i>";
  }

  var form = document.getElementById("chat-form");
  var transcript = document.getElementById("chat-transcript");
  var sendBtn = document.getElementById("chat-send");
  var emptyState = document.getElementById("chat-empty");

  if (!form || !transcript || !sendBtn) return;

  // ── Composer settings popover (gear): model + voice dropdowns. ──────────
  (function () {
    var btn = document.getElementById("composer-settings-btn");
    var panel = document.getElementById("composer-settings");
    if (!btn || !panel) return;
    function close() { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); }
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = panel.hidden;
      panel.hidden = !open;
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("click", function (e) {
      if (!panel.hidden && !panel.contains(e.target) && !btn.contains(e.target)) close();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !panel.hidden) close();
    });
  })();

  // ── Suggestion buttons fill the composer and send. ──────────────────────
  document.querySelectorAll(".suggest-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var msgEl = document.getElementById("message");
      if (!msgEl) return;
      var span = btn.querySelector("span");
      msgEl.value = span ? span.textContent.trim() : btn.textContent.trim();
      if (typeof form.requestSubmit === "function") form.requestSubmit();
      else sendBtn.click();
    });
  });

  if (sendBtn.disabled) return; // chatbot not configured

  // Enter submits, Shift+Enter newline; textarea auto-grows.
  var messageInput = document.getElementById("message");
  if (messageInput) {
    messageInput.addEventListener("input", function () {
      messageInput.style.height = "auto";
      messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + "px";
    });
    messageInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        if (typeof form.requestSubmit === "function") form.requestSubmit();
        else sendBtn.click();
      }
    });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var messageEl = document.getElementById("message");
    var modelEl = document.getElementById("model");
    var message = messageEl.value.trim();
    if (!message) return;

    // Clear the composer immediately on send — the message is already
    // captured and echoed as the user bubble; the field shouldn't hold the
    // sent text for the whole turn.
    messageEl.value = "";
    messageEl.style.height = "auto";

    if (emptyState) emptyState.style.display = "none";

    renderUserBubble(message);
    var assistantBubble = renderAssistantBubble();

    sendBtn.disabled = true;
    sendBtn.classList.add("disabled");

    var body = new URLSearchParams();
    body.set("message", message);
    if (modelEl) body.set("model", modelEl.value);

    fetch("/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    })
      .then(function (resp) {
        if (!resp.ok) { renderError(assistantBubble, "HTTP " + resp.status); return; }
        return consumeSse(resp.body, assistantBubble);
      })
      .catch(function (err) { renderError(assistantBubble, String(err)); })
      .finally(function () {
        sendBtn.disabled = false;
        sendBtn.classList.remove("disabled");
        messageEl.focus();  // composer was already cleared on send
        resolveAllPending(assistantBubble); // backstop if stream ended early
        removeTyping(assistantBubble);
      });
  });

  // ── SSE consumer ────────────────────────────────────────────────────────
  async function consumeSse(stream, assistantBubble) {
    var reader = stream.getReader();
    var decoder = new TextDecoder();
    var buffer = "";

    while (true) {
      var res = await reader.read();
      if (res.done) break;
      buffer += decoder.decode(res.value, { stream: true });

      var sep;
      while ((sep = buffer.indexOf("\n\n")) >= 0) {
        var raw = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        var parsed = parseSseEvent(raw);
        if (!parsed) continue;

        switch (parsed.event) {
          case "start": break;
          case "text": appendText(assistantBubble, parsed.data.chunk || ""); break;
          case "tool_call": renderToolCard(assistantBubble, parsed.data); break;
          case "tool_result":
            resolveToolResult(assistantBubble, parsed.data);
            try {
              var s = JSON.stringify(parsed.data || {});
              scanForTokens(s, CONFIRM_URL_RE, "confirm");
              scanForTokens(s, CAPTURE_URL_RE, "capture");
            } catch (_) {}
            break;
          case "done":
            renderUsageFooter(assistantBubble, parsed.data);
            resolveAllPending(assistantBubble); // turn ended → tools finished
            // Refresh the conversation drawer: a brand-new conversation and
            // its freshly-generated title should appear without a reload.
            if (typeof loadConversations === "function") loadConversations();
            // Scan the *complete* assistant text once, now that streaming is
            // done. (Scanning incrementally in appendText could match a token
            // chunk-split mid-stream — a partial id ≥20 chars — and render a
            // phantom "expired" approval card. The authoritative confirm_url
            // already came through the tool_result above; this only catches a
            // URL that appears solely in prose.)
            try {
              var fullText = assistantBubble.querySelector(".at-blocks").textContent;
              scanForTokens(fullText, CONFIRM_URL_RE, "confirm");
              scanForTokens(fullText, CAPTURE_URL_RE, "capture");
            } catch (_) {}
            break;
          case "error": renderError(assistantBubble, parsed.data.message); break;
        }
      }
    }
  }

  function parseSseEvent(raw) {
    var event = "message", data = "";
    raw.split("\n").forEach(function (line) {
      if (line.indexOf("event:") === 0) event = line.slice(6).trim();
      else if (line.indexOf("data:") === 0) data = line.slice(5).trim();
    });
    if (!data) return null;
    try { return { event: event, data: JSON.parse(data) }; } catch (_) { return null; }
  }

  // ── Rendering ─────────────────────────────────────────────────────────
  function renderUserBubble(text) {
    var turn = document.createElement("div");
    turn.className = "turn";
    var bubble = document.createElement("div");
    bubble.className = "user-bubble";
    var ub = document.createElement("div");
    ub.className = "ub";
    ub.textContent = text;
    var av = document.createElement("span");
    av.className = "avatar";
    av.textContent = (window.ADMZ_INITIALS || "EC");
    bubble.appendChild(ub);
    bubble.appendChild(av);
    turn.appendChild(bubble);
    transcript.appendChild(turn);
  }

  function renderAssistantBubble() {
    var at = document.createElement("div");
    at.className = "assistant-turn";
    at.innerHTML =
      '<span class="sp">' + ico("sparkles") + "</span>" +
      '<div class="at-body">' +
      '<div class="at-blocks"></div>' +
      '<div class="typing"><span></span><span></span><span></span></div>' +
      '<div class="chat-footer"></div>' +
      "</div>";
    at._pending = []; // tool cards awaiting resolution
    transcript.appendChild(at);
    icons();
    return at;
  }

  // The text block to append into: reuse the last block if it's text, else
  // start a new one — so a tool card rendered between two text runs splits
  // them and everything stays in arrival order.
  function currentTextBlock(bubble) {
    var blocks = bubble.querySelector(".at-blocks");
    var last = blocks.lastElementChild;
    if (last && last.classList.contains("assistant-text")) return last;
    var el = document.createElement("div");
    el.className = "assistant-text";
    blocks.appendChild(el);
    return el;
  }

  function removeTyping(bubble) {
    if (!bubble) return;
    var t = bubble.querySelector(".typing");
    if (t) t.remove();
  }

  var CONFIRM_URL_RE = /\/confirm\/([A-Za-z0-9_-]{20,})/g;
  var CAPTURE_URL_RE = /\/capture\/([A-Za-z0-9_-]{20,})/g;
  var seenTokens = new Set();

  function appendText(bubble, chunk) {
    currentTextBlock(bubble).textContent += chunk;
    // NOTE: do NOT scan for /confirm|/capture tokens here — mid-stream the
    // text can hold a chunk-split (partial) token that the {20,} regex would
    // match, rendering a phantom approval card. Tokens are scanned from the
    // structured tool_result (authoritative) and once more on `done` (the
    // complete text). See the SSE switch above.
  }

  function scanForTokens(buffer, re, kind) {
    re.lastIndex = 0;
    var m;
    while ((m = re.exec(buffer)) !== null) {
      var token = m[1];
      var key = kind + ":" + token;
      if (seenTokens.has(key)) continue;
      seenTokens.add(key);
      if (kind === "confirm") { renderApprovalCard(token); addPinnedAction("confirm", token); }
      else if (kind === "capture") { renderCaptureCard(token); addPinnedAction("capture", token); }
    }
  }

  // ── Tool-call card ──────────────────────────────────────────────────────
  function renderToolCard(bubble, data) {
    var card = document.createElement("div");
    card.className = "tool-card";
    card.dataset.tool = data.name || "tool";
    if (data.call_id != null) card.dataset.callId = String(data.call_id);
    card._args = (data.args !== undefined) ? data.args : null;
    card._result = null;
    card.innerHTML =
      '<div class="tc-row" role="button" tabindex="0" aria-expanded="false">' +
      '<span class="tc-chev"></span>' +
      '<span class="tc-ico tool-status"><span class="spinner"></span></span>' +
      '<span class="tc-label">Calling</span>' +
      '<span class="tc-op tool-name"></span>' +
      '<span class="tc-args tool-summary"></span>' +
      '<span class="tc-status"><span class="badge blue mono">RUNNING</span></span>' +
      "</div>" +
      '<div class="tc-result" style="display:none"></div>' +
      '<div class="tc-details" style="display:none"></div>';
    card.querySelector(".tool-name").textContent = data.name || "tool";
    card.querySelector(".tool-summary").textContent = data.summary ? "(" + data.summary + ")" : "";
    card.querySelector(".tc-chev").innerHTML = ico("chevron-right");
    var row = card.querySelector(".tc-row");
    row.addEventListener("click", function () { toggleDetails(card); });
    row.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
        e.preventDefault();
        toggleDetails(card);
      }
    });
    (bubble ? bubble.querySelector(".at-blocks") : transcript).appendChild(card);
    if (bubble && bubble._pending) bubble._pending.push(card);
    icons();
    return card;
  }

  // Toggle a card's expanded detail pane (args + result).
  function toggleDetails(card) {
    var pane = card.querySelector(".tc-details");
    var chev = card.querySelector(".tc-chev");
    var row = card.querySelector(".tc-row");
    if (!pane) return;
    var open = pane.style.display !== "none" && pane.style.display !== "";
    // Treat empty string (initial) as closed.
    open = pane.dataset.open === "1";
    if (open) {
      pane.style.display = "none";
      pane.dataset.open = "0";
      if (chev) chev.classList.remove("open");
      if (row) row.setAttribute("aria-expanded", "false");
    } else {
      renderDetails(card);
      pane.style.display = "";
      pane.dataset.open = "1";
      if (chev) chev.classList.add("open");
      if (row) row.setAttribute("aria-expanded", "true");
    }
  }

  function renderDetails(card) {
    var pane = card.querySelector(".tc-details");
    if (!pane) return;
    function section(label, value) {
      var body;
      if (value === undefined || value === null) {
        body = '<span class="tcd-muted">' + (value === undefined ? "(pending)" : "(none)") + "</span>";
      } else {
        var txt;
        try { txt = JSON.stringify(value, null, 2); } catch (_) { txt = String(value); }
        if (txt.length > 4000) txt = txt.slice(0, 4000) + "\n… (truncated)";
        body = '<pre class="tcd-pre">' + escapeHtml(txt) + "</pre>";
      }
      return '<div class="tcd-h">' + escapeHtml(label) + "</div>" + body;
    }
    // _args === null means the call carried no args field (e.g. AFC path).
    var argsVal = (card._args === null) ? undefined : card._args;
    var resVal = (card._result === null) ? undefined : card._result;
    pane.innerHTML = section("Arguments", argsVal) + section("Result", resVal);
  }

  // Match an incoming tool_result to the right pending card (by call_id, then
  // name, else oldest), and resolve it.
  function resolveToolResult(bubble, data) {
    if (!bubble || !bubble._pending || !bubble._pending.length) return;
    var idx = -1;
    if (data.call_id != null) {
      for (var j = 0; j < bubble._pending.length; j++) {
        if (bubble._pending[j].dataset.callId === String(data.call_id)) { idx = j; break; }
      }
    }
    if (idx < 0) {
      for (var i = 0; i < bubble._pending.length; i++) {
        if (data.name && bubble._pending[i].dataset.tool === data.name) { idx = i; break; }
      }
    }
    if (idx < 0) idx = 0;
    var card = bubble._pending.splice(idx, 1)[0];
    if (data.result !== undefined) card._result = data.result;
    updateToolCard(card, data);
  }

  // The streaming path emits tool_call but (for AFC-executed tools) no
  // tool_result, so cards would spin forever. When the turn ends, every
  // still-pending tool has necessarily finished — resolve to a neutral
  // "done" (we can't claim ok/err without a result event).
  function resolveAllPending(bubble) {
    if (!bubble || !bubble._pending) return;
    bubble._pending.forEach(function (card) { updateToolCard(card, { status: "done" }); });
    bubble._pending = [];
  }

  function updateToolCard(card, data) {
    if (!card) return;
    var statusEl = card.querySelector(".tool-status");
    var badge = card.querySelector(".tc-status");
    var ok = data.status === "ok";
    var err = data.status === "error";
    var skipped = data.status === "skipped";
    if (statusEl) {
      statusEl.innerHTML = err ? ico("x-circle")
        : skipped ? ico("clock") : ico("check-circle-2");
      statusEl.className = "tc-ico tool-status " +
        (ok ? "fg-green" : err ? "fg-red" : skipped ? "fg-amber" : "fg-grey");
    }
    if (badge) {
      var cls = ok ? "green" : err ? "red" : skipped ? "amber" : "grey";
      var label = ok ? "COMPLETED" : err ? "BLOCKED"
        : skipped ? "AWAITING APPROVAL" : "DONE";
      badge.innerHTML = '<span class="badge ' + cls + ' mono">' + label + "</span>";
    }
    if (data.summary) {
      var r = card.querySelector(".tc-result");
      r.textContent = data.summary;
      r.style.display = "";
    }
    // An AWAITING-APPROVAL card carries the confirm token — record it so a
    // later out-of-band approval can find this card and flip it. The token is
    // read from confirm_url, NOT confirm_token: the display redactor masks any
    // key containing "token" (confirm_token -> "***"), but confirm_url
    // ("/confirm/{token}") passes through intact.
    if (skipped && card._result) {
      var tok = "";
      var m = String(card._result.confirm_url || "").match(/\/confirm\/([A-Za-z0-9_-]+)/);
      if (m) tok = m[1];
      else if (card._result.confirm_token && card._result.confirm_token !== "***") {
        tok = card._result.confirm_token;
      }
      if (tok) card.dataset.confirmToken = tok;
    }
    // If the detail pane is open, re-render now that _result has arrived.
    var pane = card.querySelector(".tc-details");
    if (pane && pane.dataset.open === "1") renderDetails(card);
    icons();
  }

  // Flip an AWAITING-APPROVAL tool card once its confirm token is resolved
  // out-of-band (the approval widget). status: "ok" (approved+executed) or
  // "error" (denied / failed). Matched by the confirm_token stashed above.
  function resolveApprovedToolCard(token, status, summary) {
    if (!token) return;
    var sel = '.tool-card[data-confirm-token="' + token + '"]';
    transcript.querySelectorAll(sel).forEach(function (card) {
      updateToolCard(card, {
        status: status || "ok",
        summary: summary || (status === "error" ? "Denied" : "Approved — executed"),
      });
    });
  }

  function renderUsageFooter(bubble, data) {
    if (!data) return;
    var footer = bubble.querySelector(".chat-footer");
    if (!footer) return;
    var parts = [];
    if (data.input_tokens != null) parts.push("in=" + data.input_tokens);
    if (data.output_tokens != null) parts.push("out=" + data.output_tokens);
    if (data.model) parts.push("model=" + data.model);
    if (data.cost_usd != null) parts.push("≈$" + Number(data.cost_usd).toFixed(4));
    if (parts.length) footer.textContent = "tokens: " + parts.join(" · ");
  }

  function renderError(bubble, message) {
    removeTyping(bubble);
    var err = document.createElement("div");
    err.className = "result-row red";
    err.innerHTML = ico("x-circle") + "<span></span>";
    err.querySelector("span").textContent = "Error: " + message;
    if (bubble && bubble.parentNode) bubble.parentNode.insertBefore(err, bubble.nextSibling);
    else transcript.appendChild(err);
    icons();
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // ── Inline approval card (two-gate) ──────────────────────────────────────
  function renderApprovalCard(token) {
    var card = document.createElement("div");
    card.className = "approval-card";
    card.dataset.confirmToken = token;
    card.innerHTML =
      '<div class="ac-head">' + ico("shield-check") +
      '<span class="ttl">Approval required</span><span class="r"></span></div>' +
      '<div class="ac-body"><div class="approval-body"><span class="mono">Loading…</span></div></div>';
    transcript.appendChild(card);
    icons();

    fetch("/api/chat/confirm/" + encodeURIComponent(token))
      .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
      .then(function (resp) {
        if (!resp.ok || !resp.body) {
          renderApprovalDone(card, "error",
            resp.body && resp.body.status === "expired_or_not_found"
              ? "This confirmation link is invalid or has expired — ask me to run the action again."
              : "Could not load confirmation details.");
          // A card that can't load is dead — drop its pinned chip so it
          // doesn't linger (e.g. a phantom/expired token).
          removePinnedAction("confirm", token);
          return;
        }
        if (resp.body.status === "completed") {
          renderApprovalDone(card, "ok", "Already approved.");
          removePinnedAction("confirm", token);
          resolveApprovedToolCard(token);  // flip the in-chat tool card too
          return;
        }
        populateApprovalForm(card, token, resp.body);
      })
      .catch(function (err) {
        renderApprovalDone(card, "error", String(err));
        removePinnedAction("confirm", token);
      });
  }

  function populateApprovalForm(card, token, details) {
    var dangerous = (details.risk_level || "").toLowerCase() === "dangerous";
    if (dangerous) card.classList.add("dangerous");
    var head = card.querySelector(".ac-head");
    head.innerHTML = ico(dangerous ? "alert-triangle" : "shield-check") +
      '<span class="ttl">Approval required</span><span class="r">' +
      riskBadge(details.risk_level) + "</span>";

    var body = card.querySelector(".approval-body");
    var opLine =
      '<div class="ac-grid">' +
      '<span class="section-label">Operation</span><span class="mono ink" style="font-weight:600">' +
      escapeHtml(details.operation_id || "operation") + "</span>" +
      (details.device_id ? '<span class="section-label">Target</span><span class="mono text">' +
        escapeHtml(details.device_id) + "</span>" : "") +
      "</div>";
    var dangerLine = details.danger_description
      ? '<p class="ac-summary">' + escapeHtml(details.danger_description) + "</p>" : "";
    var gate =
      '<div class="gate-trace">' + ico("check") +
      "<span>Gate 1 · plain-language review</span>" + ico("chevron-right") +
      '<span>Gate 2 · risk check · armed</span></div>';
    var passwordRow = details.needs_password
      ? '<div class="ac-password"><div class="lbl">' + ico("lock") +
        "Out-of-band confirmation</div>" +
        '<input id="pw-' + token + '" type="password" autocomplete="off" placeholder="Confirmation password"></div>'
      : "";
    var actions =
      '<div class="ac-actions">' +
      '<button class="btn subtle sm deny-btn" type="button">' + ico("x") + "Deny</button>" +
      '<span class="spacer"></span>' +
      '<button class="btn ' + (dangerous ? "danger" : "primary") + ' sm approve-btn" type="button">' +
      ico(dangerous ? "lock" : "check") + (dangerous ? "Confirm dangerous op" : "Approve") + "</button></div>" +
      '<div class="approval-error result-row red" style="display:none"><span></span></div>';

    body.innerHTML = opLine + dangerLine + gate + passwordRow + actions;
    icons();

    body.querySelector(".approve-btn").addEventListener("click", function () {
      submitApproval(card, token, details.needs_password);
    });
    body.querySelector(".deny-btn").addEventListener("click", function () {
      renderApprovalDone(card, "grey", details.operation_id + " denied — no change made");
      removePinnedAction("confirm", token);
      resolveApprovedToolCard(token, "error", "Denied — no change made");
    });
  }

  function submitApproval(card, token, needsPassword) {
    var body = card.querySelector(".approval-body");
    var errorEl = body.querySelector(".approval-error");
    var approveBtn = body.querySelector(".approve-btn");
    var params = new URLSearchParams();
    if (needsPassword) {
      var pwInput = body.querySelector("#pw-" + token);
      var pw = pwInput ? pwInput.value : "";
      if (!pw) { showApprovalError(errorEl, "Password required."); return; }
      params.set("confirm_password", pw);
    }
    approveBtn.disabled = true;
    approveBtn.textContent = "Approving…";
    errorEl.style.display = "none";

    fetch("/api/chat/confirm/" + encodeURIComponent(token), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: params.toString(),
    })
      .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, status: r.status, body: b }; }); })
      .then(function (resp) {
        if (resp.ok && resp.body && resp.body.status === "completed") {
          removePinnedAction("confirm", token);
          // The op already ran synchronously on approval — the POST returned
          // its outcome. So this is the FINAL state (ADMZ doesn't track the
          // device's own post-reboot recovery). Reflect success/failure.
          var oc = resp.body.outcome;
          if (oc && oc.success === false) {
            var failMsg = "Approved, but the operation failed" + (oc.error ? ": " + oc.error : "");
            renderApprovalDone(card, "error", failMsg);
            resolveApprovedToolCard(token, "error", "Approved — operation failed");
          } else {
            renderApprovalDone(card, "ok", "Approved — executed");
            resolveApprovedToolCard(token, "ok", "Approved — executed");
          }
          return;
        }
        var msg = (resp.body && (resp.body.error || resp.body.status)) || "HTTP " + resp.status;
        var terminal = resp.body && (resp.body.status === "expired_or_not_found" || resp.body.status === "locked");
        if (terminal) { renderApprovalDone(card, "error", msg); }
        else { showApprovalError(errorEl, msg); approveBtn.disabled = false; approveBtn.innerHTML = ico("check") + "Approve"; icons(); }
      })
      .catch(function (err) {
        showApprovalError(errorEl, String(err));
        approveBtn.disabled = false; approveBtn.innerHTML = ico("check") + "Approve"; icons();
      });
  }

  function showApprovalError(errorEl, msg) {
    if (!errorEl) return;
    errorEl.querySelector("span").textContent = msg;
    errorEl.style.display = "";
  }

  function renderApprovalDone(card, status, message) {
    var sem = status === "ok" ? "green" : status === "grey" ? "grey" : "red";
    var name = status === "ok" ? "check-circle-2" : status === "grey" ? "x-circle" : "alert-triangle";
    var body = card.querySelector(".ac-body");
    card.classList.remove("dangerous");
    body.innerHTML = '<div class="result-row ' + sem + '">' + ico(name) + "<span></span></div>";
    body.querySelector("span").textContent = message;
    icons();
  }

  function riskBadge(risk) {
    var r = (risk || "").toLowerCase();
    var map = { "read-only": ["green", "READ"], readonly: ["green", "READ"], normal: ["blue", "NORMAL"],
      "service-affecting": ["amber", "SERVICE"], service: ["amber", "SERVICE"], dangerous: ["red", "DANGER"] };
    var v = map[r] || ["grey", (risk || "").toUpperCase()];
    return '<span class="risk-badge ' + v[0] + '">' + (v[0] === "red" ? ico("alert-triangle") : "") + v[1] + "</span>";
  }

  // ── Inline capture card ──────────────────────────────────────────────────
  function renderCaptureCard(token) {
    var card = document.createElement("div");
    card.className = "approval-card";
    card.dataset.captureToken = token;
    card.innerHTML =
      '<div class="ac-head">' + ico("key") +
      '<span class="ttl">Credential capture pending</span></div>' +
      '<div class="ac-body"><div class="capture-body"><span class="mono">Loading…</span></div></div>';
    transcript.appendChild(card);
    icons();

    fetch("/api/capture/" + encodeURIComponent(token) + "/status")
      .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
      .then(function (resp) {
        if (!resp.ok || !resp.body) { renderCaptureDone(card, "error", "Could not load capture details."); return; }
        if (resp.body.status === "expired_or_not_found") { renderCaptureDone(card, "error", "This capture link has expired."); removePinnedAction("capture", token); return; }
        if (resp.body.status === "completed") { renderCaptureDone(card, "ok", "Credentials already captured."); removePinnedAction("capture", token); return; }
        populateCaptureCard(card, token, resp.body);
      })
      .catch(function (err) { renderCaptureDone(card, "error", String(err)); });
  }

  function populateCaptureCard(card, token, details) {
    var body = card.querySelector(".capture-body");
    var deviceLine = details.device_id
      ? '<div class="ac-grid"><span class="section-label">Device</span><span class="mono text">' +
        escapeHtml(details.device_id) + "</span>" +
        (details.account_id ? '<span class="section-label">Account</span><span class="mono text">' +
          escapeHtml(details.account_id) + "</span>" : "") + "</div>"
      : "";
    body.innerHTML = deviceLine +
      '<p class="ac-summary">Open the single-use form in a new tab to enter credentials. The form is tied to this token.</p>' +
      '<div class="ac-actions">' +
      '<a class="btn accent sm" href="/capture/' + encodeURIComponent(token) + '" target="_blank" rel="noopener">' +
      ico("external-link") + "Open capture form</a>" +
      '<span class="spacer"></span>' +
      '<button class="btn subtle sm dismiss-btn" type="button">Dismiss</button></div>';
    icons();
    body.querySelector(".dismiss-btn").addEventListener("click", function () {
      card.remove(); removePinnedAction("capture", token);
    });
  }

  function renderCaptureDone(card, kind, message) {
    var sem = kind === "ok" ? "green" : "red";
    var body = card.querySelector(".ac-body");
    body.innerHTML = '<div class="result-row ' + sem + '">' + ico(kind === "ok" ? "check-circle-2" : "alert-triangle") + "<span></span></div>";
    body.querySelector("span").textContent = message;
    icons();
  }

  // ── Pinned-action widget ──────────────────────────────────────────────────
  var actionsContainer = document.getElementById("chat-actions");
  var actionsList = document.getElementById("chat-actions-list");
  var pinnedActions = new Map();

  function actionKey(kind, token) { return kind + ":" + token; }
  function showActionsContainer() { if (actionsContainer) actionsContainer.style.display = ""; }
  function hideActionsContainerIfEmpty() {
    if (actionsContainer && pinnedActions.size === 0) actionsContainer.style.display = "none";
  }

  function addPinnedAction(kind, token) {
    if (!actionsList) return;
    var key = actionKey(kind, token);
    if (pinnedActions.has(key)) return;

    var row = document.createElement("div");
    row.className = "pending-row";
    var isCapture = kind === "capture";
    row.innerHTML =
      '<span class="pr-ico ' + (isCapture ? "fg-blue" : "fg-red") + '">' + ico(isCapture ? "key" : "lock") + "</span>" +
      '<div style="min-width:0"><div class="pr-op">' +
      (isCapture ? "Capture credentials" : "Approve dangerous op") + "</div>" +
      '<div class="pr-target mono"></div></div>' +
      '<div class="pr-right"><a class="btn accent sm"></a></div>';
    row.querySelector(".pr-target").textContent = token.slice(0, 10) + "…";

    var action = row.querySelector("a.btn");
    if (isCapture) {
      action.href = "/capture/" + encodeURIComponent(token);
      action.target = "_blank"; action.rel = "noopener";
      action.innerHTML = ico("external-link") + "Open form";
    } else {
      action.href = "#";
      action.innerHTML = ico("arrow-down") + "Jump to approval";
      action.addEventListener("click", function (e) {
        e.preventDefault();
        var c = transcript.querySelector('[data-confirm-token="' + token + '"]');
        if (c) c.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }

    actionsList.appendChild(row);
    pinnedActions.set(key, row);
    showActionsContainer();
    icons();

    setTimeout(function () { removePinnedAction(kind, token); }, 5 * 60 * 1000);
  }

  function removePinnedAction(kind, token) {
    var key = actionKey(kind, token);
    var row = pinnedActions.get(key);
    if (!row) return;
    row.remove();
    pinnedActions.delete(key);
    hideActionsContainerIfEmpty();
  }

  // Expose the approval/capture cards so voice mode (voice.js) can render the
  // same inline confirmation widget instead of having the model read the
  // /confirm URL aloud. Idempotent per token (skips if a card already exists).
  window.admzRenderApprovalCard = function (token) {
    if (!token) return;
    if (transcript.querySelector('.approval-card[data-confirm-token="' + token + '"]')) return;
    renderApprovalCard(token);
    addPinnedAction("confirm", token);
    icons();
  };
  window.admzRenderCaptureCard = function (token) {
    if (!token) return;
    if (transcript.querySelector('.capture-card[data-capture-token="' + token + '"]')) return;
    renderCaptureCard(token);
    addPinnedAction("capture", token);
    icons();
  };

  // ──────────────────────────────────────────────────────────────────────────
  // Conversation history drawer (left slide-out pane)
  // ──────────────────────────────────────────────────────────────────────────
  var drawer = document.getElementById("conv-drawer");
  var scrim = document.getElementById("conv-scrim");
  var convList = document.getElementById("conv-list");
  var convToggle = document.getElementById("conv-toggle");

  function openDrawer() {
    if (!drawer) return;
    drawer.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
    if (scrim) scrim.hidden = false;
    loadConversations();
  }
  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    if (scrim) scrim.hidden = true;
  }

  function relTime(iso) {
    if (!iso) return "";
    var then = new Date(iso).getTime();
    if (isNaN(then)) return "";
    var secs = Math.max(0, (Date.now() - then) / 1000);
    if (secs < 60) return "just now";
    var mins = Math.floor(secs / 60);
    if (mins < 60) return mins + "m ago";
    var hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + "h ago";
    var days = Math.floor(hrs / 24);
    if (days < 7) return days + "d ago";
    return new Date(then).toLocaleDateString();
  }

  function loadConversations() {
    if (!convList) return;
    fetch("/api/chat/conversations", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        renderConvList(data.conversations || [], data.active);
      })
      .catch(function () {});
  }

  function renderConvList(items, activeId) {
    convList.innerHTML = "";
    if (!items.length) {
      var empty = document.createElement("div");
      empty.className = "conv-empty";
      empty.textContent = "No conversations yet.";
      convList.appendChild(empty);
      return;
    }
    items.forEach(function (c) {
      var row = document.createElement("div");
      row.className = "conv-row" + (c.active ? " active" : "");
      row.dataset.id = c.id;

      var main = document.createElement("button");
      main.type = "button";
      main.className = "conv-open";
      var title = document.createElement("span");
      title.className = "conv-title";
      title.textContent = c.title || "New chat";
      var meta = document.createElement("span");
      meta.className = "conv-time";
      meta.textContent = relTime(c.updated_at);
      main.appendChild(title);
      main.appendChild(meta);
      main.addEventListener("click", function () { openConversation(c.id); });

      var actions = document.createElement("span");
      actions.className = "conv-actions";
      var ren = document.createElement("button");
      ren.type = "button";
      ren.className = "icon-btn xs";
      ren.title = "Rename";
      ren.innerHTML = ico("pencil");
      ren.addEventListener("click", function (e) {
        e.stopPropagation();
        renameConversation(c.id, c.title || "");
      });
      var del = document.createElement("button");
      del.type = "button";
      del.className = "icon-btn xs";
      del.title = "Delete";
      del.innerHTML = ico("trash-2");
      del.addEventListener("click", function (e) {
        e.stopPropagation();
        deleteConversation(c.id);
      });
      actions.appendChild(ren);
      actions.appendChild(del);

      row.appendChild(main);
      row.appendChild(actions);
      convList.appendChild(row);
    });
    icons();
  }

  function resetTranscript() {
    transcript.innerHTML = "";
    seenTokens.clear();
    var actions = document.getElementById("chat-actions");
    var actionsList = document.getElementById("chat-actions-list");
    if (actionsList) actionsList.innerHTML = "";
    if (actions) actions.style.display = "none";
  }

  function replayMessage(role, text) {
    if (role === "user") {
      renderUserBubble(text);
    } else {
      var at = renderAssistantBubble();
      currentTextBlock(at).textContent = text;
      removeTyping(at);
    }
  }

  function openConversation(id) {
    fetch("/api/chat/conversations/" + encodeURIComponent(id), {
      headers: { Accept: "application/json" },
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        return fetch("/api/chat/conversations/" + encodeURIComponent(id) + "/activate", {
          method: "POST",
        }).then(function () {
          if (emptyState) emptyState.style.display = "none";
          resetTranscript();
          (data.messages || []).forEach(function (m) { replayMessage(m.role, m.text); });
          icons();
          closeDrawer();
          loadConversations();
        });
      })
      .catch(function () {});
  }

  // On load, resume the active conversation in the main view so the screen
  // matches what the next message continues (instead of a misleadingly blank
  // transcript). "New chat" stays the explicit way to start fresh. Display-only:
  // we render the last RESTORE_MAX messages; the LLM context window is capped
  // separately server-side.
  var RESTORE_MAX = 60; // ~30 turns shown on resume
  function restoreActiveConversation() {
    // Only restore into a genuinely empty transcript — skip the no-JS,
    // server-rendered fallback turn (which omits the #chat-empty marker).
    if (!emptyState || transcript.children.length) return;
    fetch("/api/chat/conversations", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.active) return;
        var meta = (data.conversations || []).filter(function (c) {
          return c.id === data.active;
        })[0];
        if (!meta || !meta.message_count) return; // active conversation is empty
        return fetch("/api/chat/conversations/" + encodeURIComponent(data.active), {
          headers: { Accept: "application/json" },
        })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (conv) {
            if (!conv || !conv.messages || !conv.messages.length) return;
            if (transcript.children.length) return; // user already started typing/sending
            if (emptyState) emptyState.style.display = "none";
            conv.messages.slice(-RESTORE_MAX).forEach(function (m) {
              replayMessage(m.role, m.text);
            });
            icons();
            transcript.scrollIntoView(false);
          });
      })
      .catch(function () {});
  }

  function newConversation() {
    fetch("/api/chat/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function () {
        resetTranscript();
        if (emptyState) emptyState.style.display = "";
        closeDrawer();
        loadConversations();
        var msgEl = document.getElementById("message");
        if (msgEl) msgEl.focus();
      })
      .catch(function () {});
  }

  function renameConversation(id, current) {
    var next = window.prompt("Rename conversation", current || "");
    if (next == null) return;
    next = next.trim();
    if (!next) return;
    fetch("/api/chat/conversations/" + encodeURIComponent(id), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: next }),
    })
      .then(function (r) { if (r.ok) loadConversations(); })
      .catch(function () {});
  }

  function deleteConversation(id) {
    if (!window.confirm("Delete this conversation? This cannot be undone.")) return;
    fetch("/api/chat/conversations/" + encodeURIComponent(id), { method: "DELETE" })
      .then(function (r) {
        if (!r.ok) return;
        loadConversations();
      })
      .catch(function () {});
  }

  if (convToggle) convToggle.addEventListener("click", openDrawer);
  if (scrim) scrim.addEventListener("click", closeDrawer);
  var convClose = document.getElementById("conv-close");
  if (convClose) convClose.addEventListener("click", closeDrawer);
  // "+ New chat" (drawer) via event delegation so it fires regardless of when
  // the drawer DOM is (re)rendered or the icon is swapped by lucide.
  document.addEventListener("click", function (e) {
    if (!e.target || !e.target.closest) return;
    if (e.target.closest("#conv-new")) {
      e.preventDefault();
      newConversation();
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && drawer && drawer.classList.contains("open")) closeDrawer();
  });

  // Resume the active conversation on Console load (display-only).
  restoreActiveConversation();
})();
