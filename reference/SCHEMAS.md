# JSON Schema Definitions

All data modules follow these canonical schemas. Use them for validation during ingestion.

---

## Verbs Schema (`data/verbs/verbs.json`)

```json
{
  "verb": {
    "infinitive": "hablar",
    "stem": "habl",
    "irregularities": ["stem_change", "yo_irregular", "subjunctive_irregular"],
    "moods": {
      "indicative": {
        "present": { "yo": "hablo", "tú": "hablas", "él": "habla", "nosotros": "hablamos", "vosotros": "habláis", "ellos": "hablan" },
        "preterite": { "yo": "hablé", "tú": "hablaste", ... },
        "imperfect": { "yo": "hablaba", "tú": "hablabas", ... }
      },
      "subjunctive": {
        "present": { "yo": "hable", "tú": "hables", ... },
        "imperfect": { "yo": "hablara", "tú": "hablaras", ... }
      },
      "conditional": { "yo": "hablaría", "tú": "hablarías", ... },
      "imperative": {
        "affirmative": { "tú": "habla", "usted": "hable", "nosotros": "hablemos", "ustedes": "hablen" },
        "negative": { "tú": "no hables", "usted": "no hable", "nosotros": "no hablemos", "ustedes": "no hablen" }
      }
    },
    "gerund": "hablando",
    "past_participle": "hablado",
    "reflexive_form": "hablarse",
    "infinitive_with_clitics": ["decírmelo", "no me lo digas", "dímelo"],
    "example_sentences": [
      { "spanish": "Háblame de tu día.", "english": "Tell me about your day.", "mood": "imperative", "register": "informal" },
      { "spanish": "Dígame la verdad, por favor.", "english": "Tell me the truth, please.", "mood": "imperative", "register": "formal" }
    ],
    "teaching_notes": "Focus on the imperative stem (habl-) and how clitics attach to affirmative forms."
  }
}
```

---

## Vocabulary Schema (`data/vocabulary/vocabulary.json`)

```json
{
  "entry": {
    "spanish": "autobús",
    "english": "bus",
    "part_of_speech": "noun",
    "gender": "masculine",
    "plural": "autobuses",
    "domain": "transit",
    "cefr_level": "A1",
    "collocations": ["tomar el autobús", "esperar el autobús", "bajar del autobús"],
    "example_sentences": [
      { "spanish": "El autobús llega cada diez minutos.", "english": "The bus arrives every ten minutes." }
    ],
    "synonyms": ["bus", "autobús urbano"],
    "antonyms": [],
    "notes": "Common in Latin America; 'bus' alone is also acceptable."
  }
}
```

---

## Grammar Schema (`data/grammar/grammar_rules.json`)

```json
{
  "rule": {
    "id": "clitic_order_double_object",
    "title": "Double Object Pronoun Order",
    "description": "When both indirect and direct object pronouns appear, the indirect precedes the direct. Indirect comes before direct: me/te/le/nos/os/les before lo/la/los/las.",
    "examples": [
      { "correct": "Dímelo.", "incorrect": "Dimelo.", "explanation": "The indirect object 'me' precedes the direct object 'lo'." },
      { "correct": "No me lo digas.", "incorrect": "No lo me digas.", "explanation": "Same rule applies in negative imperatives." }
    ],
    "contraindications": ["When only one pronoun is present, this rule does not apply."],
    "related_rules": ["clitic_attachment_affirmative_imperative", "clitic_position_infinitive"],
    "practice_focus": "imperative"
  }
}
```

---

## Scenarios Schema (`data/scenarios/scenarios.json`)

```json
{
  "scenario": {
    "id": "transit_delay_resolution",
    "title": "Transit Delay Resolution",
    "context": "You're at a bus station. A bus is 30 minutes late. You need to negotiate with the attendant.",
    "persona": { "name": "Attendant (Oficial de Estación)", "role": "transit_worker", "formality": "formal" },
    "user_objective": "Find out why the bus is delayed and request compensation or alternative transport.",
    "target_grammar": ["imperative_formal", "preterite", "subjunctive_uncertainty"],
    "required_vocabulary": ["retraso", "autobús", "compensación", "alternativo"],
    "success_criteria": ["Use at least 3 formal commands", "Successfully extract reason for delay", "Negotiate for alternative or compensation"],
    "difficulty": "B1",
    "notes": "Focuses on formal register and problem-solving commands."
  }
}
```

---

## Expressions Schema (`data/expressions/expressions.json`)

```json
{
  "expression": {
    "spanish": "sin embargo",
    "english": "nevertheless, however",
    "type": "discourse_marker",
    "register": "formal",
    "literal_translation": "without embargo (without hindrance)",
    "context": "Transitions between clauses to introduce a contrasting idea.",
    "example_sentences": [
      { "spanish": "Estudié mucho; sin embargo, no aprobé el examen.", "english": "I studied a lot; nevertheless, I didn't pass the exam." }
    ],
    "synonyms": ["no obstante", "empero", "pero"],
    "related_expressions": ["por lo tanto", "en cambio", "a fin de cuentas"]
  }
}
```

---

## Readings Schema (`data/readings/readings.json`)

```json
{
  "reading": {
    "id": "preterite_vs_imperfect_1",
    "title": "A Day in Seville",
    "level": "B1",
    "target_structures": ["preterite", "imperfect", "past_continuous"],
    "text": "Ayer estaba en Sevilla. Hacía mucho calor. De repente, empezó a llover...",
    "annotations": [
      { "word": "estaba", "pos": "verb", "mood": "imperfect", "note": "Background condition (I was in Seville)" },
      { "word": "empezó", "pos": "verb", "mood": "preterite", "note": "Sudden event (it started to rain)" }
    ],
    "comprehension_questions": [
      { "question": "¿Qué tiempo hacía?", "answer": "Hacía mucho calor." },
      { "question": "¿Qué pasó de repente?", "answer": "Empezó a llover." }
    ]
  }
}
```

---

## Drill Schema (for runtime use)

```json
{
  "drill": {
    "type": "conjugation | cloze | error_parsing | transformation",
    "module": "imperativo",
    "duration_seconds": 300,
    "target_grammar": ["imperative_affirmative", "clitic_attachment"],
    "instructions": "Conjugate the verb in the affirmative imperative form (tú). Add pronouns if given.",
    "items": [
      {
        "prompt": "Conjugate 'hablar' (tú, affirmative): Tú debe _____ con tu amigo.",
        "target": "habla",
        "alternative_targets": [],
        "hint": "Use the present tense stem for regular verbs.",
        "explanation": "Regular -ar verbs drop the -r in the tú affirmative imperative."
      }
    ]
  }
}
```

---

## Ingestion Template (for user submissions)

When adding content, provide:

```json
{
  "source": "lesson_screenshot_20260815.png or homework_assignment_3.txt",
  "content_type": "verbs | vocabulary | grammar_rule | scenario | expression | reading",
  "raw_data": "...",
  "metadata": {
    "topic": "imperatives, transit vocabulary, etc.",
    "difficulty": "A1 | A2 | B1 | B2 | C1 | C2",
    "extracted_date": "2026-08-16"
  }
}
```

---

## Contracts that are enforced in code

The per-file shapes above are illustrative. These three are checked by code and tests:

### Progress database (`app/progress.py`, schema version 2)

| Table | Columns |
|---|---|
| `attempts` | `id`, `ts`, `module`, `exercise_type`, `target_form`, `is_correct`, `typed_answer`, `error_tag`, `card_key` |
| `cards` | `key` (sha1 of prompt and answer), `item_json`, `box` (0–3), `due`, `attempts`, `misses` |
| `lt_done` | `track` (Language Transfer tracks listened to) |
| `meta` | `key`, `value` (`schema_version`) |

`typed_answer`, `error_tag` and `card_key` are empty for attempts logged before version 2. `error_tag` is an `error` concept id; the app itself only sets `accent`.

### Concepts (`data/concepts.json`, validated by `python app/concepts.py`)

```json
{"id": "preterito", "label": "Pretérito (pasado simple)", "kind": "grammar",
 "modules": ["preterito", "ejercicio"], "exercise_type_prefixes": ["preterite_"], "parent": null}
```

`kind` is `grammar`, `vocab` or `error`. An attempt's concept is looked up from its exercise type (longest matching prefix), then its module, when it is read; it is not stored.

### Lesson observations (`ingest/schemas.py`, Pydantic)

`data/observations/staged/<sha12>.json` holds one `ObservationFile`: the `Artifact` (the screenshot: `sha256`, `filename`, `kind`, `lesson`, `captured_on`, `ingested_at`, `extractor`) and its `Observation`s:

```json
{"id": "abababababab-2", "artifact_id": "<sha256>", "status": "pending",
 "type": "correction", "region": "tutor_annotation",
 "verbatim": "yo hablo ayer -> hablé", "spanish": "Yo hablé ayer.", "english": null,
 "correction": {"wrong": "yo hablo ayer", "right": "yo hablé ayer", "why": "pasado: pretérito"},
 "concept_ids": ["preterito"], "error_tags": ["tense_choice"], "confidence": "medium"}
```

`type`: `vocab`, `expression`, `correction`, `example`, `rule_note`. `region`: `tutor_annotation`, `board`, `exercise`, `learner_text`. `status`: `pending`, `approved`, `rejected`, `duplicate`. Raw images are not committed (`data/artifacts/raw/` is git-ignored).
