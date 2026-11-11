# Lesson observations

What was read from lesson screenshots, before it becomes study material.

- `staged/<sha12>.json` — one file per screenshot: the `Artifact` record (hash,
  lesson, kind) and its `Observation`s (vocabulary, expressions, tutor
  corrections, examples, rule notes), each `pending`, `approved`, `rejected`
  or `duplicate`. The format is defined in `ingest/schemas.py`.
- The screenshots themselves are not in git: they go in `data/artifacts/raw/`,
  which is ignored.
- Concept and error-tag ids come from `data/concepts.json`.

Written by `python scripts/ingest.py run` and updated by `review`. `compile`
turns the approved ones into `data/compiled/lesson_observations.json`, which
is what the app reads. See "Lesson screenshots" in the main README.
