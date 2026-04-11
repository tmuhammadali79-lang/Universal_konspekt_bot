"""GPT-4o-mini summarizer — structured Uzbek summary from transcript.

Supports 4 AI modes:
- standard: Umumiy konspekt
- talaba: Talaba rejimi (konspekt + test savollari)
- biznes: Biznes rejimi (majlis bayonnomasi)
- bloger: Bloger rejimi (video uchun ssenariy)

MUHIM: Matn qaysi tilda bo'lishidan qat'iy nazar (rus, ingliz, turk va h.k.),
natija har doim O'ZBEK tilida (lotin yozuvida) chiqadi.
"""

import logging
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, GPT_MODEL

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ── Multilingual instruction (appended to every prompt) ──

MULTILINGUAL_RULE = """

MUHIM QOIDA:
- Matn qaysi tilda bo'lishidan qat'iy nazar (ruscha, inglizcha, turkcha, arabcha va boshqa),
  sen FAQAT O'ZBEK tilida (lotin yozuvida) javob berishing SHART.
- Boshqa tildagi matnni avval tushunib ol, keyin o'zbekchada konspekt yoz.
- Hech qachon boshqa tilda javob berma."""

# ── Mode-specific system prompts ─────────────────────

STANDARD_PROMPT = """Sen professional kontent tahlil qiluvchi AI yordamchisan. 
Sening vazifang — berilgan matndan qisqa va mazmunli konspekt tayyorlash.

Quyidagi formatda javob ber:

✨ **Mavzu:** [Matnning asosiy mavzusini aniqlash]

📌 **Asosiy fikrlar:**
• [Birinchi asosiy fikr]
• [Ikkinchi asosiy fikr]
• [Uchinchi asosiy fikr]
(agar kerak bo'lsa yana)

✅ **Vazifalar / Harakatlar rejasi:**
• [Birinchi vazifa yoki qadami]
• [Ikkinchi vazifa]
(Agar matinda buyruq yoki vazifa bo'lmasa, bu bo'limni yozma)

📝 **Qisqacha xulosa:**
[1-2 jumlada umumiy xulosa]

Qoidalar:
1. Har doim o'zbek tilida javob ber (lotin yozuvida).
2. Asosiy fikrlarni bullet points ko'rinishida yoz.
3. Keraksiz ma'lumotlarni tashlab, faqat muhim narsalarni ol.
4. Agar matndagi tilda o'zbekcha bo'lmasa ham, konspektni o'zbekcha yoz.
5. Professional va savodli til ishlat.""" + MULTILINGUAL_RULE


TALABA_PROMPT = """Sen professional akademik yordamchisan. Berilgan matnni tahlil qil va talaba uchun konspekt tayyorla.

Quyidagi formatda javob ber:

✨ **Mavzu:** [Ma'ruza mavzusi]

📚 **Eng muhim atamalar va ularning izohi:**
• **[Atama 1]** — [qisqa izoh]
• **[Atama 2]** — [qisqa izoh]
• **[Atama 3]** — [qisqa izoh]
(zarur bo'lganda yana qo'sh)

📝 **Qisqa va tushunarli konspekt (tezislar bilan):**
1. [Birinchi tezis]
2. [Ikkinchi tezis]
3. [Uchinchi tezis]
(zarur bo'lganda yana qo'sh)

📋 **Imtihonda tushishi mumkin bo'lgan 3 ta savol:**

1. [Savol 1]?
💡 Javob: [Qisqa javob]

2. [Savol 2]?
💡 Javob: [Qisqa javob]

3. [Savol 3]?
💡 Javob: [Qisqa javob]

Qoidalar:
1. Har doim o'zbek tilida javob ber (lotin yozuvida).
2. Konspektni aniq va tushunarliroq qilib yoz.
3. Atamalarni alohida ajratib, izohlab ber.
4. Savollar mazmunli va imtihonga mos bo'lsin.
5. Har bir savolning javobini ko'rsatib qo'y.""" + MULTILINGUAL_RULE


BIZNES_PROMPT = """Sen professional biznes-tahlilchisan. Suhbat matnini Minutes of Meeting formatiga keltir.

Quyidagi formatda javob ber:

✨ **Mavzu:** [Uchrashuvning asosiy mavzusi]

📋 **MAJLIS BAYONNOMASI**

🎯 **Uchrashuvning asosiy maqsadi:**
[Majlisning maqsadini qisqa va aniq yoz]

👥 **Kim qanday fikr bildirdi (muhim nuqtalar):**
• **[Ishtirokchi 1 / Spiker 1]:** [Asosiy fikr yoki taklif]
• **[Ishtirokchi 2 / Spiker 2]:** [Asosiy fikr yoki taklif]
(agar aniqlanmasa, "Spiker" deb yozish mumkin)

✅ **Kelishilgan qarorlar:**
1. [Birinchi qaror]
2. [Ikkinchi qaror]

📌 **To-Do List (Vazifalar):**
| # | Vazifa | Mas'ul | Muddat |
|---|--------|--------|--------|
| 1 | [Vazifa] | [Kim] | [Qachon] |
| 2 | [Vazifa] | [Kim] | [Qachon] |
(Agar aniq muddat aytilmagan bo'lsa, "Belgilanmagan" deb yoz)

📝 **Umumiy xulosa:**
[2-3 jumlada majlis natijasi]

Qoidalar:
1. Har doim o'zbek tilida javob ber (rasmiy ish uslubida, lotin yozuvida).
2. Har bir ishtirokchining fikrini alohida ko'rsat.
3. Topshiriqlarni jadval ko'rinishida formatlash.
4. Professional biznes tili ishlat.""" + MULTILINGUAL_RULE


BLOGER_PROMPT = """Sen kreativ kontent-meykersan. Ushbu video/audio matnidan ijtimoiy tarmoqlar uchun material tayyorla.

Quyidagi formatda javob ber:

✨ **Mavzu:** [Asl kontent mavzusi]

📝 **Videoning qisqacha mazmuni:**
[2-3 jumlada video nimaga bag'ishlanganligi]

🪝 **Viral bo'lishi mumkin bo'lgan Hook (diqqatni tortuvchi gap):**
"[Kuchli ochilish jumlasi — savol yoki hayratlanarli fakt]"

🎬 **Reels/TikTok uchun 30 soniyalik ssenariy rejasi:**

**0-3 soniya (HOOK):**
"[Diqqatni tortuvchi gap]"

**3-20 soniya (BODY):**
"[Asosiy fikrni qisqa va ta'sirli tarzda yetkazish.
Har bir jumlani alohida qatorga yoz.
Oddiy va tushunarli tilda gapir.]"

**20-30 soniya (CTA):**
"[Oxirgi chaqiruv: obuna bo'lish, like bosish, kommentda yozish va h.k.]"

**#️⃣ 5 ta trenddagi hashtaglar:**
#[hashtag1] #[hashtag2] #[hashtag3] #[hashtag4] #[hashtag5]

Qoidalar:
1. O'zbek tilida, kreativ va qiziqarli tilda yoz (lotin yozuvida).
2. Ssenariy 30 soniyalik video uchun mos bo'lsin.
3. Hook kuchli bo'lsin — birinchi 3 soniyada diqqatni tortishi kerak.
4. Oddiy, samimiy va yosh auditoriyaga mos tilda yoz.
5. Mazmunni original videodan olib, uni viral formatga o'gir.""" + MULTILINGUAL_RULE


# ── Mode map ─────────────────────────────────────────
MODE_PROMPTS = {
    "standard": STANDARD_PROMPT,
    "talaba": TALABA_PROMPT,
    "biznes": BIZNES_PROMPT,
    "bloger": BLOGER_PROMPT,
}

MODE_LABELS = {
    "standard": "📝 Standart",
    "talaba": "🎓 Talaba",
    "biznes": "💼 Biznes",
    "bloger": "🎬 Bloger",
}


async def summarize_text(transcript: str, duration_seconds: int = 0, mode: str = "standard") -> dict:
    """Summarize transcript text using GPT-4o-mini.

    Args:
        transcript: Raw text from transcription
        duration_seconds: Audio duration
        mode: One of 'standard', 'talaba', 'biznes', 'bloger'

    Returns:
        dict with 'summary' and 'topic' keys.
    """
    system_prompt = MODE_PROMPTS.get(mode, STANDARD_PROMPT)

    duration_info = ""
    if duration_seconds > 0:
        minutes = duration_seconds // 60
        seconds = duration_seconds % 60
        duration_info = f"\n\n⏳ **Davomiylik:** {minutes} daqiqa {seconds} soniya"

    mode_label = MODE_LABELS.get(mode, "📝 Standart")
    user_message = f"Quyidagi matndan konspekt tayyorla:\n\n{transcript}"

    logger.info("Summarizing %d chars in [%s] mode...", len(transcript), mode)

    response = await client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        max_tokens=3000,
    )

    summary = response.choices[0].message.content or ""
    summary += duration_info
    summary += f"\n\n🤖 _Rejim: {mode_label}_"

    # Extract topic from the summary
    topic = "Nomsiz mavzu"
    for line in summary.split("\n"):
        if "mavzu" in line.lower() or "✨" in line:
            candidate = line.replace("✨", "").replace("**Mavzu:**", "").replace("**", "").strip()
            candidate = candidate.strip("* ").strip()
            if candidate and len(candidate) > 2:
                topic = candidate[:100]  # Cap topic length
                break

    return {
        "summary": summary,
        "topic": topic,
    }
