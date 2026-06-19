// ADMZ realtime voice controller.
//
// Wires the mic button (#voice-toggle) to a WebSocket at /api/chat/voice:
//   - captures mic audio in a 16 kHz AudioContext + pcm-capture worklet,
//     sends raw 16-bit PCM frames as binary WS messages;
//   - plays the model's 24 kHz PCM audio frames via a scheduled queue;
//   - renders live input/output transcripts into the chat transcript.
//
// Voice mode always uses the native-audio model server-side regardless of the
// text-chat model selector. Tools run through the same gate as text chat.
(function () {
  "use strict";

  const btn = document.getElementById("voice-toggle");
  if (!btn) return;
  const statusEl = document.getElementById("voice-status");
  const modelSel = document.getElementById("voice-model");
  const voiceSel = document.getElementById("voice-name");
  const modeSel = document.getElementById("voice-mode");
  const sttSel = document.getElementById("stt-model");
  const transcript = document.getElementById("chat-transcript");
  const emptyEl = document.getElementById("chat-empty");

  function currentMode() {
    return modeSel && modeSel.value ? modeSel.value : "realtime";
  }

  const WS_BASE =
    (location.protocol === "https:" ? "wss://" : "ws://") +
    location.host +
    "/api/chat/voice";

  let ws = null;
  let micCtx = null,
    micStream = null,
    micNode = null,
    micSink = null;
  let playCtx = null,
    playHead = 0;
  let activeSources = []; // scheduled audio chunks, for barge-in interruption
  let dictateChunks = []; // accumulated PCM frames for one-shot dictation
  let active = false;
  let listeningLabel = "Listening…";
  let userBubble = null,
    asstBubble = null;

  // Populate the voice-model + voice-name dropdowns from the server.
  if (modelSel || voiceSel) {
    fetch("/api/chat/voice/models")
      .then((r) => r.json())
      .then((d) => {
        if (modelSel) {
          modelSel.innerHTML = "";
          (d.models || []).forEach((m) => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m.replace("gemini-", "").replace("-preview", "");
            if (m === d.default) opt.selected = true;
            modelSel.appendChild(opt);
          });
        }
        if (voiceSel) {
          voiceSel.innerHTML = "";
          (d.voices || []).forEach((v) => {
            const opt = document.createElement("option");
            opt.value = v;
            opt.textContent = v;
            if (v === d.default_voice) opt.selected = true;
            voiceSel.appendChild(opt);
          });
        }
        if (sttSel) {
          sttSel.innerHTML = "";
          (d.stt_models || []).forEach((m) => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m.replace("gemini-", "");
            if (m === d.default_stt_model) opt.selected = true;
            sttSel.appendChild(opt);
          });
        }
      })
      .catch(() => {});
  }

  // Show the dropdown rows relevant to the selected mode. (Toggle the
  // settings-popover row, falling back to the <select> for older markup.)
  function syncModeUI() {
    const dict = currentMode() === "dictate";
    const row = (el) => (el && el.closest(".cs-row")) || el;
    [modelSel, voiceSel].forEach((el) => { const r = row(el); if (r) r.style.display = dict ? "none" : ""; });
    const sr = row(sttSel); if (sr) sr.style.display = dict ? "" : "none";
  }
  if (modeSel) { modeSel.addEventListener("change", syncModeUI); syncModeUI(); }

  function setStatus(text, recording) {
    active = !!recording;
    btn.classList.toggle("recording", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
    if (statusEl) statusEl.textContent = text || "";
  }

  function ensureTranscriptVisible() {
    if (emptyEl) emptyEl.style.display = "none";
  }

  function bubble(kind) {
    ensureTranscriptVisible();
    const wrap = document.createElement("div");
    wrap.className = "turn voice-turn " + kind;
    const inner = document.createElement("div");
    inner.className = kind === "user" ? "user-bubble" : "assistant-text";
    const span = document.createElement("div");
    span.className = "vt-text";
    inner.appendChild(span);
    wrap.appendChild(inner);
    if (transcript) {
      transcript.appendChild(wrap);
      transcript.scrollIntoView({ block: "end" });
    }
    return span;
  }

  function appendUser(text) {
    if (!userBubble) userBubble = bubble("user");
    userBubble.textContent += text;
  }
  function appendAsst(text) {
    if (!asstBubble) asstBubble = bubble("assistant");
    asstBubble.textContent += text;
  }
  function appendTool(name) {
    const span = bubble("assistant");
    span.innerHTML = '<span class="vt-tool">↪ ' + name + "</span>";
    asstBubble = null; // start a fresh assistant bubble for the spoken reply
  }

  // ---- audio playback (24 kHz PCM) -------------------------------------
  function playPCM(arrayBuf) {
    if (!playCtx) return;
    const i16 = new Int16Array(arrayBuf);
    const f32 = new Float32Array(i16.length);
    for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 0x8000;
    const buf = playCtx.createBuffer(1, f32.length, 24000);
    buf.copyToChannel(f32, 0);
    const node = playCtx.createBufferSource();
    node.buffer = buf;
    node.connect(playCtx.destination);
    const t = Math.max(playHead, playCtx.currentTime + 0.02);
    node.start(t);
    playHead = t + buf.duration;
    activeSources.push(node);
    node.onended = () => {
      const i = activeSources.indexOf(node);
      if (i >= 0) activeSources.splice(i, 1);
    };
  }

  // Barge-in: the user interrupted, so drop everything still queued.
  function stopPlayback() {
    activeSources.forEach((n) => {
      try {
        n.onended = null;
        n.stop();
      } catch (e) {}
    });
    activeSources = [];
    if (playCtx) playHead = playCtx.currentTime;
  }

  function onMessage(ev) {
    if (ev.data instanceof ArrayBuffer) {
      playPCM(ev.data);
      return;
    }
    let m;
    try {
      m = JSON.parse(ev.data);
    } catch (e) {
      return;
    }
    switch (m.type) {
      case "ready":
        listeningLabel =
          "🎙 Listening — speak anytime · " +
          (m.model || "voice") +
          (m.voice ? " · " + m.voice : "");
        setStatus(listeningLabel, true);
        break;
      case "interrupted":
        // barge-in: stop the model's current audio immediately
        stopPlayback();
        asstBubble = null;
        setStatus(listeningLabel, true);
        break;
      case "input_transcript":
        // a new user phrase resets both bubbles
        if (asstBubble) {
          userBubble = null;
          asstBubble = null;
        }
        appendUser(m.text);
        break;
      case "output_transcript":
        setStatus("🔊 Speaking… (talk to interrupt)", true);
        appendAsst(m.text);
        break;
      case "tool_call":
        setStatus("⚙ " + m.name + "…", true);
        appendTool(m.name);
        break;
      case "tool_result":
        // A gated op came back blocked — render the same on-screen approval
        // card the text chat uses (instead of the model reading the URL aloud).
        if (m.blocked && m.confirm_token && window.admzRenderApprovalCard) {
          ensureTranscriptVisible();
          window.admzRenderApprovalCard(m.confirm_token);
          if (transcript) transcript.scrollIntoView({ block: "end" });
        }
        break;
      case "turn_complete":
        userBubble = null;
        asstBubble = null;
        setStatus(listeningLabel, true);
        break;
      case "error":
        appendAsst("⚠ voice error: " + (m.error || "unknown"));
        break;
    }
  }

  // Mic capture at 16 kHz; each PCM frame goes to onFrame (shared by both modes).
  async function setupMic(onFrame) {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    micCtx = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: 16000,
    });
    await micCtx.audioWorklet.addModule("/static/voice-worklet.js");
    const src = micCtx.createMediaStreamSource(micStream);
    micNode = new AudioWorkletNode(micCtx, "pcm-capture");
    micNode.port.onmessage = (e) => onFrame(e.data);
    src.connect(micNode);
    // A muted sink keeps the worklet's process() pumping.
    micSink = micCtx.createGain();
    micSink.gain.value = 0;
    micNode.connect(micSink);
    micSink.connect(micCtx.destination);
  }

  function teardownMic() {
    try { if (micStream) micStream.getTracks().forEach((t) => t.stop()); } catch (e) {}
    try { if (micCtx) micCtx.close(); } catch (e) {}
    micCtx = micNode = micStream = micSink = null;
  }

  // ---- realtime (Live API) --------------------------------------------
  async function start() {
    setStatus("Connecting…", true);
    activeSources = [];
    const params = new URLSearchParams();
    if (modelSel && modelSel.value) params.set("model", modelSel.value);
    if (voiceSel && voiceSel.value) params.set("voice", voiceSel.value);
    const qs = params.toString();
    ws = new WebSocket(qs ? WS_BASE + "?" + qs : WS_BASE);
    ws.binaryType = "arraybuffer";
    ws.onmessage = onMessage;
    ws.onclose = () => stop(true);
    ws.onerror = () => stop(true);
    await new Promise((res, rej) => {
      ws.onopen = res;
      ws.addEventListener("error", rej, { once: true });
    });
    playCtx = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: 24000,
    });
    playHead = playCtx.currentTime;
    await setupMic((data) => { if (ws && ws.readyState === 1) ws.send(data); });
    setStatus("Listening… (click mic to stop)", true);
  }

  function stop(fromClose) {
    setStatus("", false);
    stopPlayback();
    teardownMic();
    try { if (playCtx) playCtx.close(); } catch (e) {}
    if (!fromClose && ws && ws.readyState === 1) {
      try { ws.close(); } catch (e) {}
    }
    ws = playCtx = null;
    userBubble = asstBubble = null;
  }

  // ---- dictate (one-shot STT → text chat) -----------------------------
  async function startDictate() {
    dictateChunks = [];
    await setupMic((data) => { dictateChunks.push(new Int16Array(data)); });
    setStatus("🎙 Recording — click mic again to transcribe", true);
  }

  async function stopDictate() {
    teardownMic();
    setStatus("Transcribing…", false);
    let total = 0;
    dictateChunks.forEach((c) => (total += c.length));
    const merged = new Int16Array(total);
    let off = 0;
    dictateChunks.forEach((c) => { merged.set(c, off); off += c.length; });
    dictateChunks = [];
    if (total === 0) { setStatus("", false); return; }
    const model = sttSel && sttSel.value ? sttSel.value : "";
    const url =
      "/api/chat/voice/transcribe?rate=16000" +
      (model ? "&model=" + encodeURIComponent(model) : "");
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: merged.buffer,
      });
      const body = await resp.json();
      const text = (body && body.transcript) || "";
      setStatus("", false);
      if (!text) { setStatus("(no speech detected)", false); return; }
      // Hand the transcript to the normal text chat — tools + the approval
      // widget apply unchanged.
      const ta = document.getElementById("message");
      const form = document.getElementById("chat-form");
      if (ta) {
        ta.value = text;
        ta.dispatchEvent(new Event("input", { bubbles: true }));
      }
      if (form && form.requestSubmit) form.requestSubmit();
      else { const send = document.getElementById("chat-send"); if (send) send.click(); }
    } catch (e) {
      setStatus("Transcription failed: " + (e && e.message ? e.message : e), false);
    }
  }

  btn.addEventListener("click", async () => {
    if (currentMode() === "dictate") {
      if (active) { await stopDictate(); return; }
      try { await startDictate(); }
      catch (e) {
        setStatus("", false); teardownMic();
        setStatus("Mic unavailable: " + (e && e.message ? e.message : e), false);
      }
      return;
    }
    if (active) { stop(false); return; }
    try { await start(); }
    catch (e) {
      stop(true);
      setStatus("Voice unavailable: " + (e && e.message ? e.message : e), false);
    }
  });
})();
