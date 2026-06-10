// ADMZ voice capture worklet.
//
// Runs in the AudioWorklet thread of a 16 kHz AudioContext, so the Float32
// frames it receives are already at the rate Gemini Live wants. It converts
// each frame to 16-bit little-endian PCM and posts the raw bytes to the main
// thread, which forwards them over the WebSocket.
class PCMCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0] && input[0].length) {
      const ch = input[0]; // mono Float32Array
      const pcm = new Int16Array(ch.length);
      for (let i = 0; i < ch.length; i++) {
        const s = Math.max(-1, Math.min(1, ch[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      // Transfer the buffer (zero-copy) to the main thread.
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }
    return true; // keep the processor alive
  }
}

registerProcessor("pcm-capture", PCMCaptureProcessor);
