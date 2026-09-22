import assemblyai as aai

from config import ASSEMBLYAI_API_KEY


aai.settings.api_key = ASSEMBLYAI_API_KEY


def transcribe_audio(audio_file: str) -> str:
    """
    Convert an audio file into text using AssemblyAI.
    """

    transcriber = aai.Transcriber()

    transcript = transcriber.transcribe(audio_file)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(
            f"Transcription failed: {transcript.error}"
        )

    return transcript.text or ""