/**
 * PCM AudioWorklet for ORION browser voice.
 *
 * Captures microphone audio, resamples from the browser's
 * native rate (usually 48 kHz) to 16 kHz, converts to
 * PCM16, and posts 800-sample chunks to the main thread.
 */

class PCMProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();

    const opts = options?.processorOptions || {};

    this.sourceRate = opts.sourceRate || 48000;
    this.targetRate = opts.targetRate || 16000;
    this.ratio = this.sourceRate / this.targetRate;

    this.buffer = [];
    this.phase = 0;
    this.targetSamples = 800;

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

registerProcessor("pcm-processor", PCMProcessor);
