# Quick Start: Launch Your Spanish Learning System

You've got everything set up. Here's how to get started immediately.

---

## 1. Install Dependencies (One-Time)

```bash
cd <your clone of this repo>
pip install -r requirements.txt
```

This installs:
- `streamlit>=1.46` — Web app framework
- `pyyaml` & `python-dateutil` — Data parsing
- `anthropic>=2.3.0` — Optional: in-app `!hablar` / `!rol` chat and Claude grading (needs an API key; drills work without it)

---

## 2. Launch the Streamlit App

```bash
streamlit run app/spanish_drill.py
```

A browser window opens at `http://localhost:8501/`. You'll see:
- The landing page with available commands
- A sidebar with quick-reference command list

---

## 3. Run Your First Drill

In the **sidebar command box**, type:

```
!drill imperativo
```

Press Enter. The app launches a **5-minute imperative conjugation drill** with:
- 20 randomized questions
- Affirmative & negative imperatives (tú, usted, nosotros, ustedes)
- Common irregular verbs: decir, hacer, ir, venir, tener, ser, salir, pedir
- Real-time feedback on each answer
- Accuracy score at the end

---

## 4. (Optional) Ingest Your Existing Lesson Materials

You have 100+ lesson screenshots and homework assignments in this directory. Let's convert them into structured data so they power new drills.

### Option A: Quick Single-File Ingestion

Pick one lesson screenshot or homework assignment. Send me:

```json
{
  "source": "Leccion 100 - Imperativo Nosotros.jpg",
  "content_type": "verbs",
  "raw_data": "[Describe or paste the content from the image]",
  "metadata": {
    "topic": "imperatives (nosotros form)",
    "difficulty": "B1",
    "extracted_date": "2026-08-16"
  }
}
```

I'll parse it and merge into `data/verbs/verbs.json`.

### Option B: Bulk Ingestion Workflow

Provide a list of lessons you want ingested (e.g., "All Leccion 100-110 imperatives, All pronoun lessons Leccion 84-86"). I'll:
1. Extract content from each screenshot
2. Parse into structured JSON
3. Merge into the appropriate modules
4. Report the results

**For now**, the `!drill imperativo` command uses the 12 core verbs. As we ingest your materials, more verbs, vocabulary, and scenarios unlock.

---

## 5. What's in the app

The full command list (every menu button, grouped by section) is in the **Commands Reference** of `README.md`.

- **Drills** — grammar, verb tense and vocabulary drills (`!drill <module>`), plus 🚀 Adelantado topics ahead of your lessons
- 🎲 **Mixto** — `!drill mixto` interleaves all topics
- 🔁 **Review queue** — `!drill fallos` (quiz) / `!repasar fallos` (read-through) for what you missed
- 🃏 **Flashcards** — `!tarjetas` from your lesson vocabulary
- 📈 **Progress** — `!progreso` for streak, accuracy and spaced-repetition boxes
- 🎧 **Language Transfer** — `!lt` tracker
- 🗣️ `!hablar` / 🎭 `!rol [tema]` — conversation and roleplay (in-app with an Anthropic API key)
- ⏸️ `!pausa` / 📋 `!resumen` — step out for an English explanation / end-of-session summary

---

## 6. System Architecture (What You Built)

```
Spanish/
├── README.md                     # Full system documentation
├── QUICKSTART.md                 # This file
├── INGESTION.md                  # How to ingest lesson materials
├── requirements.txt              # Python dependencies
├── app/
│   ├── spanish_drill.py          # Streamlit app: commands, drills, UI
│   └── ...                       # conversation, grading, flashcards, progress, external, pattern_modules
├── tests/                        # pytest suite
├── data/
│   ├── verbs/
│   │   └── verbs.json            # 12 core verbs (3 regular, 9 irregular)
│   ├── grammar/                  # One file per topic
│   ├── vocabulary/               # One file per theme
│   ├── reference/                # Complete lesson vocabulary (for !tarjetas)
│   ├── scenarios/                # !rol scenario cards
│   ├── expressions/
│   ├── exercises/
│   ├── external/                 # Language Transfer mapping
│   └── progress/                 # Local progress fallback (git-ignored); see README for the hosted database
└── reference/
    ├── SCHEMAS.md                # Canonical JSON schemas
    └── CLITIC_RULES.md           # Deep dive on clitic mechanics
```

---

## 7. Next Steps

### Immediate (Next 10 mins)

1. ✅ Run `pip install -r requirements.txt`
2. ✅ Launch `streamlit run app/spanish_drill.py`
3. ✅ Try `!drill imperativo`

### Short-term (Next Hour)

- Explore the landing page and other commands
- Pick 2–3 lesson screenshots and submit for ingestion
- Start your first drill and adjust difficulty/feedback as needed

### Medium-term (This Week)

- Ingest all Leccion 97–110 (imperatives, pronouns) materials
- Ingest pronoun lessons (Leccion 84–86)

### Long-term (Ongoing)

- Ingest all lesson materials systematically
- Build out vocabulary, grammar, and scenario data

---

## 8. Troubleshooting

### "Module not found" or "JSON decode error"

Make sure you're in the right directory:

```bash
cd <your clone of this repo>
```

And that `data/verbs/verbs.json` exists:

```bash
ls -la data/verbs/verbs.json
```

### Streamlit won't start

```bash
# Check Python version (runtime.txt pins 3.11; Streamlit 1.46+ is required)
python --version

# Reinstall streamlit
pip install --upgrade streamlit
```

### Want to stop the Streamlit server?

Press `Ctrl+C` in the terminal.

---

## 9. File Descriptions

| File/Folder | Purpose |
|-------------|---------|
| `spanish_drill.py` | Main app; handles commands, drills, and UI |
| `verbs.json` | Master verb database; seed data for `!drill imperativo` |
| `SCHEMAS.md` | JSON schema reference; used during ingestion |
| `CLITIC_RULES.md` | Grammar deep dive; reference for pronoun mechanics |
| `INGESTION.md` | Workflow for converting raw materials to structured data |

---

## 10. Got Questions?

- **How does the drill work?** See the **Commands Reference** section in `README.md`
- **How do I ingest lessons?** See `INGESTION.md` with detailed examples
- **Grammar rules?** Check `reference/CLITIC_RULES.md` for pronouns; schema reference in `reference/SCHEMAS.md`
- **Data format?** See `reference/SCHEMAS.md` for all JSON structures

---

## Ready?

```bash
cd <your clone of this repo>
pip install -r requirements.txt
streamlit run app/spanish_drill.py
```

Enter `!drill imperativo` in the sidebar. 

¡Vamos! 🚀
