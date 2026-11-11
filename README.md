# Spanish Learning System

A modular, B1→B2 Spanish immersion environment built for rapid drills, conversational fluency, and grammar mastery.

## Quick Start

### 1. Install Dependencies

```bash
cd <your clone of this repo>
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
│   ├── grammar/          # One file per topic (27): clitics, tenses, subjunctive, relatives, se, si-clauses...
│   ├── verbs/
│   │   └── verbs.json    # 12 core verbs (3 regular: hablar, comer, vivir) with full paradigms
│   ├── vocabulary/       # One file per theme (18): food, household, places, body, clothing, class notes...
│   ├── reference/        # Complete lesson vocabulary reference (used by !tarjetas)
│   ├── scenarios/        # Roleplay scenario cards for !rol
│   ├── expressions/      # Greetings, classroom phrases, discourse markers
│   ├── exercises/        # Homework exercises (e.g. preterite review, for !drill ejercicio)
│   ├── external/         # Language Transfer track mapping (for !lt)
│   ├── concepts.json     # Concept taxonomy: what drills and lesson observations roll up to, and error tags
│   ├── observations/     # What was read from lesson screenshots (staged/, one file per screenshot)
│   ├── compiled/         # Generated from approved observations; read by the app (deck + corrections drill)
│   └── progress/         # Local progress fallback (SQLite); git-ignored
├── reference/
│   ├── SCHEMAS.md        # Canonical JSON schemas for all data modules
│   └── CLITIC_RULES.md   # Clitic placement and ordering rules
├── app/
│   ├── spanish_drill.py  # Streamlit interface, command parser & drill runner
│   ├── pattern_modules.py# Shared drill engine for the 🚀 Adelantado topics (se, relativos, ...)
│   ├── conversation.py   # In-app !hablar / !rol chat via the Claude API
│   ├── grading.py        # Claude grading of sentence answers (optional)
│   ├── flashcards.py     # !tarjetas decks and card logic
│   ├── progress.py       # Attempt log, Leitner queue, stats for !progreso
│   ├── store.py          # Where progress is kept: hosted Turso (HTTP) or local SQLite
│   ├── concepts.py       # Loader and validator for data/concepts.json
│   └── external.py       # Language Transfer tracker (!lt)
├── ingest/               # Screenshot ingestion: schemas.py (formats), prompt.py, pipeline.py; not imported by the app
├── scripts/              # ingest.py (lesson screenshots -> study data), migrate_progress.py
├── tests/                # pytest suite
└── README.md             # This file
```

---

## Commands Reference

### All menu commands

Every button in the app's menu, grouped by menu section (source: `DRILL_CATEGORIES` in `app/spanish_drill.py`). Longer descriptions of some of them follow below.

**🎲 Repaso interleaved**

- `!drill mixto` — 🎲 Mixto (todos los temas)

**🔁 Repaso espaciado**

- `!drill fallos` — 🔁 Quiz: lo que fallé
- `!repasar fallos` — 📖 Repasar solo lo que falle
- `!progreso` — 📈 Mi progreso

**Verbos y Tiempos**

- `!drill rutina` — ☀️ Rutina diaria (presente)
- `!drill imperativo` — ⚡ Imperativo
- `!drill cambios` — 🔄 Cambios de raíz
- `!drill pasado` — ⏳ Pasado (imperfecto)
- `!drill estar_gerundio` — 🎬 Estar + gerundio
- `!drill preterito` — 📜 Pretérito irregular
- `!drill pluscuam` — ⏮ Pluscuamperfecto
- `!drill futuro` — 🔮 Futuro irregular
- `!drill condicional` — 🤔 Condicional
- `!drill participios` — ✅ Participios
- `!drill ejercicio` — 📝 Ejercicio (homework)

**Gramática**

- `!drill ser_estar` — ⚖️ Ser, estar y hay
- `!drill gustar` — 💛 Gustar y similares
- `!drill pronombres` — 🔀 Pronombres dobles
- `!drill por_para` — ↔️ Por vs. Para
- `!drill preposiciones` — 🧩 Otras preposiciones
- `!drill demostrativos` — 👉 Demostrativos
- `!drill adjetivos` — 🔤 Adjetivos cortos
- `!drill reflexivos` — 🪞 Reflexivos/Recíprocos
- `!drill indefinidos` — 🚫 Indefinidos/Negativos
- `!drill estructuras` — 🗣️ Estructuras + preguntas

**Vocabulario**

- `!tarjetas` — 🃏 Tarjetas (mis lecciones)
- `!drill vocabulario` — 📚 Mis lecciones
- `!drill vocab_comun` — 🌍 Común (general)
- `!drill vocab_mezcla` — 🔀 Mezcla
- `!drill numeros` — 🔢 Números
- `!drill adverbios` — 🧭 Adverbios
- `!drill lugares` — 📍 Lugares

**🚀 Adelantado (aún no en clase)**

- `!drill subjuntivo` — 🌱 Subjuntivo presente
- `!drill se` — 🔄 Se: accidental, impersonal y pasivo
- `!drill relativos` — 🔗 Relativos (que, quien, lo que, cuyo)
- `!drill cond_perfecto` — 🕰️ Habría / debería haber
- `!drill si_hipotetico` — 💭 Si + hipótesis
- `!drill cognados` — 🔤 Cognados (-ción, -mente, -dad…)

**🎧 Escuchar**

- `!lt` — 🎧 Language Transfer

**👵 De mi Suegra**

- `!drill gerundio` — 🚂 Ir + Gerundio

### Drills (details)

- `!drill imperativo` — 5-min imperative conjugation drill (tú, usted, nosotros, ustedes; affirmative + negative)
- `!tarjetas` — Flashcards from your complete lesson vocabulary: `data/reference/vocabulary_reference.json`, the "Spanish Vocabulary — Complete Lesson Reference" (3,563 words and phrases from Lessons 1–119), as 36 decks (expressions by situation, verbs, nouns by topic, adjectives, small words), plus **📝 Notas de clase (extra)** for class-notes phrases the reference leaves out. Choose by topic, or by lesson range (default: your last ten lessons). Cards show the lesson where each word first appeared, and an example sentence where there is one (from the reference's notes, or the whiteboard examples in `class_notes_recent.json`). Tap the card to flip it, then "Otra vez" (it comes back a few cards later) or "Lo sabía". Results feed the spaced-repetition queue, so missed words also show up in `!drill fallos`.
- `!drill condicional` — Simple conditional: irregular stems (tendría, diría...), regular forms, and translations of the seven uses
- `!drill subjuntivo` — Present subjunctive: forms (regular, dé/vaya/sea/haya/esté/sepa, -go/-zco, stem changes incl. durmamos, -car/-gar/-zar) and sentences where the trigger decides the mood — including indicative contrasts (creo que tiene, cuando + habit), so it drills *when*, not just *how*. Ahead of the lessons; Language Transfer tracks 69–85
- `!drill gustar` — Gustar-type verbs as one pattern (gustar, encantar, doler, importar, molestar, interesar, faltar, hacer falta): pronoun + verb fill-ins in present and past, translations, and correcting the classic mistakes (Yo gusto el café → Me gusta el café). Language Transfer tracks 42, 45, 63
- **🚀 Adelantado (aún no en clase)** — topics Language Transfer teaches before the lessons do, built on one shared data shape (`app/pattern_modules.py`: fill-ins, translations, "which type?" questions, mistakes to correct):
  - `!drill se` — accidental se (se me olvidaron), impersonal and passive se, and telling se apart (reflexive, reciprocal, se = le). LT 47, 80
  - `!drill relativos` — que, quien, lo que, el que, donde, cuyo (+ the preposition-first rule). LT 83
  - `!drill cond_perfecto` — habría / debería haber / podría haber + participle. LT 43, 55
  - `!drill si_hipotetico` — si clauses: real, hypothetical (si tuviera… viajaría) and impossible past. LT 78
  - `!drill cognados` — English → Spanish suffix rules (-ción, -mente, -dad…) and false friends. LT 2–5, 12
- `!drill ser_estar` — Ser, estar or hay in context, including adjectives that change meaning (ser listo / estar listo)
- `!lt` — 🎧 Language Transfer tracker: the free 90-track Complete Spanish course mapped to your lessons (`data/external/language_transfer.json`). Tick tracks as you listen (saved to `data/progress/lt_progress.json`, so it survives restarts); 🆕 marks topics your lessons haven't covered yet. Every Repaso screen also lists the tracks that explain its grammar.
- `!drill estar_gerundio` — Gerunds (regular + the o→u, i→y, e→i irregulars) and estar + gerundio in present, future and four pasts: imperfecto (estaba), pretérito indefinido (estuve), pretérito perfecto (he estado), pluscuamperfecto (había estado)

### Immersion Modes

Typed commands also include `!hablar`, `!rol [tema]` (themes: restaurante, transporte, vecinos, salud, narrativa, viajes, compras, convivencia), `!pausa`, `!resumen`, `!progreso`, `!tarjetas` and `!lt`.

- `!hablar` — Conversational partner mode (100% Spanish, 2–4 sentence turns, corrections after each reply)
- `!rol [tema]` — Launch a roleplay scenario with persona and objective
- `!progreso` — Streak, weekly accuracy, attempts per day, spaced-repetition boxes, and accuracy per topic (weakest first)

With Claude API access the conversation happens inside the app (see **In-app conversation** below); without it, these screens give you a topic or scenario card to take to a chat with Claude.

### Control

- `!pausa` — Step out of immersion to explain a rule in English
- `!resumen` — End-of-session diagnostic (patterns practiced, mistakes, new vocabulary)

---

### Progress & spaced repetition

Every graded answer is logged with what you typed, and each item gets a spaced-repetition card. Where that is kept depends on configuration (`app/store.py`):

- **Hosted (recommended, and needed on Streamlit Community Cloud):** a [Turso](https://turso.tech) database, reached over its HTTP API with no extra package. Set two secrets, in Streamlit Cloud's *Secrets* or in `.streamlit/secrets.toml`, or as environment variables:
  ```toml
  TURSO_DATABASE_URL = "libsql://<database>-<org>.turso.io"
  TURSO_AUTH_TOKEN = "<token>"
  ```
  Progress then survives redeploys and is shared between your devices. The tables are created on first use.
- **Local fallback:** without those, a SQLite file (`data/progress/progress.db`, git-ignored; override with `SPANISH_PROGRESS_DB`). On Streamlit Cloud that file is wiped on every reboot or redeploy.

`python scripts/migrate_progress.py --check` tests the connection (it leaves nothing behind). To move an existing history into the hosted database, download a backup from 📈 `!progreso` and run `python scripts/migrate_progress.py <backup.json>` once with the two variables set; it merges, so running it twice is safe. 📈 `!progreso` keeps a 💾 *Copia de seguridad* download as an offline copy; restoring from a file is only offered with the local fallback. If the database can't be reached, drills keep working and the menu shows a warning that progress isn't being saved.

Missed items enter a Leitner queue: a miss is due again immediately, one correct answer pushes it out a day, two a week (then two weeks).

- `!drill fallos` — timed quiz on what is due
- `!repasar fallos` — read-through of the same queue ("Repasar solo lo que falle")
- Drill length defaults per module (`MODULE_DURATIONS` in `spanish_drill.py`) and can be overridden with the **Duración** selector.

### In-app conversation

`!hablar` and `!rol` talk to Claude directly when the app can find credentials:

- `ANTHROPIC_API_KEY` in the environment, **or**
- `ANTHROPIC_API_KEY = "..."` in `.streamlit/secrets.toml` (git-ignored), **or**
- a profile from `ant auth login`.

It uses `claude-opus-5-5` at low effort, streams replies, and opts into server-side refusal fallbacks (`fallbacks: "default"`). Every message is a billed API call. Without credentials the drills work exactly as before.

The same credentials turn on **Claude grading for sentence answers**: when a translation doesn't match the model answer, Claude checks whether it is still correct Spanish that uses the drilled grammar ("Te quería pedir un favor" for "Quería pedirte un favor") and explains the main error if not. That is one API call per missed sentence; single words and short forms are always graded exactly. Wrong answers also show a word-by-word comparison with the model answer (no API needed).

Entries in `data/` marked `"source": "claude-draft"` were written by Claude to fill out small drill pools, not taken from lesson materials; review them like any other content.

### Tests

`pip install pytest && python -m pytest tests` — needs Streamlit 1.46+ (the sidebar layout nests columns, which older versions reject). The chat tests use a fake client, so no API key is needed.

## Data Ingestion Workflow

### Lesson screenshots (`scripts/ingest.py`)

Screenshots of the whiteboard, chat or annotated exercises become study material in three steps, run on your own computer (it needs `ANTHROPIC_API_KEY`; the images are sent to the Claude API):

```bash
python scripts/ingest.py run ~/Desktop/leccion120 --lesson L120   # read new screenshots
python scripts/ingest.py review --approve-high                    # approve / edit / reject what was found
python scripts/ingest.py compile                                  # write the approved items for the app
git add data/observations/staged data/compiled && git commit -m "Lesson 120 screenshots"
```

- **run** hashes each image, skips any it has already read (so it is safe to run again and costs nothing), and writes what Claude found to `data/observations/staged/<hash>.json` as *pending*: vocabulary, expressions, example sentences, rule notes and tutor corrections (what you said, the fix, and why). Items the app already has are marked *duplicate*. Useful flags: `--dry-run` (send nothing), `--limit N`, `--kind`, `--date`, `--model`, `--force` (read again; add `--discard-reviews` if that image was already reviewed). PNG, JPEG, WebP and GIF are read; convert HEIC first. The images are copied to `data/artifacts/raw/`, which is not in git.
- **review** shows each pending item for a one-key decision. `--approve-high` first approves every high-confidence word and expression, leaving corrections and uncertain readings for you. `python scripts/ingest.py status` shows the counts, and `review --status approved` (or `rejected`, `duplicate`) goes back over earlier decisions.
- **compile** rewrites `data/compiled/lesson_observations.json` from the approved items only. The app shows them as the flashcard deck **📸 De mis capturas** and, once there is at least one correction, the drill **✍️ Correcciones de clase** (`!drill correcciones`: your own mistake is the prompt, the tutor's version is the answer).

The formats are defined in `ingest/schemas.py`; topics and kinds of mistake come from `data/concepts.json`.

### Submit Raw Materials (other content)

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
- `vocabulary` → a per-topic file in `data/vocabulary/` (e.g. `places.json`)
- `grammar_rule` → a per-topic file in `data/grammar/` (e.g. `subjunctive.json`)
- `scenario` → `data/scenarios/scenarios.json`
- `expression` → a file in `data/expressions/` (e.g. `greetings_and_classroom.json`)

See `reference/SCHEMAS.md` for the complete JSON schema reference.

---

## Feature Roadmap

### Done

✅ Directory structure & base schemas  
✅ `data/verbs/` with 12 core verbs (3 regular, 9 irregular)  
✅ Ingestion workflow; vocabulary, grammar and expression data populated  
✅ Drills for every menu command listed above, incl. `!drill pronombres`, `!drill mixto` and the 🚀 Adelantado topics  
✅ Scenario cards for `!rol`  
✅ `!hablar` and `!rol` conversation with Claude inside the app (`app/conversation.py`)  
✅ Session analytics & spaced repetition (`app/progress.py`, `!drill fallos`, `!progreso`)  
✅ `!tarjetas` flashcards and `!lt` Language Transfer tracker  

### Ideas

- [ ] Listening / TTS practice
- [ ] Spanish → English flashcards
- [ ] Readings with comprehension questions
- [ ] Dictation / speaking feedback

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
- Review `reference/CLITIC_RULES.md` for grammar deep dives
- Submit ingestion materials via `INGESTION.md`

¡Buena suerte! 🚀
