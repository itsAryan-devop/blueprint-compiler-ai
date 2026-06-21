"""
Phase 0 smoke test  --  prove we can actually talk to both LLM providers.

If this prints a reply from Gemini AND from Groq, three things are confirmed:
  1. the API keys in .env are valid,
  2. the libraries installed correctly,
  3. this machine can reach the providers over the internet.

This file is temporary Phase 0 scaffolding. The real, reusable provider
abstraction will live in /llm and arrives in Phase 1.
"""

import os

from dotenv import load_dotenv

# Read GEMINI_API_KEY / GROQ_API_KEY from the .env file into the environment.
load_dotenv()

# Try a few model names and keep the first that answers, so a single renamed or
# retired model can't break the check. gemini-2.5-flash is the model confirmed
# available on this free-tier key (gemini-2.0-flash returns a "limit: 0" quota
# error on free tier), so we try it first.
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
GROQ_MODELS = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]


def check_gemini() -> None:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("GEMINI: no GEMINI_API_KEY found in .env")
        return

    from google import genai

    client = genai.Client(api_key=key)
    for model in GEMINI_MODELS:
        try:
            reply = client.models.generate_content(
                model=model,
                contents="Reply with exactly these three words: Gemini is working.",
            )
            print(f"GEMINI [{model}]: {reply.text.strip()}")
            return
        except Exception as error:
            print(f"GEMINI [{model}] failed: {error}")
    print("GEMINI: every model failed -- check the key or the model names above.")


def check_groq() -> None:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        print("GROQ: no GROQ_API_KEY found in .env")
        return

    from groq import Groq

    client = Groq(api_key=key)
    for model in GROQ_MODELS:
        try:
            reply = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with exactly these three words: Groq is working.",
                    }
                ],
            )
            print(f"GROQ [{model}]: {reply.choices[0].message.content.strip()}")
            return
        except Exception as error:
            print(f"GROQ [{model}] failed: {error}")
    print("GROQ: every model failed -- check the key or the model names above.")


if __name__ == "__main__":
    print("--- Phase 0 smoke test ---")
    check_gemini()
    check_groq()
    print("--- done ---")
