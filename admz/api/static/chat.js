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
        loadNotices(false); // the turn's tools may have resolved one
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
            // Approval/capture widgets are built ONLY from the structured
            // tool_result above. A /confirm|/capture URL appearing solely in the
            // model's prose was fabricated — flag it honestly instead of
            // rendering a phantom "invalid or has expired" widget.
            try {
              var fullText = assistantBubble.querySelector(".at-blocks").textContent;
              flagUnbackedLinks(fullText, assistantBubble);
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
  var seenTokens = new Set();   // tokens that arrived via a structured tool_result (real)
  var warnedTokens = new Set(); // fabricated tokens we've already flagged

  function appendText(bubble, chunk) {
    currentTextBlock(bubble).textContent += chunk;
    // NOTE: do NOT scan for /confirm|/capture tokens here — mid-stream the
    // text can hold a chunk-split (partial) token that the {20,} regex would
    // match, rendering a phantom approval card. Tokens are scanned from the
    // structured tool_result (authoritative) and once more on `done` (the
    // complete text). See the SSE switch above.
  }

  // Render approval/capture widgets from an AUTHORITATIVE source (a structured
  // tool_result). Tokens it surfaces are recorded in seenTokens as "real".
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

  function _matchTokens(buffer, re) {
    re.lastIndex = 0;
    var out = [], m;
    while ((m = re.exec(buffer)) !== null) out.push(m[1]);
    return out;
  }

  // A real /confirm|/capture token always arrives via a structured tool_result
  // (recorded in seenTokens). A token that appears ONLY in the model's prose was
  // fabricated — the model wrote an approval link without actually invoking the
  // gate, so there is no session behind it. Don't render a widget for it (that
  // produced the misleading "invalid or has expired" card); flag it honestly so
  // the user knows nothing was actually started.
  function flagUnbackedLinks(buffer, bubble) {
    var unbacked = false;
    [["confirm", CONFIRM_URL_RE], ["capture", CAPTURE_URL_RE]].forEach(function (pair) {
      _matchTokens(buffer, pair[1]).forEach(function (token) {
        var key = pair[0] + ":" + token;
        if (seenTokens.has(key) || warnedTokens.has(key)) return; // real, or already flagged
        warnedTokens.add(key);
        unbacked = true;
      });
    });
    if (!unbacked) return;
    var warn = document.createElement("div");
    warn.className = "result-row amber";
    warn.innerHTML = ico("alert-triangle") + "<span></span>";
    warn.querySelector("span").textContent =
      "The assistant wrote an approval link but never actually started the " +
      "operation, so there's nothing to approve here. Ask it to run the action " +
      "again — a real approval will appear automatically when it does.";
    if (bubble && bubble.parentNode) bubble.parentNode.insertBefore(warn, bubble.nextSibling);
    else transcript.appendChild(warn);
    icons();
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
        if (resp.body.status === "denied") {
          renderApprovalDone(card, "grey", "Denied — no change made.");
          removePinnedAction("confirm", token);
          resolveApprovedToolCard(token, "error", "Denied — no change made");
          return;
        }
        populateApprovalForm(card, token, resp.body);
      })
      .catch(function (err) {
        renderApprovalDone(card, "error", String(err));
        removePinnedAction("confirm", token);
      });
  }

  // Mirrors the server-rendered plan layout in confirm_form.html: step count,
  // risk badges, and a collapsed step table. Deliberately minimal — ADR-0062
  // will revise this toward an envelope, so a rich version now is work thrown
  // away. The point is only that the operator can see what they are approving.
  function planSummaryHtml(sum) {
    var risk = sum.risk_summary || {};
    var steps = sum.steps || [];
    var n = sum.step_count != null ? sum.step_count : steps.length;
    var badges = '<span class="risk-badge grey">' + n + " step" + (n === 1 ? "" : "s") + "</span>";
    if (risk.dangerous) {
      badges += '<span class="risk-badge red">' + risk.dangerous + " dangerous</span>";
    }
    if (risk["service-affecting"]) {
      badges += '<span class="risk-badge amber">' + risk["service-affecting"] + " service-affecting</span>";
    }
    var rows = steps.map(function (s, i) {
      return "<tr><td>" + escapeHtml(String(s.step != null ? s.step : i + 1)) + "</td>" +
        '<td><span class="mono text">' + escapeHtml(s.device || "") + "</span></td>" +
        '<td><span class="mono text">' + escapeHtml(s.operation || "") + "</span></td>" +
        "<td>" + riskBadge(s.risk) + "</td></tr>";
    }).join("");
    var desc = sum.description
      ? '<p class="ac-summary">' + escapeHtml(sum.description) + "</p>" : "";
    var table = steps.length
      ? "<details open><summary>Plan steps</summary>" +
        '<table class="step-table"><thead><tr><th>#</th><th>Device</th>' +
        "<th>Operation</th><th>Risk</th></tr></thead><tbody>" + rows +
        "</tbody></table></details>"
      : "";
    var onFail = sum.on_failure
      ? '<div class="ac-grid"><span class="section-label">On failure</span>' +
        '<span class="mono text">' + escapeHtml(sum.on_failure) + "</span></div>"
      : "";
    return desc + '<div class="risk-row">' + badges + "</div>" + table + onFail;
  }

  function populateApprovalForm(card, token, details) {
    var dangerous = (details.risk_level || "").toLowerCase() === "dangerous";
    if (dangerous) card.classList.add("dangerous");
    var head = card.querySelector(".ac-head");
    head.innerHTML = ico(dangerous ? "alert-triangle" : "shield-check") +
      '<span class="ttl">Approval required</span><span class="r">' +
      riskBadge(details.risk_level) + "</span>";

    var body = card.querySelector(".approval-body");
    // A plan approval is NOT a single operation: operation_id reads
    // "plan:plan-ab12…" and device_id is the literal "multiple", so the default
    // layout shows the operator nothing to review — the gate that trains people
    // to click. plan_summary is already on the wire from
    // /api/chat/confirm/{token}; it was simply fetched and discarded (#438).
    var opLine = (details.is_plan && details.plan_summary)
      ? planSummaryHtml(details.plan_summary)
      : '<div class="ac-grid">' +
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
      submitApproval(card, token, details);
    });
    body.querySelector(".deny-btn").addEventListener("click", function () {
      // Server-side denial: terminal (the token can never be consumed) and
      // noted back into the conversation so the model knows the user said
      // no. The card resolves the same way even if the POST fails — the
      // session then simply expires like the old client-only behavior.
      fetch("/api/chat/confirm/" + encodeURIComponent(token) + "/deny", { method: "POST" })
        .catch(function () {});
      renderApprovalDone(card, "grey", details.operation_id + " denied — no change made");
      removePinnedAction("confirm", token);
      resolveApprovedToolCard(token, "error", "Denied — no change made");
    });
  }

  // The approval POST does not merely record the decision: it RUNS the
  // operation and answers with the outcome (routes/confirm.py::_approve_session
  // → operations.execute_approved_session). The request is therefore held for
  // as long as the device takes — 31s for a firmware upload to a C8110 on
  // 2026-09-15 — and a disabled button with no explanation reads as a hung
  // page, which is exactly how that was reported. This line says what is
  // running, counts the seconds, and names the slow case.
  function startApprovalWait(body, operationId) {
    var row = document.createElement("div");
    row.className = "result-row grey approval-wait";
    row.innerHTML = ico("clock") + "<span></span>";
    body.appendChild(row);
    icons();
    var label = row.querySelector("span");
    var started = Date.now();
    var firmware = /firmware/i.test(operationId || "");
    function tick() {
      var secs = Math.round((Date.now() - started) / 1000);
      label.textContent =
        (firmware
          ? "Uploading firmware to the device — this usually takes 30–60 seconds"
          : "Running it on the device now") +
        " · " + secs + "s. The card updates when the device answers.";
    }
    tick();
    var timer = setInterval(tick, 1000);
    return function stopApprovalWait() {
      clearInterval(timer);
      if (row.parentNode) row.parentNode.removeChild(row);
    };
  }

  function submitApproval(card, token, details) {
    var needsPassword = details && details.needs_password;
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
    var stopWait = startApprovalWait(body, details && details.operation_id);

    fetch("/api/chat/confirm/" + encodeURIComponent(token), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: params.toString(),
    })
      .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, status: r.status, body: b }; }); })
      .then(function (resp) {
        stopWait();
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
          // The approval POST we just awaited already wrote the console note,
          // so the continuation is owed right now — no polling needed (#444).
          maybeResumeConversation();
          return;
        }
        var msg = (resp.body && (resp.body.error || resp.body.status)) || "HTTP " + resp.status;
        var terminal = resp.body && (resp.body.status === "expired_or_not_found" || resp.body.status === "locked");
        if (terminal) { renderApprovalDone(card, "error", msg); }
        else { showApprovalError(errorEl, msg); approveBtn.disabled = false; approveBtn.innerHTML = ico("check") + "Approve"; icons(); }
      })
      .catch(function (err) {
        stopWait();
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
    if (role === "event") {
      // Console event note (out-of-band approval/capture outcome) —
      // a small centered chip, not a chat bubble.
      var chip = document.createElement("div");
      chip.className = "event-chip";
      chip.textContent = (text || "").replace(/^\[console\]\s*/, "");
      transcript.appendChild(chip);
    } else if (role === "user") {
      renderUserBubble(text);
    } else {
      var at = renderAssistantBubble();
      currentTextBlock(at).textContent = text;
      removeTyping(at);
    }
  }

  // Returns its promise so a caller can sequence after the transcript is
  // rendered (a notice review continues the conversation it just opened).
  function openConversation(id) {
    return fetch("/api/chat/conversations/" + encodeURIComponent(id), {
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
    // Returned so callers can sequence after it — the continuation trigger
    // (#444) MUST NOT append its bubble until the transcript has been
    // restored, because the guards above bail on a non-empty transcript.
    return fetch("/api/chat/conversations", { headers: { Accept: "application/json" } })
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

  // Rehydrate pinned confirm/capture widgets from the server's own session
  // tables (#340). Widgets are otherwise built ONLY from a live turn's
  // structured tool_result (see the switch above, and chat.js's own rule at
  // the top of this file) — restoreActiveConversation() rebuilds the
  // TRANSCRIPT above but rebuilds no widgets, so a plain reload, a second
  // tab, or returning from a /capture|/confirm full-page navigation drops
  // every pinned action, including any the operator never got to. This does
  // not weaken the "only from a structured tool_result" rule — the source
  // here is the server's session table, strictly stronger evidence than a
  // URL merely appearing in message text (which is what that rule exists to
  // distrust). Runs unconditionally, independent of whether the transcript
  // itself needed restoring — pending actions are principal-scoped, not
  // conversation-scoped. Reuses the SAME idempotent render hooks voice mode
  // uses (admzRenderApprovalCard / admzRenderCaptureCard): each checks
  // whether a card for that token already exists before rendering, so this
  // can never double-render one a live turn is concurrently creating.
  function rehydratePendingActions() {
    fetch("/api/chat/pending-actions", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.pending) return;
        data.pending.forEach(function (item) {
          if (item.kind === "confirm") window.admzRenderApprovalCard(item.token);
          else if (item.kind === "capture") window.admzRenderCaptureCard(item.token);
        });
      })
      .catch(function () {});
    // Deliberately silent on any failure (403 anonymous, network error, ...):
    // this is a best-effort background rehydration, not a user-facing
    // action — the operator sees nothing missing beyond what they'd have
    // seen anyway if this call didn't exist.
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

  // ── Continuation after an out-of-band resolution (#444 / ADR-0066) ───────
  // A capture or approval resolving elsewhere leaves a console note in the
  // conversation, and nothing runs the model — so the assistant never finishes
  // what it just said it would do. When a note is unanswered we send the
  // continuation the operator would otherwise have to ask for by hand.
  //
  // No user bubble is rendered: the operator typed nothing, and inventing a
  // message they never sent is the defect this avoids, not a cosmetic detail.
  // The turn is gated exactly like a typed one, so anything risky raises a
  // fresh card rather than running.
  var resumeInFlight = false;
  function maybeResumeConversation() {
    if (resumeInFlight) return;
    return fetch("/api/chat/resume-due", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.due || !data.conversation_id) return;
        if (resumeInFlight) return;
        resumeInFlight = true;
        if (emptyState) emptyState.style.display = "none";
        var assistantBubble = renderAssistantBubble();
        sendBtn.disabled = true;
        sendBtn.classList.add("disabled");
        // Sent with the model the operator picked: the turn this continues ran
        // on it. A continuation that silently changed models is how a job typed
        // on one model finished on the default, with a fabricated approval link.
        var modelEl = document.getElementById("model");
        return fetch("/api/chat/resume", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversation_id: data.conversation_id,
            model: modelEl ? modelEl.value : undefined,
          }),
        })
          .then(function (resp) {
            if (!resp.ok) {
              // 409: another tab answered it first, or it stopped being due
              // between the check and the post. A normal race — drop the
              // empty bubble rather than showing the operator an error.
              assistantBubble.remove();
              return;
            }
            return consumeSse(resp.body, assistantBubble);
          })
          .catch(function (err) { renderError(assistantBubble, String(err)); })
          .finally(function () {
            resumeInFlight = false;
            sendBtn.disabled = false;
            sendBtn.classList.remove("disabled");
            resolveAllPending(assistantBubble);
            removeTyping(assistantBubble);
            // The continuation's tools may have resolved a notice.
            loadNotices(true);
          });
      })
      .catch(function () {});
  }

  // ── Needs attention (ADR-0071) ────────────────────────────────────────────
  // Open notices are fleet-level: they live outside the transcript, so a
  // conversation switch never clears them (resetTranscript() leaves this
  // widget alone). "Review in chat" writes a console note server-side, and
  // the continuation above answers it once, as the operator. Every string
  // from the server is set with textContent — device names are data.
  var noticesBox = document.getElementById("chat-notices");
  var noticesList = document.getElementById("chat-notices-list");
  var noticesMore = document.getElementById("chat-notices-more");
  var noticesCount = document.getElementById("chat-notices-count");
  var NOTICE_ROWS = 3;
  var NOTICE_BATCH = 20;
  var NOTICE_THROTTLE_MS = 15000;
  var noticesLoadedAt = 0;
  var noticesExpanded = false;
  var openNotices = [];
  var openNoticeTotal = 0;

  function loadNotices(force) {
    if (!noticesBox) return Promise.resolve();
    var now = Date.now();
    if (!force && now - noticesLoadedAt < NOTICE_THROTTLE_MS) return Promise.resolve();
    noticesLoadedAt = now;
    return fetch("/api/notices?status=open&limit=50", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        openNotices = data.notices || [];
        openNoticeTotal = data.open_count || openNotices.length;
        renderNotices();
      })
      .catch(function () {});
  }

  function noticeAge(epochSeconds) {
    if (!epochSeconds) return "";
    return relTime(new Date(epochSeconds * 1000).toISOString());
  }

  function renderNoticeRow(n) {
    var row = document.createElement("div");
    row.className = "pending-row notice-row";
    row.dataset.noticeId = String(n.id);
    var isDrift = n.kind === "drift";
    var tone = n.severity === "high" ? "fg-red" : (n.severity === "low" ? "fg-blue" : "fg-amber");
    row.innerHTML =
      '<span class="pr-ico ' + tone + '">' + ico(isDrift ? "git-compare" : "bell-ring") + "</span>" +
      '<div style="min-width:0"><div class="pr-op"></div><div class="pr-target"></div></div>' +
      '<div class="pr-right">' +
      '<button type="button" class="btn accent sm notice-review">' + ico("message-square-text") + "Review in chat</button>" +
      '<button type="button" class="btn sm ghost notice-snooze" title="Hide for 4 hours">' + ico("alarm-clock") + "Snooze</button>" +
      '<button type="button" class="icon-btn xs notice-dismiss" title="Dismiss" aria-label="Dismiss notice">' + ico("x") + "</button>" +
      "</div>";
    var summary = n.summary || {};
    var op;
    if (isDrift) {
      var fields = Number(summary.fields || 0);
      op = "Drift on " + n.device_id + " · " + fields + (fields === 1 ? " field" : " fields");
    } else {
      op = (n.title || "Event detected") + (n.occurrences > 1 ? " · ×" + n.occurrences : "");
    }
    row.querySelector(".pr-op").textContent = op;
    var device = n.device || {};
    var bits = [];
    if (device.model) bits.push(device.model);
    if (device.nickname) bits.push(device.nickname);
    if (device.host) bits.push(device.host);
    if (!isDrift && n.device_id) bits.push(n.device_id);
    var age = noticeAge(n.created_at);
    if (age) bits.push(age);
    if (n.reviewed_at) bits.push("reviewed " + noticeAge(n.reviewed_at));
    row.querySelector(".pr-target").textContent = bits.join(" · ");
    row.querySelector(".notice-review").addEventListener("click", function () { reviewNotices([n.id]); });
    row.querySelector(".notice-snooze").addEventListener("click", function () { snoozeNotice(n.id, 4); });
    row.querySelector(".notice-dismiss").addEventListener("click", function () { dismissNotice(n.id); });
    return row;
  }

  function renderNotices() {
    if (!noticesBox || !noticesList) return;
    noticesList.innerHTML = "";
    if (!openNotices.length) {
      noticesBox.style.display = "none";
      return;
    }
    var shown = noticesExpanded ? openNotices : openNotices.slice(0, NOTICE_ROWS);
    shown.forEach(function (n) { noticesList.appendChild(renderNoticeRow(n)); });
    if (noticesCount) noticesCount.textContent = openNoticeTotal + " open";
    if (noticesMore) {
      noticesMore.innerHTML = "";
      if (openNoticeTotal > NOTICE_ROWS) {
        var label = document.createElement("div");
        label.className = "pr-op";
        var hidden = openNoticeTotal - shown.length;
        label.textContent = hidden > 0 ? hidden + " more need attention" : "All open notices";
        var right = document.createElement("div");
        right.className = "pr-right";
        var toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "btn sm ghost";
        toggle.textContent = noticesExpanded ? "Show fewer" : "Show all";
        toggle.addEventListener("click", function () {
          noticesExpanded = !noticesExpanded;
          renderNotices();
        });
        var all = document.createElement("button");
        all.type = "button";
        all.className = "btn accent sm";
        all.textContent = "Review all";
        all.addEventListener("click", function () {
          reviewNotices(openNotices.slice(0, NOTICE_BATCH).map(function (n) { return n.id; }));
        });
        right.appendChild(toggle);
        right.appendChild(all);
        noticesMore.appendChild(label);
        noticesMore.appendChild(right);
        noticesMore.style.display = "";
      } else {
        noticesMore.style.display = "none";
      }
    }
    noticesBox.style.display = "";
    icons();
  }

  function noticeFlash(message) {
    if (!noticesCount) return;
    noticesCount.textContent = message;
    setTimeout(function () { loadNotices(true); }, 4000);
  }

  function postNotice(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body || {}),
    }).then(function (r) {
      return r.json()
        .catch(function () { return {}; })
        .then(function (b) { return { ok: r.ok, status: r.status, body: b }; });
    });
  }

  function reviewNotices(ids) {
    if (!ids || !ids.length) return Promise.resolve();
    // One reply at a time: a second stream into the transcript would interleave.
    if (resumeInFlight || sendBtn.disabled) {
      noticeFlash("Wait for the current reply to finish");
      return Promise.resolve();
    }
    var url = ids.length === 1
      ? "/api/notices/" + encodeURIComponent(ids[0]) + "/review"
      : "/api/notices/review";
    return postNotice(url, ids.length === 1 ? {} : { ids: ids })
      .then(function (resp) {
        if (!resp.ok) {
          var why = (resp.body && resp.body.detail) || ("HTTP " + resp.status);
          noticeFlash(why === "continuation_in_flight"
            ? "A reply is still running — try again shortly"
            : (why === "not_open" ? "Already handled" : "Could not open it"));
          return;
        }
        var result = resp.body || {};
        if (result.created) {
          // A new conversation was made active: show it, then answer the note.
          return Promise.resolve(openConversation(result.conversation_id))
            .then(maybeResumeConversation);
        }
        if (emptyState) emptyState.style.display = "none";
        replayMessage("event", result.note || "");
        transcript.scrollIntoView(false);
        return maybeResumeConversation();
      })
      .catch(function () {})
      .finally(function () { loadNotices(true); });
  }

  function dismissNotice(id) {
    return postNotice("/api/notices/" + encodeURIComponent(id) + "/dismiss", {})
      .catch(function () {})
      .finally(function () { loadNotices(true); });
  }

  function snoozeNotice(id, hours) {
    return postNotice("/api/notices/" + encodeURIComponent(id) + "/snooze", { hours: hours })
      .catch(function () {})
      .finally(function () { loadNotices(true); });
  }

  // /chat?review_notice=<id> — the Tasks page's "Review in chat" link.
  function reviewFromLink() {
    var params;
    try { params = new URLSearchParams(window.location.search); } catch (e) { return; }
    var id = params.get("review_notice");
    if (!id || !/^[0-9]+$/.test(id)) return;
    params.delete("review_notice");
    var rest = params.toString();
    try {
      window.history.replaceState(
        null, "", window.location.pathname + (rest ? "?" + rest : "") + window.location.hash);
    } catch (e) { /* the link still works; it just stays in the address bar */ }
    return reviewNotices([Number(id)]);
  }

  // The capture form opens in a SECOND tab, so this chat tab may never reload
  // and would otherwise never learn the note landed. Refocus is the moment the
  // operator comes back to look.
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") {
      maybeResumeConversation();
      loadNotices(false);
    }
  });

  // Resume the active conversation on Console load (display-only).
  // CHAINED, not parallel: restoreActiveConversation() bails when the
  // transcript is already non-empty, so appending a continuation bubble first
  // would abort the history restore on exactly the load that matters. A fast
  // localhost load hides this; a real one does not. A review deep link waits
  // for both, for the same reason.
  Promise.resolve(restoreActiveConversation())
    .then(maybeResumeConversation)
    .then(reviewFromLink);
  rehydratePendingActions();
  loadNotices(true);
})();
