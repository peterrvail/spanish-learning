# Data Ingestion Workflow

Convert your raw lesson materials (homework, screenshots, notes) into structured JSON data.

---

## How It Works

1. **Collect** raw materials (text, images, PDFs)
2. **Describe** using the ingestion template below
3. **Paste/upload** the raw content
4. **I parse** and extract into canonical JSON schemas (see `reference/SCHEMAS.md`)
5. **Data merged** into the appropriate module (`verbs.json`, `vocabulary.json`, etc.)

---

## Ingestion Template

Use this template to structure your submission:

```json
{
  "source": "FILENAME_or_DESCRIPTION",
  "content_type": "verbs | vocabulary | grammar_rule | scenario | expression | reading | general",
  "raw_data": "PASTE_YOUR_RAW_MATERIAL_HERE",
  "metadata": {
    "topic": "imperative conjugation, transit vocabulary, etc.",
    "difficulty": "A1 | A2 | B1 | B2 | C1 | C2",
    "extracted_date": "YYYY-MM-DD",
    "notes": "Optional additional context"
  }
}
```

---

## Example Submissions

### Example 1: Verb Conjugation Homework

**File**: `homework_week_3_imperatives.txt`

```json
{
  "source": "homework_week_3_imperatives.txt",
  "content_type": "verbs",
  "raw_data": "Conjugate the following verbs in tú affirmative imperative:\n1. escribir → escribe\n2. romper → rompe\n3. subir → sube\n4. conseguir → consigue (stem change e→i)\n5. dormir → duerme (stem change o→ue)\n\nNegative imperatives (tú):\n1. escribir → no escribas\n2. romper → no rompas\n3. subir → no subas\n4. conseguir → no consigas\n5. dormir → no duermas",
  "metadata": {
    "topic": "regular and stem-changing imperatives",
    "difficulty": "B1",
    "extracted_date": "2026-08-16",
    "notes": "Focus on -ir and -er verbs with stem changes"
  }
}
```

**Result**: New verb entries added to `data/verbs/verbs.json` for escribir, romper, subir, conseguir, dormir with imperative paradigms.

---

### Example 2: Vocabulary List

**File**: `transit_vocabulary_lesson.txt`

```json
{
  "source": "transit_vocabulary_lesson.txt",
  "content_type": "vocabulary",
  "raw_data": "TRANSIT & LOGISTICS VOCABULARY (B1/B2)\n\n1. el retraso — delay\n   Pronunciation: reh-TRAH-so (masculine)\n   Collocations: tener un retraso, el retraso de 30 minutos\n   Example: El autobús tiene un retraso de media hora.\n\n2. la compensación — compensation\n   Pronunciation: kohm-pehn-sah-thee-OHN (feminine)\n   Collocations: pedir compensación, ofrecer compensación\n   Example: Pidieron compensación por el retraso.\n\n3. la parada — stop (bus/train)\n   Pronunciation: pah-RAH-dah (feminine)\n   Collocations: la próxima parada, bajar en la parada\n   Example: ¿Cuál es la próxima parada?\n\n4. el andén — platform (train station)\n   Pronunciation: ahn-DEHN (masculine)\n   Collocations: en el andén, el andén número 3\n   Example: El tren sale del andén 5.\n\n5. la taquilla — ticket window/booth\n   Pronunciation: tah-KEE-yah (feminine)\n   Collocations: en la taquilla, ir a la taquilla\n   Example: Compré los boletos en la taquilla.",
  "metadata": {
    "topic": "transit, logistics, travel",
    "difficulty": "B1",
    "extracted_date": "2026-08-16",
    "notes": "High-frequency vocabulary for travel scenarios"
  }
}
```

**Result**: New entries added to `data/vocabulary/vocabulary.json` for retraso, compensación, parada, andén, taquilla with gender, pronunciation, collocations, and examples.

---

### Example 3: Grammar Rule (Clitic Order)

**File**: `grammar_lesson_double_clitics.txt`

```json
{
  "source": "grammar_lesson_double_clitics.txt",
  "content_type": "grammar_rule",
  "raw_data": "DOUBLE OBJECT PRONOUNS: WORD ORDER\n\nRule: Indirect Object Pronoun + Direct Object Pronoun\n\nOrder: me/te/le/nos/os/les BEFORE lo/la/los/las\n\nExamples:\n• Dímelo. (Tell me it.) — me + lo\n• No me lo digas. (Don't tell me it.) — me + lo\n• Les compré los libros. (I bought them the books.) — les + los\n• Te la presté ayer. (I lent it to you yesterday.) — te + la\n\nSpecial Case: When le or les precedes lo, la, los, las, the le/les changes to SE:\n• Le expliqué el problema. → Se lo expliqué. (I explained the problem to him.) — se + lo\n• Les envié el correo. → Se lo envié. (I sent them the email.) — se + lo",
  "metadata": {
    "topic": "pronoun mechanics, clitic order, double objects",
    "difficulty": "B1",
    "extracted_date": "2026-08-16",
    "notes": "Critical for both spoken and written Spanish"
  }
}
```

**Result**: New grammar rule entry added to `data/grammar/grammar_rules.json` with the rule, examples, special cases, and related rules.

---

### Example 4: Screenshot of Lesson Notes

**File**: `lesson_screenshot_20260815.png` (hypothetical image upload)

```json
{
  "source": "lesson_screenshot_20260815.png",
  "content_type": "verbs",
  "raw_data": "[Image contains: A lesson page showing irregular imperatives with examples]\n\nIRREGULAR IMPERATIVES (TÚ FORM):\n1. decir → di (not 'digas', just 'di')\n2. hacer → haz (not 'haces')\n3. ir → ve (not 'vas')\n4. poner → pon (not 'pones')\n5. salir → sal (not 'sales')\n6. ser → sé (not 'eres', accent on 'sé' to distinguish from 'se')\n7. tener → ten (not 'tienes')\n8. venir → ven (not 'vienes')",
  "metadata": {
    "topic": "irregular tú affirmative imperatives",
    "difficulty": "B1",
    "extracted_date": "2026-08-15",
    "notes": "Key high-frequency irregulars for spoken fluency"
  }
}
```

**Result**: Verb data for decir, hacer, ir, poner, salir, ser, tener, venir verified and enhanced in `data/verbs/verbs.json`.

---

### Example 5: Real-World Scenario

**File**: `roleplay_scenario_airport_checkin.txt`

```json
{
  "source": "roleplay_scenario_airport_checkin.txt",
  "content_type": "scenario",
  "raw_data": "SCENARIO: Airport Check-In Problem\n\nSITUATION:\nYou arrive at the airport for an international flight. The check-in agent tells you your luggage is 5 kg overweight. You need to: (1) negotiate a reduction in baggage fees, (2) clarify what items you can remove, (3) ask about alternative solutions (redistributing weight, purchasing an additional bag).\n\nPERSONA:\n- Name: Agent López\n- Role: Airline check-in representative\n- Formality: Formal/professional\n- Tone: Polite but firm on regulations\n\nTARGET GRAMMAR:\n- Subjunctive (request/doubt): 'Es posible que...', 'Quiero que...'\n- Conditional: 'Podría...', 'Sería posible...'\n- Negative imperatives (formal): 'No abra sus maletas aquí'\n- Past tense for context: 'Me han dicho que...'\n\nVOCABULARY:\n- el equipaje — luggage\n- el sobrepeso — overweight\n- la tarifa — fee/rate\n- descargar/redistribuir — to remove/redistribute\n- la maleta — suitcase\n\nSUCCESS CRITERIA:\n1. Use at least 2 subjunctive forms\n2. Successfully negotiate or accept the overweight fee\n3. Maintain formal register throughout",
  "metadata": {
    "topic": "travel, air travel, negotiation",
    "difficulty": "B1-B2",
    "extracted_date": "2026-08-16",
    "notes": "Real-world problem-solving with formal register"
  }
}
```

**Result**: New scenario card added to `data/scenarios/scenarios.json` with context, persona, objectives, grammar targets, and success criteria.

---

## Submission Process

### Step 1: Prepare Your Material

Gather any of the following:
- Homework assignments (text or images)
- Lesson notes or screenshots
- Vocabulary lists
- Grammar rules or explanations
- Real-world scenarios or dialogues
- Short stories or reading passages
- Audio transcripts or dictation exercises

### Step 2: Fill Out the Template

Copy the JSON template above and paste:
1. Source filename/description
2. Content type (verbs, vocabulary, grammar_rule, scenario, expression, reading, etc.)
3. Raw material (paste directly or describe image contents)
4. Metadata (topic, difficulty, date, notes)

### Step 3: Submit to Me

Paste the filled template in your next message and I will:
1. **Parse** the raw data
2. **Extract** key information
3. **Map** to canonical JSON schemas
4. **Validate** against `reference/SCHEMAS.md`
5. **Merge** into the appropriate data module
6. **Confirm** completion with a summary

---

## FAQ

**Q: Can I submit images (lesson screenshots)?**  
A: Yes! Describe the text contents in the `raw_data` field. I'll extract verbs, vocabulary, grammar rules, etc., directly from the image.

**Q: What if my material overlaps with existing data?**  
A: I'll merge, enhance, or update existing entries. For example, if you submit a homework sheet about verbs I already have, I'll add new example sentences or refine the teaching notes.

**Q: How often should I submit materials?**  
A: As often as you have them! Weekly submissions are ideal for continuous system enrichment.

**Q: Can I submit in bulk (multiple lessons at once)?**  
A: Yes. Use multiple JSON objects in an array or submit them sequentially. I'll process each.

**Q: What happens to the ingested data?**  
A: Data is merged into `data/*/` modules and immediately usable in drills, scenarios, and conversational modes.

---

## Next Steps

1. Gather your first set of lesson materials
2. Fill out the ingestion template
3. Submit with: `I want to ingest...` followed by your filled template
4. I'll parse, validate, and merge into the system
5. New drills and scenarios unlock as modules are populated

¡Vamos! Let's build your personalized learning system. 🚀
