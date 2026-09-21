import os

from dotenv import load_dotenv

load_dotenv()


ASSEMBLYAI_API_KEY = os.getenv(
    "ASSEMBLYAI_API_KEY"
)

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


print(
    "AssemblyAI API key loaded:",
    bool(ASSEMBLYAI_API_KEY)
)

print(
    "Groq API key loaded:",
    bool(GROQ_API_KEY)
)

print(
    "Groq model:",
    GROQ_MODEL
)