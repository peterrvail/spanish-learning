# Spanish Learning System

A modular, B1→B2 Spanish immersion environment built for rapid drills, conversational fluency, and grammar mastery.

## Quick Start

### 1. Install Dependencies

```bash
cd /Users/petervail/Documents/Spanish
pip install -r requirements.txt
```

### 2. Launch the Streamlit App

```bash
streamlit run app/spanish_drill.py
```

The app will open at `http://localhost:8501/`.

### 2b. Access from Your iPhone

To use the app on your iPhone while your Mac runs the server:

```bash
./run_mobile.sh
```

This starts Streamlit bound to your local network instead of just `localhost`, and prints a URL like:

```
http://192.168.1.240:8501
```

**Requirements:**
- Your iPhone and Mac must be on the **same Wi-Fi network**
- macOS may show a firewall prompt the first time — click **Allow** (System Settings → Network → Firewall if you missed it)
- Open the printed URL in **Safari** on your iPhone
- Keep the Mac terminal window open and the Mac awake while using it from your phone
- Your Mac's IP can change if you reconnect to Wi-Fi — rerun `./run_mobile.sh` to get the current one, or check manually with `ipconfig getifaddr en0`

**Tip:** Add the page to your iPhone Home Screen (Share → Add to Home Screen) for an app-like icon and fullscreen view without Safari's address bar.

### 3. Run Your First Drill

In the sidebar, enter:
```
!drill imperativo
```

This launches a 5-minute imperative conjugation drill with 20 randomized questions.

---

## System Architecture

```
Spanish/
├── data/
│   ├── grammar/          # Syntax rules, clitic laws, relative pronouns
│   ├── verbs/            # Conjugation paradigms, mood triggers
│   │   └── verbs.json    # Master verb database (imperative focus)
│   ├── vocabulary/       # Thematic lexical sets
│   ├── scenarios/        # Situational dialogues & roleplay cards
│   ├── expressions/      # Idioms, discourse markers
│   ├── readings/         # Annotated short stories
│   └── speaking/         # Oral prompts, discussion topics
├── reference/
│   └── SCHEMAS.md        # Canonical JSON schemas for all data modules
├── app/
│   └── spanish_drill.py  # Streamlit interface & drill runner
└── README.md             # This file
```

---

## Commands Reference

### Drills

- `!drill imperativo` — 5-min imperative conjugation drill (tú, usted, nosotros, ustedes; affirmative + negative)
- `!drill pronombres` — Double object pronoun mechanics (coming soon)
- `!drill aspecto` — Preterite vs. Imperfect (coming soon)

### Immersion Modes

- `!hablar` — Conversational partner mode (100% Spanish, 2–4 sentence turns)
- `!rol [tema]` — Launch a roleplay scenario with persona and objective

### Control

- `!pausa` — Step out of immersion to explain a rule in English
- `!resumen` — End-of-session diagnostic (patterns practiced, mistakes, new vocabulary)

---

## Data Ingestion Workflow

### Submit Raw Materials

Have lesson screenshots, homework assignments, or notes you want to convert into structured data?

**Step 1:** Collect your materials (images, text files, PDFs)

**Step 2:** Use the ingestion template at `INGESTION.md` to describe what you're submitting

**Step 3:** Paste or upload the raw content

**Example:**

```json
{
  "source": "homework_assignment_imperatives_20260815.txt",
  "content_type": "verbs",
  "raw_data": "Conjugate the following in tú affirmative imperative:\n1. decir\n2. hacer\n3. ir\n...",
  "metadata": {
    "topic": "irregular imperatives",
    "difficulty": "B1",
    "extracted_date": "2026-08-16"
  }
}
```

**Step 4:** I parse and extract structured JSON entries into the appropriate data modules

### Supported Data Types

- `verbs` → `data/verbs/verbs.json`
- `vocabulary` → `data/vocabulary/vocabulary.json`
- `grammar_rule` → `data/grammar/grammar_rules.json`
- `scenario` → `data/scenarios/scenarios.json`
- `expression` → `data/expressions/expressions.json`
- `reading` → `data/readings/readings.json`

See `reference/SCHEMAS.md` for the complete JSON schema reference.

---

## Feature Roadmap

### Current (Phase 1-3)

✅ Directory structure & base schemas  
✅ `data/verbs/` with 12 common irregular verbs  
✅ `!drill imperativo` runner  
🔄 Ingestion workflow for raw materials  

### Next (Phase 4)

- [ ] `data/vocabulary/` seeding from ingestion
- [ ] `data/grammar/` clitic rules & examples
- [ ] `!drill pronombres` for double-object pronoun mechanics
- [ ] Scenario card system for `!rol` command
- [ ] Expression & discourse marker database

### Future

- [ ] `!hablar` conversational partner with LLM
- [ ] `!drill aspecto` for Preterite vs. Imperfect
- [ ] Readings with comprehension questions
- [ ] Speaking module with dictation feedback
- [ ] Session analytics & spaced repetition scheduling

---

## Grammar Focus Areas

### Imperatives (Priority 1 ✅)

- Affirmative tú, usted, nosotros, ustedes
- Negative imperatives (subjunctive forms)
- Clitic attachment rules
- Common irregulars: decir → di, hacer → haz, ir → ve, ser → sé, tener → ten, venir → ven

### Pronoun Mechanics (Priority 2)

- Direct object pronouns: lo, la, los, las
- Indirect object pronouns: me, te, le, nos, os, les
- Double object order: indirect before direct
- Reflexive pronouns: me, te, se, nos, os, se
- Clitic positioning in infinitives & gerunds

### Aspect & Tense (Priority 3)

- Preterite vs. Imperfect in narrative
- Verbal periphrases: acabar de + inf., soler + inf., llevar + gerundio
- Subjunctive triggers (doubt, emotion, volition, etc.)

---

## Immersion Protocol

**Target Language**: 100% natural, idiomatic Spanish (B1/B2 level)

**Conversational Style**: Compact turns (2–4 sentences) to sustain interactive rhythm and real-time thinking.

**Error Correction**: When grammar or clitic errors occur in dialogue, append a concise footer:

```
💬 [Natural conversational response in Spanish]

📌 Ajuste rápido:
* Dijiste: "..."
* Corrección: "..." (Explanation of the rule.)
```

---

## File Descriptions

| File | Purpose |
|------|---------|
| `verbs.json` | Master conjugation database with imperative paradigms, irregularities, and example sentences |
| `SCHEMAS.md` | Canonical JSON schemas for all data modules; reference during ingestion |
| `spanish_drill.py` | Streamlit app; runs drills, roleplay, and immersion modes |
| `INGESTION.md` | Template & workflow for converting raw materials into structured data |

---

## Next Steps

1. **Run the first drill**: `streamlit run app/spanish_drill.py` → `!drill imperativo`
2. **Prepare ingestion materials**: Gather your lesson screenshots, homework, and notes
3. **Submit for parsing**: Use `INGESTION.md` to describe your raw materials
4. **Expand modules**: As we populate `vocabulary/`, `grammar/`, `scenarios/`, etc., more drills and modes unlock

---

## Questions or Issues?

- Check `reference/SCHEMAS.md` for data format questions
- Review `reference/CLITIC_RULES.md` (coming soon) for grammar deep dives
- Submit ingestion materials via `INGESTION.md`

¡Buena suerte! 🚀
