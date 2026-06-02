// ADMZ chat streaming client.
//
// Intercepts the chat form's submit, POSTs to /chat/stream, and reads
// the SSE response chunk-by-chunk. Renders three kinds of events:
//
//   - text         → appended to the assistant's message bubble
//   - tool_call    → a card "ADMZ is calling <name>"
//   - tool_result  → updates the previous card with status/summary
//   - done         → appends a token-usage footer
//   - error        → red error banner inside the transcript
//
// Falls back gracefully: if JS is disabled, the form posts to /chat
// (Phase 5A) and the server renders the full response.

(function () {
  "use strict";

  const form = document.getElementById("chat-form");
  const transcript = document.getElementById("chat-transcript");
  const sendBtn = document.getElementById("chat-send");

  if (!form || !transcript || !sendBtn) {
    return; // page may not be the chat page
  }

  // Bail out if the Send button is disabled (chatbot not configured).
  // Server-side render already shows the "not configured" banner.
  if (sendBtn.disabled) {
    return;
  }

  // Keyboard UX: Enter submits, Shift+Enter inserts a newline.
  // Matches the convention every modern chat UI follows. Alt+Enter
  // is treated as a newline too (some users have muscle memory for
  // it). Plain Enter triggers requestSubmit() which fires the
  // existing submit handler below, including its no-op return for
  // empty messages.
  const messageInput = document.getElementById("message");
  if (messageInput) {
    messageInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
        // Suppress the default newline insertion and submit instead.
        e.preventDefault();
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          // Older browsers — fall back to clicking the submit button,
          // which triggers the form's submit event.
          sendBtn.click();
        }
      }
      // Shift+Enter / Alt+Enter fall through to the textarea's
      // default behavior (insert a literal newline).
    });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    const messageEl = document.getElementById("message");
    const modelEl = document.getElementById("model");
    const message = messageEl.value.trim();
    if (!message) return;

    renderUserBubble(message);
    const assistantBubble = renderAssistantBubble();

    sendBtn.disabled = true;
    const originalLabel = sendBtn.textContent;
    sendBtn.textContent = "Sending…";

    const body = new URLSearchParams();
    body.set("message", message);
    body.set("model", modelEl.value);

    fetch("/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    })
      .then(function (resp) {
        if (!resp.ok) {
          renderError(assistantBubble, "HTTP " + resp.status);
          return;
        }
        return consumeSse(resp.body, assistantBubble);
      })
      .catch(function (err) {
        renderError(assistantBubble, String(err));
      })
      .finally(function () {
        sendBtn.disabled = false;
        sendBtn.textContent = originalLabel;
        messageEl.value = "";
        messageEl.focus();
      });
  });

  // ---------------------------------------------------------------------
  // SSE consumer
  // ---------------------------------------------------------------------

  async function consumeSse(stream, assistantBubble) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    // Tracks the last-emitted tool-call card so tool_result can update it.
    let lastToolCard = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by blank lines.
      let sep;
      while ((sep = buffer.indexOf("\n\n")) >= 0) {
        const raw = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);

        const parsed = parseSseEvent(raw);
        if (!parsed) continue;

        switch (parsed.event) {
          case "start":
            // First event of the stream — no UI change beyond the
            // already-rendered empty assistant bubble.
            break;
          case "text":
            appendText(assistantBubble, parsed.data.chunk || "");
            break;
          case "tool_call":
            lastToolCard = renderToolCard(parsed.data);
            break;
          case "tool_result":
            updateToolCard(lastToolCard, parsed.data);
            // tool_result payloads from capture_credentials /
            // confirm-emitting tools may carry the URL in a structured
            // field. Scan the serialized payload so we don't miss a
            // token that the assistant hasn't yet echoed in its prose.
            try {
              const serialized = JSON.stringify(parsed.data || {});
              scanForTokens(serialized, CONFIRM_URL_RE, "confirm");
              scanForTokens(serialized, CAPTURE_URL_RE, "capture");
            } catch (_) { /* ignore */ }
            break;
          case "done":
            renderUsageFooter(assistantBubble, parsed.data);
            break;
          case "error":
            renderError(assistantBubble, parsed.data.message);
            break;
        }
      }
    }
  }

  function parseSseEvent(raw) {
    // raw looks like: "event: text\ndata: {...}"
    let event = "message";
    let data = "";
    for (const line of raw.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data = line.slice(5).trim();
    }
    if (!data) return null;
    try {
      return { event: event, data: JSON.parse(data) };
    } catch (_) {
      return null;
    }
  }

  // ---------------------------------------------------------------------
  // Rendering
  // ---------------------------------------------------------------------

  function renderUserBubble(text) {
    const div = document.createElement("div");
    div.style.cssText =
      "background:#eff6ff;border:1px solid #bfdbfe;padding:12px;" +
      "border-radius:6px;margin-bottom:8px;";
    div.innerHTML =
      '<div style="font-size:12px;font-weight:600;color:#1e40af;margin-bottom:4px;">You</div>' +
      '<div style="white-space:pre-wrap;color:#1e3a8a;"></div>';
    div.querySelector("div:last-child").textContent = text;
    transcript.appendChild(div);
  }

  function renderAssistantBubble() {
    const div = document.createElement("div");
    div.style.cssText =
      "background:#f0fdf4;border:1px solid #86efac;padding:12px;" +
      "border-radius:6px;margin-bottom:16px;";
    div.innerHTML =
      '<div style="font-size:12px;font-weight:600;color:#166534;margin-bottom:4px;">ADMZ</div>' +
      '<div class="chat-text" style="white-space:pre-wrap;color:#14532d;"></div>' +
      '<div class="chat-footer" style="font-size:11px;color:#65a30d;margin-top:8px;"></div>';
    transcript.appendChild(div);
    return div;
  }

  // Token format: secrets.token_urlsafe(32) → base64url, 43 chars.
  // Match /confirm/{token} or /capture/{token} anywhere in text. The
  // token alphabet (a-z A-Z 0-9 - _) excludes everything outside
  // that, so the boundary character class catches the end naturally.
  const CONFIRM_URL_RE = /\/confirm\/([A-Za-z0-9_-]{20,})/g;
  const CAPTURE_URL_RE = /\/capture\/([A-Za-z0-9_-]{20,})/g;
  const seenTokens = new Set();

  function appendText(bubble, chunk) {
    const textEl = bubble.querySelector(".chat-text");
    textEl.textContent += chunk;
    // After accumulating, scan the WHOLE assistant text for new
    // confirmation / capture URLs. Scanning the buffer rather than
    // each chunk is robust to token URLs that arrive split across
    // chunk boundaries.
    const buffer = textEl.textContent;
    scanForTokens(buffer, CONFIRM_URL_RE, "confirm");
    scanForTokens(buffer, CAPTURE_URL_RE, "capture");
  }

  function scanForTokens(buffer, re, kind) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(buffer)) !== null) {
      const token = m[1];
      const key = kind + ":" + token;
      if (seenTokens.has(key)) continue;
      seenTokens.add(key);
      if (kind === "confirm") {
        renderApprovalCard(token);
        addPinnedAction("confirm", token);
      } else if (kind === "capture") {
        renderCaptureCard(token);
        addPinnedAction("capture", token);
      }
    }
  }

  // ---------------------------------------------------------------------
  // Inline approval cards (Phase 5C)
  // ---------------------------------------------------------------------
  //
  // When the assistant emits a "/confirm/{token}" URL, we insert an
  // approval card after the latest assistant bubble. The card fetches
  // session details from /api/chat/confirm/{token}, renders an
  // appropriate UI (with or without password field), and POSTs the
  // approval inline — no separate browser tab.

  function renderApprovalCard(token) {
    const card = document.createElement("div");
    card.style.cssText =
      "background:#fff7ed;border:1px solid #fdba74;padding:12px;" +
      "border-radius:6px;margin:8px 0;color:#7c2d12;";
    card.innerHTML =
      '<div style="font-size:12px;font-weight:600;color:#9a3412;margin-bottom:4px;">Approval required</div>' +
      '<div class="approval-body" style="font-size:13px;">Loading…</div>';
    transcript.appendChild(card);

    fetch("/api/chat/confirm/" + encodeURIComponent(token))
      .then(function (r) {
        return r.json().then(function (body) {
          return { ok: r.ok, body: body };
        });
      })
      .then(function (resp) {
        if (!resp.ok || !resp.body) {
          renderApprovalDone(
            card,
            "error",
            resp.body && resp.body.status === "expired_or_not_found"
              ? "This confirmation link has expired."
              : "Could not load confirmation details."
          );
          return;
        }
        if (resp.body.status === "completed") {
          renderApprovalDone(card, "ok", "Already approved.");
          return;
        }
        populateApprovalForm(card, token, resp.body);
      })
      .catch(function (err) {
        renderApprovalDone(card, "error", String(err));
      });
  }

  function populateApprovalForm(card, token, details) {
    const body = card.querySelector(".approval-body");
    const riskLabel = details.risk_level
      ? '<span style="display:inline-block;padding:1px 8px;border-radius:3px;' +
        'background:#fecaca;color:#991b1b;font-size:11px;font-weight:600;' +
        'text-transform:uppercase;margin-left:6px;">' +
        details.risk_level +
        "</span>"
      : "";

    const opLine =
      "<div style=\"margin-bottom:6px;\"><strong>" +
      escapeHtml(details.operation_id || "operation") +
      "</strong>" +
      riskLabel +
      "</div>";

    const deviceLine = details.device_id
      ? '<div style="font-size:12px;color:#9a3412;margin-bottom:6px;">on <code>' +
        escapeHtml(details.device_id) +
        "</code></div>"
      : "";

    const dangerLine = details.danger_description
      ? '<div style="font-size:12px;background:#fffbeb;padding:6px 8px;border-radius:4px;margin-bottom:8px;color:#78350f;">' +
        escapeHtml(details.danger_description) +
        "</div>"
      : "";

    const passwordRow = details.needs_password
      ? '<div style="margin-bottom:8px;">' +
        '<label for="pw-' +
        token +
        '" style="display:block;font-size:12px;color:#7c2d12;margin-bottom:2px;">' +
        "Confirmation password</label>" +
        '<input id="pw-' +
        token +
        '" type="password" autocomplete="off" ' +
        'style="width:100%;padding:6px;border:1px solid #fdba74;border-radius:4px;font-size:13px;">' +
        "</div>"
      : "";

    body.innerHTML =
      opLine +
      deviceLine +
      dangerLine +
      passwordRow +
      '<div style="display:flex;gap:8px;">' +
      '<button class="approve-btn" style="padding:6px 14px;background:#dc2626;color:white;border:none;border-radius:4px;font-size:13px;font-weight:600;cursor:pointer;">Approve</button>' +
      '<button class="deny-btn" style="padding:6px 14px;background:transparent;color:#7c2d12;border:1px solid #fdba74;border-radius:4px;font-size:13px;cursor:pointer;">Dismiss</button>' +
      "</div>" +
      '<div class="approval-error" style="font-size:12px;color:#991b1b;margin-top:6px;display:none;"></div>';

    body.querySelector(".approve-btn").addEventListener("click", function () {
      submitApproval(card, token, details.needs_password);
    });
    body.querySelector(".deny-btn").addEventListener("click", function () {
      // Dismiss removes the card from the UI; the server-side session
      // stays pending until it expires (or until someone approves it
      // through the URL). Same semantics as closing the browser tab.
      card.remove();
    });
  }

  function submitApproval(card, token, needsPassword) {
    const body = card.querySelector(".approval-body");
    const errorEl = body.querySelector(".approval-error");
    const approveBtn = body.querySelector(".approve-btn");

    const params = new URLSearchParams();
    if (needsPassword) {
      const pwInput = body.querySelector("#pw-" + token);
      const pw = pwInput ? pwInput.value : "";
      if (!pw) {
        showApprovalError(errorEl, "Password required.");
        return;
      }
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
      .then(function (r) {
        return r.json().then(function (body) {
          return { ok: r.ok, status: r.status, body: body };
        });
      })
      .then(function (resp) {
        if (resp.ok && resp.body && resp.body.status === "completed") {
          renderApprovalDone(card, "ok", "Approved.");
          return;
        }
        // Failure paths return a body with status + error.
        const msg =
          (resp.body && (resp.body.error || resp.body.status)) ||
          ("HTTP " + resp.status);
        // Re-enable Approve unless the session is gone for good.
        const terminal =
          resp.body &&
          (resp.body.status === "expired_or_not_found" ||
            resp.body.status === "locked");
        if (terminal) {
          renderApprovalDone(card, "error", msg);
        } else {
          showApprovalError(errorEl, msg);
          approveBtn.disabled = false;
          approveBtn.textContent = "Approve";
        }
      })
      .catch(function (err) {
        showApprovalError(errorEl, String(err));
        approveBtn.disabled = false;
        approveBtn.textContent = "Approve";
      });
  }

  function showApprovalError(errorEl, msg) {
    if (!errorEl) return;
    errorEl.textContent = msg;
    errorEl.style.display = "block";
  }

  function renderApprovalDone(card, status, message) {
    const body = card.querySelector(".approval-body");
    const icon = status === "ok" ? "✓" : "✗";
    const color = status === "ok" ? "#166534" : "#991b1b";
    body.innerHTML =
      '<span style="color:' +
      color +
      ';font-weight:600;">' +
      icon +
      "</span> " +
      escapeHtml(message);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderToolCard(data) {
    // Inserted between user message and assistant bubble.
    const card = document.createElement("div");
    card.style.cssText =
      "background:#f5f3ff;border:1px solid #c4b5fd;padding:8px 12px;" +
      "border-radius:6px;margin:4px 0;font-size:13px;color:#4c1d95;";
    card.innerHTML =
      '<span class="tool-status">⏳</span> ' +
      '<strong class="tool-name"></strong> ' +
      '<span class="tool-summary" style="color:#6d28d9;"></span>';
    card.querySelector(".tool-name").textContent = data.name || "tool";
    card.querySelector(".tool-summary").textContent = data.summary || "";
    transcript.appendChild(card);
    return card;
  }

  function updateToolCard(card, data) {
    if (!card) return;
    const statusEl = card.querySelector(".tool-status");
    if (statusEl) {
      statusEl.textContent =
        data.status === "ok"
          ? "✓"
          : data.status === "error"
          ? "✗"
          : "•";
    }
    if (data.summary) {
      card.querySelector(".tool-summary").textContent = data.summary;
    }
  }

  function renderUsageFooter(bubble, data) {
    if (!data) return;
    const footer = bubble.querySelector(".chat-footer");
    if (!footer) return;
    const parts = [];
    if (data.input_tokens != null) parts.push("in=" + data.input_tokens);
    if (data.output_tokens != null) parts.push("out=" + data.output_tokens);
    if (data.model) parts.push("model=" + data.model);
    if (data.cost_usd != null) {
      // Show cost to four decimals — typical turn is sub-cent.
      parts.push("≈$" + Number(data.cost_usd).toFixed(4));
    }
    if (parts.length) {
      footer.textContent = "tokens: " + parts.join(" · ");
    }
  }

  function renderError(bubble, message) {
    const err = document.createElement("div");
    err.style.cssText =
      "background:#fef2f2;border:1px solid #fca5a5;padding:8px 12px;" +
      "border-radius:6px;margin:4px 0;color:#991b1b;font-size:13px;";
    err.textContent = "Error: " + message;
    if (bubble && bubble.parentNode) {
      bubble.parentNode.insertBefore(err, bubble.nextSibling);
    } else {
      transcript.appendChild(err);
    }
  }

  // ---------------------------------------------------------------------
  // Inline capture cards (mirrors the /confirm/ inline approval pattern)
  // ---------------------------------------------------------------------
  //
  // The capture form itself is multi-step (credentials, optional batch
  // device selection, optional saved-account choices) and lives at
  // /capture/{token}.html — we don't try to render that whole form
  // inline. The card just surfaces enough info for the user to know
  // what's pending and a clear "Open form" button that opens the
  // actual capture page in a new tab.

  function renderCaptureCard(token) {
    const card = document.createElement("div");
    card.style.cssText =
      "background:#eff6ff;border:1px solid #93c5fd;padding:12px;" +
      "border-radius:6px;margin:8px 0;color:#1e3a8a;";
    card.dataset.captureToken = token;
    card.innerHTML =
      '<div style="font-size:12px;font-weight:600;color:#1e40af;margin-bottom:4px;">' +
      "Credential capture pending</div>" +
      '<div class="capture-body" style="font-size:13px;">Loading…</div>';
    transcript.appendChild(card);

    fetch("/api/capture/" + encodeURIComponent(token) + "/status")
      .then(function (r) {
        return r.json().then(function (body) {
          return { ok: r.ok, body: body };
        });
      })
      .then(function (resp) {
        if (!resp.ok || !resp.body) {
          renderCaptureDone(card, "error", "Could not load capture details.");
          return;
        }
        if (resp.body.status === "expired_or_not_found") {
          renderCaptureDone(card, "error", "This capture link has expired.");
          removePinnedAction("capture", token);
          return;
        }
        if (resp.body.status === "completed") {
          renderCaptureDone(card, "ok", "Credentials already captured.");
          removePinnedAction("capture", token);
          return;
        }
        populateCaptureCard(card, token, resp.body);
      })
      .catch(function (err) {
        renderCaptureDone(card, "error", String(err));
      });
  }

  function populateCaptureCard(card, token, details) {
    const body = card.querySelector(".capture-body");
    const deviceLine = details.device_id
      ? '<div style="margin-bottom:6px;">for <code>' +
        escapeHtml(details.device_id) +
        "</code>" +
        (details.account_id
          ? " · account <code>" + escapeHtml(details.account_id) + "</code>"
          : "") +
        "</div>"
      : "";

    body.innerHTML =
      deviceLine +
      '<div style="font-size:12px;color:#1e40af;margin-bottom:8px;">' +
      "Open the form in a new tab to enter credentials. The form " +
      "is single-use and tied to this token.</div>" +
      '<div style="display:flex;gap:8px;">' +
      '<a class="open-form-btn" href="/capture/' +
      encodeURIComponent(token) +
      '" target="_blank" rel="noopener" ' +
      'style="padding:6px 14px;background:#2563eb;color:white;text-decoration:none;border-radius:4px;font-size:13px;font-weight:600;">' +
      "Open capture form ↗</a>" +
      '<button class="dismiss-btn" style="padding:6px 14px;background:transparent;color:#1e3a8a;border:1px solid #93c5fd;border-radius:4px;font-size:13px;cursor:pointer;">Dismiss</button>' +
      "</div>";

    body.querySelector(".dismiss-btn").addEventListener("click", function () {
      card.remove();
      removePinnedAction("capture", token);
    });
  }

  function renderCaptureDone(card, kind, message) {
    const color = kind === "ok" ? "#166534" : "#991b1b";
    const bg = kind === "ok" ? "#f0fdf4" : "#fef2f2";
    card.style.background = bg;
    card.style.color = color;
    const body = card.querySelector(".capture-body");
    body.innerHTML = "";
    body.textContent = message;
  }

  // ---------------------------------------------------------------------
  // Pinned-action widget (above the chat input)
  // ---------------------------------------------------------------------
  //
  // Distinct from the transcript: lets the user see pending capture /
  // confirm tokens even after the conversation scrolls. The widget
  // mirrors the inline cards' lifecycle — adding when a URL is
  // detected, removing on dismiss/complete/expiry. The inline card
  // is still the canonical UI for *acting* on the token; the pinned
  // entry is a persistent signpost. For an external MCP client (no
  // chat.js), the URLs in the assistant's text are still the way to
  // reach the form — see chat.html's inline URLs in scrollback.

  const actionsContainer = document.getElementById("chat-actions");
  const actionsList = document.getElementById("chat-actions-list");
  const pinnedActions = new Map(); // key = "kind:token" → row element

  function actionKey(kind, token) {
    return kind + ":" + token;
  }

  function showActionsContainer() {
    if (actionsContainer) actionsContainer.style.display = "";
  }

  function hideActionsContainerIfEmpty() {
    if (actionsContainer && pinnedActions.size === 0) {
      actionsContainer.style.display = "none";
    }
  }

  function addPinnedAction(kind, token) {
    if (!actionsList) return;
    const key = actionKey(kind, token);
    if (pinnedActions.has(key)) return;

    const row = document.createElement("div");
    row.style.cssText =
      "display:flex;align-items:center;gap:8px;padding:6px 4px;" +
      "font-size:13px;color:#78350f;";

    const label = document.createElement("span");
    label.style.flex = "1";
    if (kind === "capture") {
      label.innerHTML =
        '<span style="font-weight:600;">📝 Capture credentials</span>';
    } else {
      label.innerHTML =
        '<span style="font-weight:600;">🚨 Approve dangerous op</span>';
    }
    row.appendChild(label);

    const action = document.createElement("a");
    action.href =
      kind === "capture"
        ? "/capture/" + encodeURIComponent(token)
        : "#card-confirm-" + token;
    if (kind === "capture") {
      action.target = "_blank";
      action.rel = "noopener";
      action.textContent = "Open form ↗";
    } else {
      action.textContent = "Jump to approval ↓";
      action.addEventListener("click", function (e) {
        // Find the inline approval card by walking the transcript;
        // the existing renderApprovalCard creates an .approval-body
        // child but no token ID on the wrapper, so we look for cards
        // whose fetch URL referenced this token. Cheaper: just scroll
        // to the bottom — the latest card is what the user wants.
        e.preventDefault();
        const cards = transcript.querySelectorAll(".approval-body");
        if (cards.length) {
          cards[cards.length - 1].scrollIntoView({
            behavior: "smooth",
            block: "center",
          });
        }
      });
    }
    action.style.cssText =
      "padding:4px 10px;background:#f59e0b;color:white;text-decoration:none;" +
      "border-radius:4px;font-size:12px;font-weight:600;";
    row.appendChild(action);

    const dismiss = document.createElement("button");
    dismiss.textContent = "✕";
    dismiss.title = "Dismiss";
    dismiss.style.cssText =
      "background:transparent;border:none;color:#92400e;font-size:14px;" +
      "cursor:pointer;padding:2px 6px;";
    dismiss.addEventListener("click", function () {
      removePinnedAction(kind, token);
    });
    row.appendChild(dismiss);

    actionsList.appendChild(row);
    pinnedActions.set(key, row);
    showActionsContainer();

    // Auto-clear after 5 min (token TTL). Belt + braces so the
    // widget can't get stale if the user never dismisses it and
    // never opens the form.
    setTimeout(function () {
      removePinnedAction(kind, token);
    }, 5 * 60 * 1000);
  }

  function removePinnedAction(kind, token) {
    const key = actionKey(kind, token);
    const row = pinnedActions.get(key);
    if (!row) return;
    row.remove();
    pinnedActions.delete(key);
    hideActionsContainerIfEmpty();
  }
})();
