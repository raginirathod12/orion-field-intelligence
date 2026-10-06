/**
 * PCM AudioWorklet — 24 kHz target rate.
 *
 * Captures mic audio, resamples to 24 kHz,
 * converts to PCM16, sends 1200-sample chunks (~50 ms).
 *
 * Used for the AssemblyAI Voice Agent API.
 */

class PCMProcessor24k extends AudioWorkletProcessor {
  constructor(options) {
    super();

    const opts = options?.processorOptions || {};
    this.sourceRate = opts.sourceRate || 48000;
    this.targetRate = opts.targetRate || 24000;
    this.ratio = this.sourceRate / this.targetRate;

    this.buffer = [];
    this.phase = 0;
    this.targetSamples = 2400; // ~100ms at 24kHz

    this.port.onmessage = (event) => {
      if (event.data?.type === "flush") {
        this.flush();
      }
    };
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channel = input[0];

    for (let i = 0; i < channel.length; i += 1) {
      this.phase += 1;

      if (this.phase >= this.ratio) {
        this.phase -= this.ratio;
        this.buffer.push(channel[i]);

        if (this.buffer.length >= this.targetSamples) {
          this.flush();
        }
      }
    }

    return true;
  }

  flush() {
    if (this.buffer.length === 0) return;

    const samples = this.buffer;
    this.buffer = [];

    const pcm16 = new Int16Array(samples.length);

    for (let i = 0; i < samples.length; i += 1) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
  }
}

registerProcessor("pcm-processor-24k", PCMProcessor24k);
