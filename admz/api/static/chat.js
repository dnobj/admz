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
  // Match /confirm/{token} anywhere in text. The token alphabet
  // (a-z A-Z 0-9 - _) excludes everything outside that, so the
  // boundary character class catches the end naturally.
  const CONFIRM_URL_RE = /\/confirm\/([A-Za-z0-9_-]{20,})/g;
  const seenTokens = new Set();

  function appendText(bubble, chunk) {
    const textEl = bubble.querySelector(".chat-text");
    textEl.textContent += chunk;
    // After accumulating, scan the WHOLE assistant text for new
    // confirmation URLs. Scanning the buffer rather than each
    // chunk is robust to token URLs that arrive split across
    // chunk boundaries.
    const buffer = textEl.textContent;
    let m;
    CONFIRM_URL_RE.lastIndex = 0;
    while ((m = CONFIRM_URL_RE.exec(buffer)) !== null) {
      const token = m[1];
      if (!seenTokens.has(token)) {
        seenTokens.add(token);
        renderApprovalCard(token);
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
})();
