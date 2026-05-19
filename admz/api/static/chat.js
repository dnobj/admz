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

  function appendText(bubble, chunk) {
    const textEl = bubble.querySelector(".chat-text");
    textEl.textContent += chunk;
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
