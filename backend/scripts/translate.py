"""Offline AI translation of the English UI strings into 22 scheduled languages.
Output: /app/frontend/src/i18n/locales/<code>.json (AI-translated, pending professional review)."""
import asyncio, json, os, re, sys
from pathlib import Path
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
OUT = Path("/app/frontend/src/i18n/locales")
LANGS = {
    "hi": "Hindi (Devanagari)", "bn": "Bengali", "te": "Telugu", "mr": "Marathi", "ta": "Tamil",
    "ur": "Urdu (Nastaliq/Arabic script)", "gu": "Gujarati", "kn": "Kannada", "or": "Odia", "ml": "Malayalam",
    "pa": "Punjabi (Gurmukhi)", "as": "Assamese", "mai": "Maithili (Devanagari)", "sa": "Sanskrit (Devanagari)",
    "ks": "Kashmiri (Perso-Arabic script)", "kok": "Konkani (Devanagari)", "ne": "Nepali", "sd": "Sindhi (Perso-Arabic script)",
    "mni": "Manipuri / Meitei (Meitei Mayek script)", "brx": "Bodo (Devanagari)", "doi": "Dogri (Devanagari)", "sat": "Santali (Ol Chiki script)",
}
en = json.loads((OUT / "en.json").read_text())
items = list(en.items())
CHUNK = 110
FORCE = {"verify.docs_note"}  # keys whose English text changed


async def translate_chunk(code, lang, chunk):
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"tr-{code}-{chunk[0][0]}",
                   system_message="You are a professional software localiser for Indian languages. Reply ONLY with a JSON object.").with_model("openai", "gpt-5.4")
    prompt = (f"Translate the values of this JSON into {lang} for a carpooling mobile app called Travoo. "
              "Keep keys unchanged. Keep placeholders like {n}, {route} exactly. Keep 'Travoo', 'UPI', '112', '₹', emails unchanged. "
              "Use natural, simple everyday words in native script. Keep 'ENJOY YOUR RIDE.' translated naturally.\n"
              + json.dumps(dict(chunk), ensure_ascii=False))
    for attempt in range(3):
        try:
            text = await chat.send_message(UserMessage(text=prompt))
            m = re.search(r"\{.*\}", text, re.S)
            data = json.loads(m.group(0))
            return {k: data.get(k, v) for k, v in chunk}
        except Exception as e:  # retry on malformed output
            print(code, "retry", attempt, e, file=sys.stderr)
    return {}


async def translate(code, lang, sem):
    async with sem:
        target = OUT / f"{code}.json"
        existing = json.loads(target.read_text()) if target.exists() else {}
        todo = [(k, v) for k, v in items if k not in existing or k in FORCE]
        if not todo:
            return
        parts = await asyncio.gather(*[translate_chunk(code, lang, todo[i:i + CHUNK]) for i in range(0, len(todo), CHUNK)])
        merged = dict(existing)
        for p in parts:
            merged.update(p)
        target.write_text(json.dumps(merged, ensure_ascii=False, indent=1))
        print("done", code, len(merged))


async def main():
    sem = asyncio.Semaphore(6)
    codes = sys.argv[1:] or list(LANGS)
    await asyncio.gather(*[translate(c, LANGS[c], sem) for c in codes])

asyncio.run(main())
