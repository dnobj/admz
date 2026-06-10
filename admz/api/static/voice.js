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
  const transcript = document.getElementById("chat-transcript");
  const emptyEl = document.getElementById("chat-empty");

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
  let active = false;
  let userBubble = null,
    asstBubble = null;

  // Populate the voice-model dropdown from the server.
  if (modelSel) {
    fetch("/api/chat/voice/models")
      .then((r) => r.json())
      .then((d) => {
        modelSel.innerHTML = "";
        (d.models || []).forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m;
          opt.textContent = m.replace("gemini-", "").replace("-preview", "");
          if (m === d.default) opt.selected = true;
          modelSel.appendChild(opt);
        });
      })
      .catch(() => {});
  }

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
        setStatus("Listening — " + (m.model || "voice"), true);
        break;
      case "interrupted":
        // barge-in: stop the model's current audio immediately
        stopPlayback();
        asstBubble = null;
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
        appendAsst(m.text);
        break;
      case "tool_call":
        appendTool(m.name);
        break;
      case "turn_complete":
        userBubble = null;
        asstBubble = null;
        break;
      case "error":
        appendAsst("⚠ voice error: " + (m.error || "unknown"));
        break;
    }
  }

  async function start() {
    setStatus("Connecting…", true);
    activeSources = [];
    const model = modelSel && modelSel.value ? modelSel.value : "";
    const url = model ? WS_BASE + "?model=" + encodeURIComponent(model) : WS_BASE;
    ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    ws.onmessage = onMessage;
    ws.onclose = () => stop(true);
    ws.onerror = () => stop(true);
    await new Promise((res, rej) => {
      ws.onopen = res;
      ws.addEventListener("error", rej, { once: true });
    });

    // Playback context (model speaks at 24 kHz).
    playCtx = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: 24000,
    });
    playHead = playCtx.currentTime;

    // Mic capture context at 16 kHz (browser resamples the mic for us).
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    micCtx = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: 16000,
    });
    await micCtx.audioWorklet.addModule("/static/voice-worklet.js");
    const src = micCtx.createMediaStreamSource(micStream);
    micNode = new AudioWorkletNode(micCtx, "pcm-capture");
    micNode.port.onmessage = (e) => {
      if (ws && ws.readyState === 1) ws.send(e.data);
    };
    src.connect(micNode);
    // A muted sink keeps the worklet's process() pumping.
    micSink = micCtx.createGain();
    micSink.gain.value = 0;
    micNode.connect(micSink);
    micSink.connect(micCtx.destination);

    setStatus("Listening… (click mic to stop)", true);
  }

  function stop(fromClose) {
    setStatus("", false);
    stopPlayback();
    try {
      if (micStream) micStream.getTracks().forEach((t) => t.stop());
    } catch (e) {}
    try {
      if (micCtx) micCtx.close();
    } catch (e) {}
    try {
      if (playCtx) playCtx.close();
    } catch (e) {}
    if (!fromClose && ws && ws.readyState === 1) {
      try {
        ws.close();
      } catch (e) {}
    }
    ws = micCtx = playCtx = micNode = micStream = micSink = null;
    userBubble = asstBubble = null;
  }

  btn.addEventListener("click", async () => {
    if (active) {
      stop(false);
      return;
    }
    try {
      await start();
    } catch (e) {
      stop(true);
      setStatus("Voice unavailable: " + (e && e.message ? e.message : e), false);
    }
  });
})();
