"""
Generate the demo video narration using Edge TTS.
"""

import asyncio
import edge_tts


NARRATION = """
Every AI tool you use today pretends to be right.
This one proves itself wrong.

Most system monitors tell you what's happening.
ORION tells you why. And when it's wrong, it says so.

ORION is not a chatbot. It is a real-time voice agent.
It reads live telemetry, identifies candidates, and fuses evidence.

You can interrupt ORION at any time. It stops instantly.

Not a guess. A measurement. Before and after.

ORION does not just find causes.
It tracks whether they still hold.
When the evidence changes, it changes its answer.

ORION also monitors continuously.
It investigates on its own. It logs everything it finds.

ORION. The AI that proves itself wrong.
"""


async def main():
    voice = "en-US-AriaNeural"  # or "en-US-JennyNeural" for warmer
    output = "demo_narration.mp3"
    communicate = edge_tts.Communicate(NARRATION, voice)
    await communicate.save(output)
    print(f"Saved: {output}")


if __name__ == "__main__":
    asyncio.run(main())