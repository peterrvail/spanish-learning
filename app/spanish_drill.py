import streamlit as st
import difflib
import json
import random
import re
import unicodedata
from datetime import datetime, timedelta
import os

import conversation
import external
import flashcards
import grading
import progress

# Load data
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
VERBS_FILE = os.path.join(DATA_DIR, "verbs", "verbs.json")
GRAMMAR_DIR = os.path.join(DATA_DIR, "grammar")
SCENARIOS_FILE = os.path.join(DATA_DIR, "scenarios", "scenarios.json")
EXERCISES_DIR = os.path.join(DATA_DIR, "exercises")

# Commands available from both the mobile button menu and the desktop sidebar
DRILL_CATEGORIES = {
    "🎲 Repaso interleaved": [
        ("🎲 Mixto (todos los temas)", "!drill mixto"),
    ],
    "🔁 Repaso espaciado": [
        ("🔁 Quiz: lo que fallé", "!drill fallos"),
        ("📖 Repasar solo lo que falle", "!repasar fallos"),
        ("📈 Mi progreso", "!progreso"),
    ],
    "Verbos y Tiempos": [
        ("☀️ Rutina diaria (presente)", "!drill rutina"),
        ("⚡ Imperativo", "!drill imperativo"),
        ("🔄 Cambios de raíz", "!drill cambios"),
        ("⏳ Pasado (imperfecto)", "!drill pasado"),
        ("🎬 Estar + gerundio", "!drill estar_gerundio"),
        ("📜 Pretérito irregular", "!drill preterito"),
        ("⏮ Pluscuamperfecto", "!drill pluscuam"),
        ("🔮 Futuro irregular", "!drill futuro"),
        ("🤔 Condicional", "!drill condicional"),
        ("🌱 Subjuntivo presente", "!drill subjuntivo"),
        ("✅ Participios", "!drill participios"),
        ("📝 Ejercicio (homework)", "!drill ejercicio"),
    ],
    "Gramática": [
        ("⚖️ Ser, estar y hay", "!drill ser_estar"),
        ("🔀 Pronombres dobles", "!drill pronombres"),
        ("↔️ Por vs. Para", "!drill por_para"),
        ("🧩 Otras preposiciones", "!drill preposiciones"),
        ("👉 Demostrativos", "!drill demostrativos"),
        ("🔤 Adjetivos cortos", "!drill adjetivos"),
        ("🪞 Reflexivos/Recíprocos", "!drill reflexivos"),
        ("🚫 Indefinidos/Negativos", "!drill indefinidos"),
        ("🗣️ Estructuras + preguntas", "!drill estructuras"),
    ],
    "Vocabulario": [
        ("🃏 Tarjetas (mis lecciones)", "!tarjetas"),
        ("📚 Mis lecciones", "!drill vocabulario"),
        ("🌍 Común (general)", "!drill vocab_comun"),
        ("🔀 Mezcla", "!drill vocab_mezcla"),
        ("🔢 Números", "!drill numeros"),
        ("🧭 Adverbios", "!drill adverbios"),
        ("📍 Lugares", "!drill lugares"),
    ],
    "🎧 Escuchar": [
        ("🎧 Language Transfer", "!lt"),
    ],
    "👵 De mi Suegra": [
        ("🚂 Ir + Gerundio", "!drill gerundio"),
    ],
}
# Flat list kept for backward-compatible lookups (parse_command etc.)
DRILL_COMMANDS = [item for group in DRILL_CATEGORIES.values() for item in group]
ROL_COMMANDS = [
    ("🍽 Restaurante", "!rol restaurante"),
    ("🚌 Transporte", "!rol transporte"),
    ("🏠 Vecinos", "!rol vecinos"),
    ("🏥 Salud", "!rol salud"),
    ("📖 Narrativa", "!rol narrativa"),
    ("🏨 Viajes", "!rol viajes"),
    ("🛍 Compras", "!rol compras"),
    ("🤝 Convivencia", "!rol convivencia"),
]
HABLAR_COMMANDS = [
    ("🗣️ Conversación libre", "!hablar"),
]

# Default drill length per module (seconds). Anything not listed gets
# DEFAULT_DRILL_SECONDS. The sidebar/header "Duración" selector can override all of them.
DEFAULT_DRILL_SECONDS = 300
MODULE_DURATIONS = {
    "mixto": 600,        # 20 interleaved items across topics
    "preterito": 420,    # 20 items, longer conjugations
    "preterite": 420,
    "estar_gerundio": 420,  # 16 items, some 3-word answers (habíamos estado corriendo)
    "subjuntivo": 420,      # 16 items, 10 of them sentences to read
    "progresivo": 420,
    "numeros": 180,
    "adjetivos": 180,
    "participios": 180,
    "futuro": 180,
    "futuro_irregular": 180,
    "fallos": 300,
}
DURATION_CHOICES = {"Por módulo (recomendado)": None, "3 min": 180, "5 min": 300, "10 min": 600, "15 min": 900}

def drill_duration(module_type, override=None):
    """Seconds for a drill: an explicit override, else the module's default."""
    return override or MODULE_DURATIONS.get(module_type, DEFAULT_DRILL_SECONDS)

def is_mobile():
    """Detect iOS/mobile via the request's User-Agent (server-side, no JS needed)."""
    try:
        ua = st.context.headers.get("User-Agent", "") or ""
    except Exception:
        ua = ""
    ua = ua.lower()
    return any(token in ua for token in ["iphone", "ipad", "ipod", "android", "mobile"])

def inject_wide_sidebar_css():
    """Widen the desktop sidebar and stop its buttons from clipping.

    Streamlit ellipsises a button label that doesn't fit on one line, and the
    Repasar icon rides in a narrow companion column, so on a ~1024px window the
    longer names were cut to "Rutina diaria (p..." and the icon collapsed into
    an empty sliver. Letting labels wrap and tightening the padding keeps both
    legible without giving up the two-column grid."""
    st.markdown(
        """
        <style>
        /* Wide, but never more than half of a small window. */
        section[data-testid="stSidebar"],
        section[data-testid="stSidebar"] > div {
            width: min(420px, 50vw) !important;
        }
        /* Wrap instead of truncating, and grow the button to fit the lines. */
        section[data-testid="stSidebar"] div.stButton > button {
            white-space: normal;
            overflow-wrap: anywhere;
            height: auto;
            min-height: 2.5rem;
            line-height: 1.25;
            font-size: 0.9rem;
            padding: 0.4rem 0.45rem;
        }
        /* The ellipsis lives on the label's inner markdown container and <p>,
           which set their own nowrap/hidden, so the rule above alone can't
           reach it. */
        section[data-testid="stSidebar"] div.stButton > button div[data-testid="stMarkdownContainer"],
        section[data-testid="stSidebar"] div.stButton > button p {
            white-space: normal;
            overflow: visible;
            text-overflow: clip;
        }
        /* The 📖 icon sits in a ~40px column; side padding alone would
           swallow it. Streamlit tags each widget with an st-key-<key> class. */
        section[data-testid="stSidebar"] [class*="st-key-menu_repasar_"] button {
            padding-left: 0;
            padding-right: 0;
        }
        /* Tighten the gap so the icon column keeps usable width. */
        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] {
            gap: 0.4rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def inject_responsive_css():
    """Touch-friendly sizing on narrow viewports; no-op visually on desktop widths."""
    st.markdown(
        """
        <style>
        @media (max-width: 768px) {
            div.stButton > button {
                min-height: 48px;
                font-size: 1.05rem;
                padding: 0.6rem 1rem;
            }
            div.stTextInput input {
                min-height: 44px;
                font-size: 1.05rem;
            }
            h1 { font-size: 1.6rem !important; }
            h2 { font-size: 1.3rem !important; }
            h3 { font-size: 1.1rem !important; }
            /* Streamlit stacks columns full-width on phones. For the small
               control rows in a drill (timer, Pausa/Resumen, the accent keys,
               Pista/No sé) that pushed the question and answer box off the
               screen, so keep containers keyed row_* on one line. */
            [class*="st-key-row_"] [data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                gap: 0.35rem !important;
            }
            [class*="st-key-row_"] [data-testid="stColumn"] {
                min-width: 0 !important;
            }
            [class*="st-key-row_"] button {
                padding-left: 0.2rem !important;
                padding-right: 0.2rem !important;
            }
            /* Rows of four stat tiles (progreso): two per line on a phone
               instead of one, so the page isn't a column of single numbers. */
            [class*="st-key-grid2_"] [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                gap: 0.5rem !important;
            }
            [class*="st-key-grid2_"] [data-testid="stColumn"] {
                min-width: calc(50% - 0.5rem) !important;
                flex: 1 1 calc(50% - 0.5rem) !important;
            }
            /* Narrow keys, but at least a full touch target tall. */
            [class*="st-key-row_accents"] button {
                min-height: 44px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def _set_active_command(cmd):
    st.session_state.active_command = cmd
    st.session_state.drill_active = False
    st.rerun()

def _on_typed_command(key):
    """on_change callback for the command text boxes. Acting once, on submit,
    and then clearing the box matters: reading the box on every rerun made a
    stale typed command override every button tapped afterwards, and typing
    a new !drill mid-drill kept serving the old drill's questions."""
    cmd = st.session_state.get(key, "").strip()
    if cmd:
        st.session_state.active_command = cmd
        st.session_state.drill_active = False
    st.session_state[key] = ""

def _render_button_grid(commands, columns, key_prefix):
    """Render a grid of drill/roleplay buttons. Drills whose module has a grammar
    concept to explain (see get_module_concept) also get a 📖 Repasar icon;
    pure-vocabulary drills and roleplay commands don't, since there's nothing to
    review beyond the quiz itself."""
    cols = st.columns(columns)
    for i, (label, cmd) in enumerate(commands):
        # Let long "A/B" labels wrap at the slash rather than mid-word.
        label = label.replace("/", "/\u200b")
        with cols[i % columns]:
            module = cmd.split(" ", 1)[1] if cmd.startswith("!drill ") else None
            has_concept = module is not None and get_module_concept(module) is not None
            if has_concept:
                bcol, rcol = st.columns([5, 1.5])
                with bcol:
                    if st.button(label, use_container_width=True, key=f"{key_prefix}_{cmd}"):
                        _set_active_command(cmd)
                with rcol:
                    if st.button("📖", use_container_width=True, key=f"{key_prefix}_repasar_{cmd}",
                                 help="Repasar (sin quiz, a tu ritmo)"):
                        _set_active_command(f"!repasar {module}")
            else:
                if st.button(label, use_container_width=True, key=f"{key_prefix}_{cmd}"):
                    _set_active_command(cmd)

def render_command_menu(columns=2):
    """Tap-friendly, categorized grid of drill/roleplay buttons. Sets st.session_state.active_command."""
    # On mobile the menu (and so this widget) isn't drawn during a drill, and
    # Streamlit drops an undrawn widget's state; restore it from the saved choice.
    if "duration_choice" not in st.session_state:
        saved = st.session_state.get("duration_override")
        st.session_state.duration_choice = next(k for k, v in DURATION_CHOICES.items() if v == saved)
    choice = st.selectbox("⏱️ Duración", list(DURATION_CHOICES), key="duration_choice")
    st.session_state.duration_override = DURATION_CHOICES[choice]
    pending = progress.due_count()
    if pending:
        st.caption(f"🔁 {pending} para repasar hoy")
    st.caption("📖 = Repasar (revisar sin cronómetro ni puntuación)")
    for category_name, commands in DRILL_CATEGORIES.items():
        st.markdown(f"#### {category_name}")
        _render_button_grid(commands, columns, key_prefix="menu")

    st.markdown("#### 🗣️ Conversación")
    _render_button_grid(HABLAR_COMMANDS, columns, key_prefix="menu")

    st.markdown("#### 🎭 Roleplay")
    _render_button_grid(ROL_COMMANDS, columns, key_prefix="menu")

_ARTICLES = ("el ", "la ", "los ", "las ", "un ", "una ")

def _expand_segment(seg):
    """Expand one '/'-bearing chunk of a vocab 'spanish' field into the list of
    literal forms it represents. Handles three shapes seen in the data:
    - masculine/a shorthand: 'cansado/a' -> ['cansado', 'cansada'],
      'controlador/a' -> ['controlador', 'controladora']
    - a reflexive suffix glued on: 'cortar(se)' -> ['cortarse']
    - a bare-slash alternate with no spaces: 'el apartamento/piso' -> both
    Anything else has a trailing descriptive parenthetical stripped, e.g.
    'el centro (de la ciudad)' -> ['el centro']."""
    seg = seg.strip()
    m = re.match(r"^(\S+)/a(\(s\))?$", seg)
    if m:
        masc = m.group(1)
        fem = masc[:-1] + "a" if masc.endswith("o") else masc + "a"
        return [masc, fem]
    m = re.match(r"^(\S+)\(se\)$", seg)
    if m:
        return [m.group(1) + "se"]
    if "/" in seg:
        return [p.strip() for p in seg.split("/") if p.strip()]
    seg = re.sub(r"\s*\([^)]*\)\s*$", "", seg).strip()
    return [seg] if seg else []

def split_alternates(raw):
    """Turn a vocab/grammar 'spanish' field into every form that should count
    as a correct answer, e.g. 'el esposo / la esposa' -> both genders,
    'gruñón / gruñona' -> both, 'aquí / acá' -> both, 'al lado (mío)' ->
    just 'al lado'. The first form returned is the canonical one to display."""
    if not raw:
        return [raw]
    segments = [s.strip() for s in raw.split(" / ") if s.strip()] or [raw.strip()]
    forms = []
    for seg in segments:
        forms.extend(_expand_segment(seg))
    if not forms:
        return [raw]
    article = next((a for a in _ARTICLES if forms[0].lower().startswith(a)), None)
    if article:
        forms = [f if any(f.lower().startswith(a) for a in _ARTICLES) else article + f for f in forms]
    seen, out = set(), []
    for f in forms:
        if f.lower() not in seen:
            seen.add(f.lower())
            out.append(f)
    return out

def _normalize_for_grading(s):
    """Lowercase and strip accents so grading doesn't fail on a missing á/ñ."""
    s = unicodedata.normalize("NFD", s.strip().lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def _loose(s):
    """Lowercase, collapse whitespace and drop ¿?¡!.,;: and [ ] — sentence
    answers shouldn't be marked wrong over a missing question mark, or for
    not typing the brackets of a placeholder like '¿Qué significa [tu nombre]?'.
    Accents are left alone so a missing tilde can still be flagged."""
    s = re.sub(r"[¿?¡!.,;:\[\]]", " ", s.strip().lower())
    return " ".join(s.split())

_SUBJECT_PRONOUNS = ("yo", "tú", "él", "ella", "usted", "nosotros", "nosotras", "ellos", "ellas", "ustedes")

def sentence_forms(raw):
    """Every acceptable rendering of a full-sentence target: expands 'honesto/a'
    and 'cambio/suelto' slash shorthand, and also accepts the sentence without
    its leading subject pronoun (Spanish drops it: 'Yo hablé' = 'Hablé')."""
    forms = [raw]
    # Expand each slash token in turn (a/b -> a, b; word/a -> masculine + feminine).
    for _ in range(4):
        expanded, changed = [], False
        for f in forms:
            m = re.search(r"(\w+)/(\w+)", f)
            if not m:
                expanded.append(f)
                continue
            changed = True
            first, second = m.group(1), m.group(2)
            if second == "a" and first.endswith("o"):
                second = first[:-1] + "a"
            for choice in (first, second):
                expanded.append(f[:m.start()] + choice + f[m.end():])
        forms = expanded
        if not changed:
            break
    out = list(forms)
    for f in forms:
        words = f.split(" ", 1)
        if len(words) == 2 and words[0].lower().strip("¿¡") in _SUBJECT_PRONOUNS:
            out.append(words[1])
    return list(dict.fromkeys(out))

def _expand_answer(text):
    if " " not in text and "/" not in text:
        return [text]
    # Keep the literal text too, so typing the shorthand ('honesto/a') still counts.
    return sentence_forms(text) + [text]

def accepted_forms_for(item):
    """All forms that count as correct. Items that spell out accepted_forms keep
    them; otherwise multi-word targets are expanded with sentence_forms. Data
    entries can list other right answers in "also_accepted" (tú as well as
    usted when the English doesn't say which, "voy en tren" as well as
    "voy en el tren"); the model answer shown stays the same."""
    forms = list(item["accepted_forms"]) if item.get("accepted_forms") else _expand_answer(item["target_form"])
    for alt in item.get("also_accepted", []):
        forms += _expand_answer(alt)
    return list(dict.fromkeys(forms))

def check_answer(user_answer, item):
    """Grade an answer against every accepted form for this item.

    Returns (is_correct, matched_form, needs_accent_fix). Accents and
    punctuation are forgiven so a missing tilde isn't scored as a wrong
    answer, but the match is reported back so the drill can still show the
    correctly accented spelling instead of quietly teaching the wrong one."""
    accepted = accepted_forms_for(item)
    typed = user_answer.strip()
    if not typed:
        return False, None, False

    for form in accepted:
        if _loose(typed) == _loose(form):
            return True, form, False

    normalized = _normalize_for_grading(_loose(typed))
    for form in accepted:
        if normalized == _normalize_for_grading(_loose(form)):
            return True, form, True

    return False, None, False

def is_correct_answer(user_answer, item):
    """Boolean-only view of check_answer, for callers that just need a verdict."""
    return check_answer(user_answer, item)[0]

def load_verbs():
    with open(VERBS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_grammar(filename):
    path = os.path.join(GRAMMAR_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_exercise(filename):
    path = os.path.join(EXERCISES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_vocabulary(filename):
    path = os.path.join(DATA_DIR, "vocabulary", filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_scenarios():
    with open(SCENARIOS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["scenarios"]

def _scenario_matches(s, tema_lower):
    return tema_lower in s["tema"].lower() or tema_lower in s["title"].lower() or tema_lower in s["id"].lower()

def _another_scenario(tema, current_id):
    """A different scenario on the same tema when there is one, else any other."""
    scenarios = load_scenarios()
    tema_lower = (tema or "default").lower().strip()
    same_tema = [s for s in scenarios if tema_lower != "default" and _scenario_matches(s, tema_lower)]
    pool = [s for s in (same_tema or scenarios) if s["id"] != current_id] or scenarios
    return random.choice(pool)

def find_scenario(tema):
    scenarios = load_scenarios()
    if not tema or tema == "default":
        return random.choice(scenarios)
    tema_lower = tema.lower().strip()
    # Match by tema, title, or id (partial match allowed)
    for s in scenarios:
        if _scenario_matches(s, tema_lower):
            return s
    return None

def get_pronombres_drill_items(count=15):
    """Generate double object pronoun drill items."""
    data = load_grammar("double_pronouns.json")
    combos = data["double_pronouns"]["combinations"]
    items = []
    sample = random.sample(combos, min(count, len(combos)))
    for c in sample:
        items.append({
            "id": len(items),
            "prompt": f"Combine indirect + direct object pronoun: {c['io']} + {c['do']} = ?",
            "target_form": c["combined"],
            "exercise_type": "double_pronoun",
            "explanation": f"{c['combined']} — {c['english_translation'] if 'english_translation' in c else c['english']}" + (f" (Note: {c['note']})" if 'note' in c else "")
        })
    return items

def get_stem_change_drill_items(count=15):
    """Generate stem-changing verb drill items, drawing each verb within a
    group at most once per session so a short drill doesn't repeat itself."""
    data = load_grammar("stem_changing_verbs.json")
    groups = data["stem_changing_present_tense"]
    items = []
    for group_key in ["grupo_1_e_ie", "grupo_2_e_i", "grupo_3_o_ue"]:
        group = groups[group_key]
        verb_list = group.get("verb_list", [])
        if not verb_list:
            continue
        sample = random.sample(verb_list, min(max(count // 3, 1), len(verb_list)))
        for v in sample:
            target = v["yo_form"]
            accepted = [target]
            if "(se)" in v["infinitive"]:
                # '(se)' marks the pronoun as optional: 'divierto' and 'me divierto'
                # are both right, whichever one the data happens to list.
                accepted.append(target[3:] if target.startswith("me ") else "me " + target)
            items.append({
                "id": len(items),
                "prompt": f"Conjugate '{v['infinitive']}' ({v['english']}) in the YO form. Pattern: {group['rule']}",
                "target_form": target,
                "accepted_forms": accepted,
                "exercise_type": "stem_change",
                "explanation": f"{group['name']}: {v['infinitive']} → {v['yo_form']}" + (f" ({v['note']})" if v.get("note") else "")
            })
    random.shuffle(items)
    return items[:count]

def get_imperfect_drill_items(count=15):
    """Generate imperfect vs preterite contrast drill items, drawing on both
    the dedicated practice sentences and the (much larger) worked-example set
    already authored under each of the 8 imperfect "uses" categories."""
    tense = load_grammar("imperfect_complete.json")["imperfect_tense"]
    items = []
    for p in tense["practice_sentences"]:
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish (imperfect): {p['english']} [Use type: {p['use_type']}]",
            "target_form": p["spanish"],
            "also_accepted": p.get("also_accepted", []),
            "exercise_type": "imperfect",
            "explanation": f"{p['spanish']} — {p['use_type']}"
        })
    for use in tense["uses"]:
        for ex in use["examples"]:
            items.append({
                "id": len(items),
                "prompt": f"Translate to Spanish (imperfect): {ex['english']} [Use type: {use['name']}]",
                "target_form": ex["spanish"],
                "also_accepted": ex.get("also_accepted", []),
                "exercise_type": "imperfect",
                "explanation": f"{ex['spanish']} — {ex.get('explanation', use['name'])}"
            })
    random.shuffle(items)
    return items[:count]

_PRETERITE_PERSONS = ["yo", "tú", "él_ella_usted", "nosotros", "ellos_ustedes"]

def get_preterite_drill_items(count=20):
    """Generate preterite (pasado simple) drill items covering regular -ar/-er/-ir
    verbs, fully irregular verbs (dar/ser/ir), the four strong-irregular-stem
    pattern groups, -car/-gar/-zar spelling-change verbs, and 3rd-person-only
    semi-irregular verbs."""
    data = load_grammar("preterite_complete.json")
    tense = data["preterite_tense"]
    items = []

    # Regular -ar/-er/-ir verbs
    reg = tense["regular_conjugation"]
    for v in reg["common_regular_verbs"]:
        infinitive, english = v["infinitive"], v["english"]
        person = random.choice(_PRETERITE_PERSONS)
        stem = infinitive[:-2]
        endings = reg["ar_endings"] if infinitive.endswith("ar") else reg["er_ir_endings"]
        target = stem + endings[person].lstrip("-")
        items.append({
            "id": len(items),
            "prompt": f"Conjugate '{infinitive}' ({english}) in preterite, {person} form.",
            "target_form": target,
            "exercise_type": "preterite_regular",
            "explanation": f"{infinitive} ({person}) → {target}. Regular {'-ar' if infinitive.endswith('ar') else '-er/-ir'} preterite ending."
        })

    # Completely irregular: dar, ser, ir
    for v in tense["grupo_completamente_irregulares"]["verbs"]:
        conj = v["conjugation"]
        person = random.choice(list(conj.keys()))
        items.append({
            "id": len(items),
            "prompt": f"Conjugate '{v['infinitive']}' ({v['english']}) in preterite, {person} form.",
            "target_form": conj[person],
            "exercise_type": "preterite_irregular",
            "explanation": f"{v['infinitive']} ({person}) → {conj[person]}. {v.get('note', '')}"
        })

    # Strong irregular verbs with a stem pattern (4 groups)
    patron = tense["verbos_patron_fuerte"]
    for group_key in ["grupo_1_uv", "grupo_2_i", "grupo_3_u", "grupo_4_j"]:
        group = patron[group_key]
        ellos_ending = group.get("ellos_ending", "ieron")
        for v in group["verbs"]:
            person = random.choice(_PRETERITE_PERSONS)
            if person == "él_ella_usted" and v.get("irregular_el_form"):
                target = v["irregular_el_form"]
            else:
                endings = {"yo": "e", "tú": "iste", "él_ella_usted": "o", "nosotros": "imos", "ellos_ustedes": ellos_ending}
                target = v["stem"] + endings[person]
            items.append({
                "id": len(items),
                "prompt": f"Conjugate '{v['infinitive']}' ({v['english']}) in preterite, {person} form.",
                "target_form": target,
                "exercise_type": "preterite_patron",
                "explanation": f"Irregular stem: {v['infinitive']} → {v['stem']}- ({person}: {target})" + (f". {v['note']}" if v.get("note") else "")
            })

    # Spelling-change verbs: -car/-gar/-zar, YO form only
    ortho = tense["verbos_ortograficos"]
    for key, change_desc in [("car_to_que", "c→qu"), ("gar_to_gue", "g→gu"), ("zar_to_ce", "z→c")]:
        group = ortho[key]
        verb = random.choice(group["verbs"])
        base = verb.replace("(se)", "")
        suffix = {"car_to_que": "qué", "gar_to_gue": "gué", "zar_to_ce": "cé"}[key]
        target = base[:-3] + suffix
        items.append({
            "id": len(items),
            "prompt": f"Conjugate '{verb}' in preterite, yo form. (Spelling change: {change_desc})",
            "target_form": target,
            "exercise_type": "preterite_ortografico",
            "explanation": f"{verb} → {target} (yo). Spelling change {change_desc} keeps the sound of the infinitive."
        })

    # Semi-irregular verbs: 3rd person only (e→i, o→u, i→y)
    semi = tense["verbos_semi_irregulares"]
    semi_pools = (
        semi["grupo_1_e_o"]["e_to_i"]["verbs"]
        + semi["grupo_1_e_o"]["o_to_u"]["verbs"]
        + semi["grupo_2_i_a_y"]["verbs"]
    )
    for v in random.sample(semi_pools, min(6, len(semi_pools))):
        person = random.choice(["él_ella_usted", "ellos_ustedes"])
        items.append({
            "id": len(items),
            "prompt": f"Conjugate '{v['infinitive']}' ({v['english']}) in preterite, {person} form.",
            "target_form": v[person],
            "exercise_type": "preterite_semi_irregular",
            "explanation": f"{v['infinitive']} is regular except in the 3rd person: {person} → {v[person]}."
        })

    random.shuffle(items)
    return items[:count]

def get_pluscuamperfecto_drill_items(count=10):
    """Generate pluscuamperfecto (past perfect) usage drill items."""
    data = load_grammar("pluscuamperfecto.json")
    uses = data["pluscuamperfecto"]["uses"]
    items = []
    for use in uses:
        for ex in use["examples"]:
            items.append({
                "id": len(items),
                "prompt": f"Translate to Spanish (pluscuamperfecto - {use['name']}): {ex['english']}",
                "target_form": ex["spanish"],
                "also_accepted": ex.get("also_accepted", []),
                "exercise_type": "pluscuamperfecto",
                "explanation": f"{ex['spanish']} — {ex.get('explanation', '')}"
            })
    random.shuffle(items)
    return items[:count]

def get_ejercicio_drill_items(count=15):
    """Generate fill-in-the-blank items from the homework exercise bank."""
    data = load_exercise("preterite_review.json")
    sections = data["exercise_set"]["sections"]
    items = []
    for section in sections:
        for it in section["items"]:
            items.append({
                "id": len(items),
                "prompt": it["prompt"].replace("___", "_____"),
                "target_form": it["answer"],
                "exercise_type": "ejercicio",
                "explanation": f"{it['infinitive']} → {it['answer']} — {it['english']}" + (f" ({it['note']})" if 'note' in it else "")
            })
    random.shuffle(items)
    return items[:count]

def _blank_out(sentence, word):
    """Replace the first whole-word, case-insensitive occurrence of `word` in
    `sentence` with a blank — used to turn a worked example into a fill-in-
    the-blank prompt without leaking the answer if the word isn't capitalized
    or isn't the first word."""
    return re.sub(rf"\b{re.escape(word)}\b", "___", sentence, count=1, flags=re.IGNORECASE)

def get_por_para_drill_items(count=15):
    """Generate POR vs PARA choice items from the practice sentences and idioms."""
    data = load_grammar("prepositions_por_para.json")
    ppp = data["por_vs_para"]
    items = []

    for use in ppp["para"]["uses"]:
        for key in ("example", "example2"):
            if key in use:
                items.append({
                    "id": len(items),
                    "prompt": f"Fill in POR or PARA: {_blank_out(use[key], 'para')}",
                    "target_form": "para",
                    "exercise_type": "por_para",
                    "explanation": f"{use['use']}: {use[key]} — {use.get('english', '')}"
                })
    for use in ppp["por"]["uses"]:
        items.append({
            "id": len(items),
            "prompt": f"Fill in POR or PARA: {_blank_out(use['example'], 'por')}",
            "target_form": "por",
            "exercise_type": "por_para",
            "explanation": f"{use['use']}: {use['example']} — {use['english']}"
        })
    for expr in ppp["para"]["idiomatic_expressions"]:
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish (uses PARA): {expr['english']}",
            "target_form": expr["spanish"],
            "also_accepted": expr.get("also_accepted", []),
            "exercise_type": "por_para",
            "explanation": f"{expr['spanish']} — {expr['english']}"
        })

    random.shuffle(items)
    return items[:count]

def get_demostrativos_drill_items(count=12):
    """Generate demonstrative (este/ese/aquel) and distance-adverb drill items."""
    data = load_grammar("demonstratives.json")
    d = data["demonstratives"]
    items = []

    for group_key in ["este_this", "ese_that"]:
        group = data["demonstratives"][group_key]
        for ex in group["examples"]:
            items.append({
                "id": len(items),
                "prompt": f"Translate to Spanish ({group['meaning']}): {ex['english']}",
                "target_form": ex["spanish"],
                "also_accepted": ex.get("also_accepted", []),
                "exercise_type": "demostrativos",
                "explanation": f"{ex['spanish']} — {ex.get('note', group['meaning'])}"
            })

    for pair in data["place_adverbs_pairs"]["pairs"]:
        forms = split_alternates(pair["spanish"])
        items.append({
            "id": len(items),
            "prompt": f"Which place adverb means '{pair['english']}' ({pair['distance']})?",
            "target_form": forms[0],
            "accepted_forms": forms,
            "exercise_type": "demostrativos",
            "explanation": f"{pair['spanish']} — {pair['english']} ({pair['distance']})"
        })

    random.shuffle(items)
    return items[:count]

def get_adverbios_drill_items(count=15):
    """Generate adverb translation items across cantidad/lugar/tiempo categories."""
    data = load_vocabulary("adverbs.json")
    items = []
    for category_key in ["adverbios_de_cantidad", "adverbios_de_lugar", "adverbios_de_tiempo"]:
        category = data[category_key]
        for w in category["words"]:
            forms = split_alternates(w["spanish"])
            items.append({
                "id": len(items),
                "prompt": f"Translate to Spanish ({category['english_category']}): {w['english']}",
                "target_form": forms[0],
                "accepted_forms": forms,
                "exercise_type": "adverbios",
                "explanation": f"{w['spanish']} — {w['english']}"
            })
    # The list has synonyms as separate entries ('outside' = afuera / fuera),
    # so merge them, or one of two right answers is graded wrong.
    items = merge_same_prompt(items)
    random.shuffle(items)
    return items[:count]

def merge_same_prompt(items):
    """Collapse items that ask the identical question into one that accepts
    every answer any of them had. Must run on the whole pool before sampling,
    since the synonyms may not both land in the sample."""
    merged = {}
    for item in items:
        if item["prompt"] not in merged:
            merged[item["prompt"]] = dict(item, accepted_forms=list(accepted_forms_for(item)))
            continue
        keep = merged[item["prompt"]]
        for form in accepted_forms_for(item):
            if form not in keep["accepted_forms"]:
                keep["accepted_forms"].append(form)
        keep["explanation"] += f" · {item.get('explanation', '')}"
    for i, item in enumerate(merged.values()):
        item["id"] = i
    return list(merged.values())

def get_adjetivos_drill_items(count=10):
    """Generate shortened-adjective (apocope) drill items: buen/bueno, mal/malo, etc."""
    data = load_grammar("adjectives.json")
    items = []
    for adj in data["shortened_adjectives"]["affected_adjectives"]:
        items.append({
            "id": len(items),
            "prompt": f"Shortened form of '{adj['full_form']}' ({adj['context']})?",
            "target_form": adj["shortened_form"],
            "exercise_type": "adjetivos",
            "explanation": f"{adj['full_form']} → {adj['shortened_form']} — {adj['example']} ({adj.get('english', '')})" + (f" {adj['note']}" if adj.get("note") else "")
        })
    random.shuffle(items)
    return items[:count]

def get_numeros_drill_items(count=15):
    """Generate number-writing drill items (digits -> Spanish words)."""
    data = load_vocabulary("numbers_and_money.json")
    numbers = data["numbers"]
    items = []
    pools = numbers["0_20"] + numbers["compound_21_30"]["examples"] + numbers["compound_31_plus"]["examples"] + numbers["hundreds"]
    for n in pools:
        items.append({
            "id": len(items),
            "prompt": f"Write this number in Spanish: {n['number']}",
            "target_form": n["spanish"],
            "also_accepted": n.get("also_accepted", []),
            "exercise_type": "numeros",
            "explanation": f"{n['number']} → {n['spanish']}" + (f" ({n['note']})" if 'note' in n else "")
        })
    random.shuffle(items)
    return items[:count]

def get_reflexivos_drill_items(count=12):
    """Generate reflexive verb drill items: pronoun choice (always mechanically
    correct regardless of stem changes) plus the fully-conjugated bañarse paradigm."""
    data = load_grammar("reflexive_verbs.json")
    rv = data["reflexive_verbs"]
    items = []

    pronoun_by_person = {
        "yo": "me", "tú": "te", "él/ella/usted": "se",
        "nosotros": "nos", "ellos/ellas/ustedes": "se"
    }
    verb_list = rv["common_reflexive_verbs"]
    combos = [(v, person) for v in verb_list for person in pronoun_by_person]
    for v, person in random.sample(combos, min(max(count - 4, 1), len(combos))):
        # 'sentarse' -> 'sentar', 'darse cuenta (de)' -> 'dar cuenta (de)'
        bare_verb = re.sub(r"se\b", "", v["spanish"], count=1)
        items.append({
            "id": len(items),
            "prompt": f"Which reflexive pronoun goes with '{person}' for '{v['spanish']}' ({v['english']})?",
            "target_form": pronoun_by_person[person],
            "exercise_type": "reflexivos",
            "explanation": f"{person} → {pronoun_by_person[person]} + {bare_verb}"
        })

    for person, details in rv["conjugation"].items():
        items.append({
            "id": len(items),
            "prompt": f"Conjugate 'bañarse' (to bathe) for '{person}' (pronoun + verb form).",
            "target_form": f"{details['pronoun']} {details['form']}",
            "exercise_type": "reflexivos",
            "explanation": f"{person}: {details['pronoun']} {details['form']}"
        })

    random.shuffle(items)
    return items[:count]

def get_participios_drill_items(count=15):
    """Generate irregular past participle drill items (perfect tense)."""
    data = load_grammar("perfect_complete.json")
    parts = data["perfect_tense"]["past_participles"]["irregular_participles"]
    items = []
    for p in parts:
        items.append({
            "id": len(items),
            "prompt": f"Irregular past participle of '{p['infinitive']}' ({p.get('english', '')})?",
            "target_form": p["participle"],
            "exercise_type": "participios",
            "explanation": f"{p['infinitive']} → {p['participle']} — {p.get('english', '')}"
                           + (f" ({p['note']})" if p.get("note") else ""),
        })
    random.shuffle(items)
    return items[:count]

def get_futuro_irregular_drill_items(count=12):
    """Generate irregular future/conditional stem drill items."""
    data = load_grammar("future_complete.json")
    stems = data["future_simple"]["irregular_stems"]
    items = []
    persons = [("yo", 0), ("tú", 1), ("él/ella/usted", 2), ("nosotros", 3), ("ellos/ustedes", 5)]
    for s in stems:
        forms = [f.strip() for f in s["example"].split(",")]
        explanation = f"{s['infinitive']} → {s['irregular_stem']} — e.g. {s['example']}"
        # Half the time ask for a full conjugated form: knowing the stem is
        # only useful once you can put the ending on it.
        if len(forms) == 6 and random.random() < 0.5:
            person, idx = random.choice(persons)
            items.append({
                "id": len(items),
                "prompt": f"Future tense of '{s['infinitive']}' ({s['english']}) — {person}?",
                "target_form": forms[idx],
                "exercise_type": "futuro_conjugado",
                "explanation": explanation,
            })
        else:
            items.append({
                "id": len(items),
                "prompt": f"Irregular future stem of '{s['infinitive']}' ({s['english']})?",
                "target_form": s["irregular_stem"].rstrip("-"),
                "exercise_type": "futuro_irregular",
                "explanation": explanation,
            })
    random.shuffle(items)
    return items[:count]

def get_estructuras_drill_items(count=15):
    """Generate verb+infinitive structure and common question drill items."""
    data = load_grammar("verb_infinitive_structures.json")
    items = []
    for q in data["common_questions"]:
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish: {q['english']}",
            "target_form": q["spanish"],
            "also_accepted": q.get("also_accepted", []),
            "exercise_type": "estructuras",
            "explanation": f"{q['spanish']} — {q['english']}" + (f" ({q['note']})" if 'note' in q else "")
        })
    random.shuffle(items)
    return items[:count]

def get_lugares_drill_items(count=15):
    """Generate places/locations vocabulary drill items."""
    data = load_vocabulary("places.json")
    places = data["places"]
    items = []
    for category_key in ["everyday_errands", "civic_institutional", "leisure_dining", "home_and_city_structure"]:
        for p in places[category_key]:
            forms = split_alternates(p["spanish"])
            items.append({
                "id": len(items),
                "prompt": f"Translate to Spanish: {p['english']}",
                "target_form": forms[0],
                "accepted_forms": forms,
                "exercise_type": "lugares",
                "explanation": f"{p['spanish']} — {p['english']}" + (f" ({p.get('gender', '')})" if p.get('gender') else "")
            })
    random.shuffle(items)
    return items[:count]

def get_rutina_drill_items(count=15):
    """Generate daily-routine present-tense drill items (yo form)."""
    data = load_grammar("present_tense_routine.json")
    ptr = data["present_tense_routine"]
    items = []
    for ex in ptr["source_examples"] + ptr["additional_routine_verbs"]:
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish (present tense, daily routine): {ex['english']}",
            "target_form": ex["spanish"],
            "also_accepted": ex.get("also_accepted", []),
            "exercise_type": "rutina",
            "explanation": f"{ex['spanish']} — {ex['infinitive']}" + (f" ({ex['note']})" if 'note' in ex else "")
        })
    random.shuffle(items)
    return items[:count]

def fill_blank(sentence, answer):
    """'Ayer yo ___ (dormir).' -> 'Ayer yo estaba durmiendo.': the blank and
    the verb hint after it, so the explanation reads as a real sentence."""
    return re.sub(r"___(\s*\([^)]*\))?", answer, sentence, count=1)

_TENSE_LABELS = {
    "presente": "presente",
    "imperfecto": "imperfecto",
    "preterito": "pretérito indefinido",
    "perfecto": "pretérito perfecto",
    "pluscuamperfecto": "pluscuamperfecto",
    "futuro": "futuro",
}

def get_estar_gerundio_drill_items(count=16):
    """Gerunds and the progressive tenses (estar + gerundio), from the "Notes
    on Grammar: The Gerund" lesson: present, future, and four kinds of past
    (estaba / estuve / he estado / había estado + gerundio). Three kinds of
    item, with every tense getting the same share:
    - the gerund on its own, mostly the irregular groups (o→u, i→y, e→i);
    - estar + gerundio for a given tense and person, one per tense;
    - a sentence with a blank, labelled with the tense to use."""
    d = load_grammar("estar_gerundio.json")["estar_gerundio"]
    tenses = list(_TENSE_LABELS)
    persons = list(d["estar_forms"]["presente"])
    irregular = [(verb, group) for group in d["irregular_groups"] for verb in group["verbs"]]
    # Some verbs have a perfectly good gerund but are (almost) never used in
    # the progressive: no "estaban prefiriendo". Drill their gerunds only.
    stative = set(d["not_used_with_estar"]["verbs"])
    progressive_verbs = [v for v in d["regular_verbs"] + [verb for verb, _ in irregular]
                         if v["infinitive"] not in stative]
    items = []

    def add(prompt, target, exercise_type, explanation, also=()):
        items.append({"id": len(items), "prompt": prompt, "target_form": target,
                      "exercise_type": exercise_type, "explanation": explanation,
                      "also_accepted": list(also)})

    # Gerund forms: three irregular, one regular.
    for verb, group in random.sample(irregular, 3):
        add(f"Gerundio de '{verb['infinitive']}' ({verb['english']})?", verb["gerund"], "gerundio_irregular",
            f"{verb['infinitive']} → {verb['gerund']}. Irregular {group['name']}: {group['rule']}")
    verb = random.choice(d["regular_verbs"])
    add(f"Gerundio de '{verb['infinitive']}' ({verb['english']})?", verb["gerund"], "gerundio_regular",
        f"{verb['infinitive']} → {verb['gerund']}. {d['formation']['ar']}; {d['formation']['er_ir']}")

    # estar + gerundio: one per tense.
    for tense in tenses:
        verb, person = random.choice(progressive_verbs), random.choice(persons)
        estar = d["estar_forms"][tense][person]
        add(f"Estar + gerundio en {_TENSE_LABELS[tense]}, {person}: '{verb['infinitive']}' ({verb['english']})",
            f"{estar} {verb['gerund']}", f"estar_gerundio_{tense}",
            f"{estar} (estar en {_TENSE_LABELS[tense]}) + {verb['gerund']}. {d['tense_notes'][tense]}")

    # Sentences: the rest, taken round-robin from the three tenses.
    by_tense = {t: random.sample([x for x in d["sentences"] if x["tense"] == t],
                                 sum(x["tense"] == t for x in d["sentences"])) for t in tenses}
    random.shuffle(tenses)
    while len(items) < count and any(by_tense.values()):
        for tense in tenses:
            if by_tense[tense] and len(items) < count:
                x = by_tense[tense].pop()
                add(f"Completa con estar + gerundio en {_TENSE_LABELS[tense]}: {x['sentence']}", x["answer"],
                    f"estar_gerundio_{tense}", f"{fill_blank(x['sentence'], x['answer'])} — {x['english']}",
                    x.get("also_accepted", []))

    random.shuffle(items)
    return items[:count]

_CONDITIONAL_PERSONS = [("yo", "ía"), ("tú", "ías"), ("él/ella/usted", "ía"), ("nosotros", "íamos"), ("ellos/ustedes", "ían")]

def get_condicional_drill_items(count=15):
    """Simple conditional (lessons 87-91): conjugated forms built the same way
    as the future (infinitive or irregular future stem + -ía endings), plus
    translations of the worked examples under each of its seven uses."""
    cond = load_grammar("conditional_complete.json")["conditional_simple"]
    regular = [v["infinitive"] for v in load_grammar("preterite_complete.json")["preterite_tense"]
               ["regular_conjugation"]["common_regular_verbs"]]
    items = []

    def add(prompt, target, exercise_type, explanation):
        items.append({"id": len(items), "prompt": prompt, "target_form": target,
                      "exercise_type": exercise_type, "explanation": explanation})

    for verb in random.sample(cond["irregular_stems"]["verbs"], 6):
        person, ending = random.choice(_CONDITIONAL_PERSONS)
        stem = verb["stem"].rstrip("-")
        add(f"Condicional de '{verb['infinitive']}' — {person}", stem + ending, "condicional_irregular",
            f"{verb['infinitive']} → {verb['stem']} (la misma raíz que el futuro) + -{ending} = {stem + ending}")
    for infinitive in random.sample(regular, 4):
        person, ending = random.choice(_CONDITIONAL_PERSONS)
        add(f"Condicional de '{infinitive}' — {person}", infinitive + ending, "condicional_regular",
            f"Regular: infinitivo completo + -{ending} = {infinitive + ending}")
    examples = [(use, ex) for use in cond["uses"] for ex in use.get("examples", [])]
    for use, ex in random.sample(examples, min(count - len(items), len(examples))):
        add(f"Translate to Spanish (condicional — {use['name']}): {ex['english']}", ex["spanish"],
            "condicional_uso", f"{ex['spanish']} — {ex.get('explanation', use['name'])}")
    random.shuffle(items)
    return items[:count]

def get_ser_estar_drill_items(count=15):
    """Ser, estar or hay in a sentence (lessons 8-10, 14), including the
    adjectives whose meaning changes with the verb (ser listo / estar listo)."""
    d = load_grammar("ser_estar.json")["ser_estar"]
    items = []
    for x in random.sample(d["sentences"], min(count, len(d["sentences"]))):
        verb = "hay" if x["use"].startswith("HAY") else "estar" if x["use"].startswith("ESTAR") else "ser"
        items.append({
            "id": len(items),
            "prompt": f"Ser, estar o hay: {x['sentence']}",
            "target_form": x["answer"],
            "exercise_type": f"ser_estar_{verb}",
            "explanation": f"{fill_blank(x['sentence'], x['answer'])} — {x['english']} ({x['use']})",
        })
    return items

def get_subjuntivo_drill_items(count=16):
    """Present subjunctive (Language Transfer tracks 69-85; not yet in the
    lessons beyond the command forms). Six form questions, mostly from the
    irregular groups, then ten sentences where the trigger decides the mood.
    About a third of those need the INDICATIVE (creo que tiene, cuando +
    habit): always answering subjunctive would teach the forms but not when
    to use them."""
    d = load_grammar("subjunctive.json")["subjunctive"]
    items = []

    def add(prompt, target, exercise_type, explanation):
        items.append({"id": len(items), "prompt": prompt, "target_form": target,
                      "exercise_type": exercise_type, "explanation": explanation})

    groups = {g["id"]: g for g in d["groups"]}
    askable = lambda v: not v.get("third_person_only")  # no "yo llueva"
    picks = [("regulares", random.choice([v for v in groups["regulares"]["verbs"] if askable(v)]))]
    irregular = [(g["id"], v) for g in d["groups"] if g["id"] != "regulares" for v in g["verbs"] if askable(v)]
    picks += random.sample(irregular, 5)
    for group_id, verb in picks:
        person = random.choice(d["persons"])
        add(f"Presente de subjuntivo de '{verb['infinitive']}' ({verb['english']}) — {person}",
            verb["forms"][person], "subjuntivo_formas",
            f"{groups[group_id]['name']}: {', '.join(verb['forms'].values())}. {groups[group_id]['rule']}")

    subj = [x for x in d["sentences"] if x["mood"] == "subjuntivo"]
    ind = [x for x in d["sentences"] if x["mood"] == "indicativo"]
    n_ind = min(len(ind), round((count - len(items)) * 0.3))
    for x in random.sample(subj, count - len(items) - n_ind) + random.sample(ind, n_ind):
        add(f"¿Subjuntivo o indicativo? {x['sentence']}", x["answer"],
            "subjuntivo_frase" if x["mood"] == "subjuntivo" else "indicativo_contraste",
            f"{fill_blank(x['sentence'], x['answer'])} — {x['english']} ({x['mood']}: {x['trigger']})")
    random.shuffle(items)
    return items[:count]

def get_ir_gerundio_drill_items(count=12):
    """Generate IR (conjugated) + gerundio drill items (action while in motion)."""
    data = load_grammar("ir_gerundio.json")
    ig = data["ir_gerundio"]
    items = []

    for ex in ig["source_examples"]:
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish (voy + gerundio — action while traveling): {ex['english']}",
            "target_form": ex["spanish"],
            "also_accepted": ex.get("also_accepted", []),
            "exercise_type": "ir_gerundio",
            "explanation": f"{ex['spanish']} — {ex['base_verb']} → {ex['gerund']}"
        })

    for ex in ig["additional_examples_other_persons"]:
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish (ir + gerundio, '{ex['person']}' form): {ex['english']}",
            "target_form": ex["spanish"],
            "also_accepted": ex.get("also_accepted", []),
            "exercise_type": "ir_gerundio",
            "explanation": f"{ex['spanish']} — {ex.get('use', 'simultaneous action while moving')}"
        })

    random.shuffle(items)
    return items[:count]

# Vocabulary files sampled by the mixed vocabulary drill: (filename, [top-level keys to pull entries from])
_VOCABULARIO_MIXTO_SOURCES = [
    ("household_and_rooms.json", ["rooms", "furniture_and_objects"]),
    ("family_and_people.json", ["family", "professions_and_roles", "titles_and_marital_status"]),
    ("body_and_health.json", ["body_parts", "health_and_symptoms"]),
    ("emotions_and_adjectives.json", ["emotions_and_states", "descriptive_adjectives", "colors"]),
    ("food_extended.json", ["food_items"]),
    ("clothing.json", ["clothing"]),
    ("nature_weather_animals.json", ["weather", "seasons", "nature", "animals"]),
    ("time_and_calendar.json", ["days_of_the_week", "time_expressions"]),
    ("misc_common_nouns.json", ["technology_and_money", "transportation", "other_common_nouns"]),
    ("additional_verbs.json", ["everyday_action_verbs", "story_and_emotion_verbs"]),
    ("class_notes_recent.json", ["casa_y_reparaciones", "naturaleza_y_animales", "comida_y_compras",
                                 "cuerpo_y_salud", "ciudad_y_direcciones", "tiempo_libre_y_trabajo",
                                 "verbos_y_expresiones"]),
]

def _lesson_vocabulario_pool():
    """Vocabulary extracted from the user's own lesson materials."""
    pool = []
    for filename, keys in _VOCABULARIO_MIXTO_SOURCES:
        data = load_vocabulary(filename)
        for key in keys:
            for entry in data[key]:
                pool.append((entry, key))
    return pool

def _common_vocabulario_pool():
    """General high-frequency Spanish vocabulary, independent of the lesson corpus."""
    data = load_vocabulary("common_words.json")
    pool = []
    for category_key, entries in data.items():
        if category_key.startswith("_"):
            continue
        for entry in entries:
            pool.append((entry, category_key))
    return pool

def get_vocabulario_drill_items(count=20, source="mio"):
    """Generate vocabulary drill items from lesson-specific words ("mio"),
    general high-frequency words not tied to the lessons ("comun"), or a
    combined pool of both ("mezcla")."""
    if source == "comun":
        pool = _common_vocabulario_pool()
    elif source == "mezcla":
        pool = _lesson_vocabulario_pool() + _common_vocabulario_pool()
    else:
        pool = _lesson_vocabulario_pool()

    items = []
    sample = random.sample(pool, min(count, len(pool)))
    for entry, category in sample:
        forms = split_alternates(entry["spanish"])
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish ({category.replace('_', ' ')}): {entry['english']}",
            "target_form": forms[0],
            "accepted_forms": forms,
            "exercise_type": f"vocabulario_{source}",
            "explanation": f"{entry['spanish']} — {entry['english']}" + (f" ({entry['gender']})" if entry.get('gender') else "")
        })
    return items[:count]

def get_indefinidos_drill_items(count=8):
    """Generate indefinite/negative pronoun drill items (alguien/nadie, algo/nada, etc.)."""
    data = load_grammar("indefinite_pronouns.json")
    ip = data["indefinite_and_negative_pronouns"]
    items = []
    for pair in ip["pairs"]:
        forms = split_alternates(pair["affirmative"])
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish: {pair['english_affirmative']}",
            "target_form": forms[0],
            "accepted_forms": forms,
            "exercise_type": "indefinidos",
            "explanation": f"{pair['affirmative']} ↔ {pair['negative']} — {pair['example_affirmative']}"
        })
        neg_forms = split_alternates(pair["negative"])
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish: {pair['english_negative']}",
            "target_form": neg_forms[0],
            "accepted_forms": neg_forms,
            "exercise_type": "indefinidos",
            "explanation": f"{pair['negative']} ↔ {pair['affirmative']} — {pair['example_negative']}"
        })
    random.shuffle(items)
    return items[:count]

def get_preposiciones_drill_items(count=12):
    """Generate drill items for the extended preposition set (contra, hacia,
    hasta, desde, según, tras, sin) plus idiomatic prepositional expressions."""
    data = load_grammar("prepositions_por_para.json")
    other = data["other_prepositions"]
    items = []

    for prep_key in ["contra", "hacia", "hasta", "desde", "según", "tras", "sin"]:
        p = other[prep_key]
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish (using '{prep_key}'): {p['english']}",
            "target_form": p["example"],
            "exercise_type": "preposiciones",
            "explanation": f"{prep_key} = {p['meaning']} — {p['example']}"
        })

    for expr in other["idiomatic_expressions_with_prepositions"]:
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish (idiom): {expr['english']}",
            "target_form": expr["spanish"],
            "also_accepted": expr.get("also_accepted", []),
            "exercise_type": "preposiciones",
            "explanation": f"{expr['spanish']} — {expr['english']}"
        })

    random.shuffle(items)
    return items[:count]

def initialize_session():
    """Initialize or reset session state."""
    if "drill_active" not in st.session_state:
        st.session_state.drill_active = False
        st.session_state.drill_module = None
        st.session_state.drill_start_time = None
        st.session_state.drill_items = []
        st.session_state.current_item_index = 0
        st.session_state.answers = []
        st.session_state.score = 0
        st.session_state.total_questions = 0

def get_imperative_drill_items(verbs_data, count=20):
    """Generate conjugation drill items focused on imperatives, sampling each
    (verb, person, polarity) combination at most once per session."""
    verbs = verbs_data["verbs"]
    persons = ["tú", "usted", "nosotros", "ustedes"]
    polarities = ["affirmative", "negative"]

    combos = []
    for verb in verbs:
        imperative_forms = verb["moods"]["imperative"]
        for polarity in polarities:
            for person in persons:
                target_form = imperative_forms.get(polarity, {}).get(person, "")
                if target_form:
                    combos.append((verb, person, polarity, target_form))

    items = []
    for verb, person, polarity, target_form in random.sample(combos, min(count, len(combos))):
        spanish_polarity = "afirmativo" if polarity == "affirmative" else "negativo"
        accepted = [target_form]
        if polarity == "negative" and target_form.lower().startswith("no "):
            # The prompt already says "negativo", so the bare verb form counts too.
            accepted.append(target_form[3:])
        items.append({
            "id": len(items),
            "prompt": f"Imperativo {spanish_polarity} de '{verb['infinitive']}' ({verb.get('translation', '')}) — {person}",
            "verb_infinitive": verb["infinitive"],
            "person": person,
            "polarity": polarity,
            "target_form": target_form,
            "accepted_forms": accepted,
            "exercise_type": f"imperativo_{spanish_polarity}",
            "explanation": f"The {person} {polarity} imperative of '{verb['infinitive']}' is '{target_form}'."
        })

    return items

# Every module name _build_drill_items understands, aliases included.
KNOWN_MODULES = {
    "mixto", "fallos", "imperativo", "pronombres", "stem_changes", "cambios", "imperfecto", "pasado",
    "preterito", "preterite", "pluscuamperfecto", "pluscuam", "ejercicio", "review111", "por_para",
    "porpara", "demostrativos", "distancias", "adverbios", "adjetivos", "numeros", "reflexivos",
    "participios", "futuro_irregular", "futuro", "estructuras", "preguntas", "lugares", "rutina",
    "ir_gerundio", "gerundio", "estar_gerundio", "progresivo", "condicional", "conditional",
    "ser_estar", "serestar", "subjuntivo", "subjunctive", "vocabulario", "comunes", "vocab_comun", "vocab_mezcla", "indefinidos",
    "preposiciones",
}

def _build_drill_items(module_type):
    """Generate the raw item list for a given module type."""
    if module_type == "imperativo":
        return get_imperative_drill_items(load_verbs())
    elif module_type == "pronombres":
        return get_pronombres_drill_items()
    elif module_type == "stem_changes" or module_type == "cambios":
        return get_stem_change_drill_items()
    elif module_type == "imperfecto" or module_type == "pasado":
        return get_imperfect_drill_items()
    elif module_type == "preterito" or module_type == "preterite":
        return get_preterite_drill_items()
    elif module_type == "pluscuamperfecto" or module_type == "pluscuam":
        return get_pluscuamperfecto_drill_items()
    elif module_type == "ejercicio" or module_type == "review111":
        return get_ejercicio_drill_items()
    elif module_type == "por_para" or module_type == "porpara":
        return get_por_para_drill_items()
    elif module_type == "demostrativos" or module_type == "distancias":
        return get_demostrativos_drill_items()
    elif module_type == "adverbios":
        return get_adverbios_drill_items()
    elif module_type == "adjetivos":
        return get_adjetivos_drill_items()
    elif module_type == "numeros":
        return get_numeros_drill_items()
    elif module_type == "reflexivos":
        return get_reflexivos_drill_items()
    elif module_type == "participios":
        return get_participios_drill_items()
    elif module_type == "futuro_irregular" or module_type == "futuro":
        return get_futuro_irregular_drill_items()
    elif module_type == "estructuras" or module_type == "preguntas":
        return get_estructuras_drill_items()
    elif module_type == "lugares":
        return get_lugares_drill_items()
    elif module_type == "rutina":
        return get_rutina_drill_items()
    elif module_type == "ir_gerundio" or module_type == "gerundio":
        return get_ir_gerundio_drill_items()
    elif module_type in ("estar_gerundio", "progresivo"):
        return get_estar_gerundio_drill_items()
    elif module_type in ("condicional", "conditional"):
        return get_condicional_drill_items()
    elif module_type in ("ser_estar", "serestar"):
        return get_ser_estar_drill_items()
    elif module_type in ("subjuntivo", "subjunctive"):
        return get_subjuntivo_drill_items()
    elif module_type == "vocabulario" or module_type == "comunes":
        return get_vocabulario_drill_items(source="mio")
    elif module_type == "vocab_comun":
        return get_vocabulario_drill_items(source="comun")
    elif module_type == "vocab_mezcla":
        return get_vocabulario_drill_items(source="mezcla")
    elif module_type == "indefinidos":
        return get_indefinidos_drill_items()
    elif module_type == "preposiciones":
        return get_preposiciones_drill_items()
    elif module_type == "fallos":
        return progress.due_items()
    else:
        return get_imperative_drill_items(load_verbs())

# Every topic the interleaved drill pulls from.
_MIXTO_MODULES = [
    "imperativo", "pronombres", "cambios", "pasado", "preterito", "pluscuam",
    "por_para", "demostrativos", "adjetivos", "reflexivos", "participios",
    "futuro", "estructuras", "rutina", "gerundio", "estar_gerundio", "condicional", "ser_estar", "subjuntivo", "indefinidos",
    "preposiciones", "adverbios", "lugares", "numeros", "vocabulario",
]

def get_mixto_drill_items(count=20):
    """Interleaved drill: one item each from many different topics, so no two
    consecutive questions share a rule. Blocked practice (20 preterite items in
    a row) lets you coast on the last answer's pattern; interleaving forces you
    to work out WHICH rule applies first, which is the part that actually
    transfers to speaking. The topic is revealed in the explanation afterwards,
    never in the prompt."""
    items = []
    for module_type in random.sample(_MIXTO_MODULES, min(len(_MIXTO_MODULES), count)):
        pool = _build_drill_items(module_type)
        if not pool:
            continue
        # Make the multiple-choice variants here, while the whole topic is at
        # hand: in the finished drill every item is from a different topic,
        # so the wrong options would be giveaways (a number vs. a verb).
        item = random.choice(_add_recognition_variants(pool))
        item["module"] = module_type
        item["explanation"] = f"[{module_type}] {item.get('explanation', '')}".strip()
        items.append(item)
    random.shuffle(items)
    return items[:count]

def _add_recognition_variants(items, fraction=0.3):
    """Turn a slice of the drill into multiple-choice questions, using other
    answers from the same drill as distractors.

    Two reasons this matters pedagogically: those distractors are minimal pairs
    by construction (same tense, same topic, e.g. pidió/pedió/pidío), so
    choosing between them trains the discrimination that free recall alone
    doesn't; and recognition is a lower rung than production, which gives
    material you've just met a rung to stand on instead of only ever facing the
    hardest possible format.

    Distractors only come from the same module, so a mixed review queue
    ('fallos') never offers a number as a wrong answer to a verb question."""
    candidates = [it for it in items if len(it["target_form"].split()) <= 3]
    forms_by_module = {}
    for it in candidates:
        forms_by_module.setdefault(it.get("module"), []).append(it["target_form"])
    forms_by_module = {m: list(dict.fromkeys(f)) for m, f in forms_by_module.items()}

    for item in random.sample(candidates, int(len(candidates) * fraction)):
        unique_forms = forms_by_module[item.get("module")]
        accepted = {_normalize_for_grading(_loose(a)) for a in accepted_forms_for(item)}
        distractors = [f for f in unique_forms if _normalize_for_grading(_loose(f)) not in accepted]
        if len(distractors) < 3:
            continue
        choices = _plausible_distractors(item["target_form"], distractors) + [item["target_form"]]
        random.shuffle(choices)
        item["choices"] = choices
    return items

def _plausible_distractors(target, pool, count=3, shortlist=8):
    """Pick wrong options that actually resemble the right one.

    Sampling the pool uniformly produces giveaways — asking for the yo form of
    'querer' against habló/vendí/recibiste is solvable by spotting the only
    yo-form, without knowing the verb. Ranking by string similarity instead
    surfaces same-person, same-ending, same-gender neighbours (quise vs. cupe
    vs. puse; la silla vs. la policía), so the question tests the contrast it
    claims to. The shortlist keeps some variety across sessions."""
    ranked = sorted(pool, key=lambda f: difflib.SequenceMatcher(None, target, f).ratio(), reverse=True)
    return random.sample(ranked[:max(shortlist, count)], count)

def get_drill_items(module_type):
    """Generate the item list for a module. Shared by the quiz runner and Repaso.

    Also renumbers ids, which matters because each generator numbers its own
    items from zero and the mixto drill combines several of them — duplicate
    ids would collide as Streamlit widget keys."""
    items = get_mixto_drill_items() if module_type == "mixto" else _build_drill_items(module_type)
    for i, item in enumerate(items):
        item["id"] = i
        item.setdefault("module", module_type)
    # mixto already made its variants per topic (see get_mixto_drill_items).
    return items if module_type == "mixto" else _add_recognition_variants(items)

def render_breakdown(answers):
    """Per-type tally of this session's answers, weakest first."""
    if not answers:
        return
    st.markdown("#### Por tipo de ejercicio")
    for label, (right, total) in progress.breakdown(answers).items():
        icon = "✅" if right == total else ("⚠️" if right * 2 >= total else "❌")
        st.markdown(f"- {icon} **{label.replace('_', ' ')}**: {right}/{total}")

def _render_timer(time_remaining, duration_seconds):
    minutes, seconds = divmod(int(time_remaining), 60)
    with st.container(key="row_timer"):
        col1, col2 = st.columns([3, 1], vertical_alignment="center")
        with col1:
            st.progress(max(0.0, time_remaining / duration_seconds))
        with col2:
            st.metric("Time Left", f"{minutes}:{seconds:02d}")

@st.fragment(run_every=1)
def _live_timer(duration_seconds):
    """Tick the countdown every second without rerunning the page, so the
    clock moves while you think and a half-typed answer is left alone. When
    time runs out, rerun the whole app once so the summary replaces the
    question; otherwise the drill only ended on your next click."""
    elapsed = (datetime.now() - st.session_state.drill_start_time).total_seconds()
    time_remaining = max(0, duration_seconds - elapsed)
    _render_timer(time_remaining, duration_seconds)
    if time_remaining <= 0:
        st.rerun(scope="app")

def run_drill(module_type="imperativo", duration_seconds=None):
    """Main drill runner. Length defaults to the module's own (MODULE_DURATIONS)
    unless the user picked a fixed length in the Duración selector."""
    initialize_session()

    if duration_seconds is None:
        duration_seconds = drill_duration(module_type, st.session_state.get("duration_override"))

    if st.session_state.drill_active:
        _resume_drill()  # back from Pausa/Resumen, where the clock was stopped
    else:
        st.session_state.pop("paused_at", None)

    # Header
    st.title("⚡ Spanish Drill")
    st.markdown(f"**Module:** `!drill {module_type}` | **Duration:** {duration_seconds // 60} minutes")

    # Initialize drill if not active
    if not st.session_state.drill_active:
        st.session_state.drill_active = True
        st.session_state.drill_module = module_type
        st.session_state.drill_start_time = datetime.now()
        st.session_state.drill_items = get_drill_items(module_type)
        st.session_state.current_item_index = 0
        st.session_state.answers = []
        st.session_state.score = 0
        st.session_state.total_questions = 0
        st.session_state.pending_feedback = None

        if not st.session_state.drill_items:
            st.session_state.drill_active = False
            st.info("✅ No hay nada pendiente de repasar ahora mismo. ¡Haz un drill y vuelve después!"
                    if module_type == "fallos" else "No hay elementos para este módulo.")
            return

    elapsed = (datetime.now() - st.session_state.drill_start_time).total_seconds()
    time_remaining = max(0, duration_seconds - elapsed)
    finished = time_remaining <= 0 or st.session_state.current_item_index >= len(st.session_state.drill_items)

    if finished:
        _render_timer(time_remaining, duration_seconds)
    else:
        _live_timer(duration_seconds)

    pausa_col, resumen_col = st.container(key="row_drill_tools").columns(2)
    with pausa_col:
        if st.button("⏸️ Pausa (explicar)", use_container_width=True):
            st.session_state.active_command = "!pausa"
            st.rerun()
    with resumen_col:
        if st.button("📋 Resumen", use_container_width=True):
            st.session_state.active_command = "!resumen"
            st.rerun()

    # Check if drill is complete
    if finished:
        st.success("✅ Drill Complete!")

        # Show summary
        st.subheader("📊 Session Summary")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Correct Answers", st.session_state.score)
        with col2:
            st.metric("Total Questions", st.session_state.total_questions)
        with col3:
            accuracy = (st.session_state.score / st.session_state.total_questions * 100) if st.session_state.total_questions > 0 else 0
            st.metric("Accuracy", f"{accuracy:.0f}%")

        render_breakdown(st.session_state.answers)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔄 Start New Drill", use_container_width=True):
                st.session_state.drill_active = False
                st.rerun()
        with col_b:
            missed = sum(1 for a in st.session_state.answers if not a["is_correct"] or a.get("hinted"))
            if st.button(f"📖 Repasar lo que fallé ({missed})", use_container_width=True, disabled=not missed):
                _set_active_command("!repasar fallos")

        return

    # Display current question
    if st.session_state.current_item_index < len(st.session_state.drill_items):
        item = st.session_state.drill_items[st.session_state.current_item_index]

        st.subheader(f"Question {st.session_state.current_item_index + 1} of {len(st.session_state.drill_items)}")

        st.markdown(f"### {item['prompt']}")

        pending = st.session_state.get("pending_feedback")

        if pending and pending.get("item_id") == item["id"]:
            # Feedback phase: show the result and wait for the user to move on,
            # at their own pace, instead of a hardcoded sleep.
            if pending.get("revealed"):
                st.info(f"🤷 La respuesta: **{pending['target_form']}**")
                if pending.get("explanation"):
                    st.caption(f"💡 {pending['explanation']}")
            elif pending["is_correct"] and pending.get("ai_review"):
                # Didn't match the model answer, but Claude judged it right.
                st.success("✅ ¡Correcto! Tu versión también vale.")
                st.caption(f"Respuesta modelo: {pending['target_form']}")
                if pending["ai_review"].get("feedback"):
                    st.info(f"🤖 {pending['ai_review']['feedback']}")
            elif pending["is_correct"]:
                st.success(f"✅ Correct! '{pending['target_form']}'")
                if pending.get("accent_fix"):
                    st.warning(f"✍️ Ojo con la tilde: se escribe **{pending['accent_fix']}**.")
                if pending.get("hinted"):
                    st.caption("💡 Con pista — volverá a salir en el repaso espaciado.")
            else:
                st.error(f"❌ Incorrect. The correct form is: '{pending['target_form']}'")
                diff = grading.word_diff(pending.get("user_answer", ""), pending["target_form"])
                if diff:
                    st.markdown(f"🔍 {diff}")
                if (pending.get("ai_review") or {}).get("feedback"):
                    st.info(f"🤖 {pending['ai_review']['feedback']}")
                if pending.get("explanation"):
                    st.info(f"💡 {pending['explanation']}")
            if pending.get("ai_unavailable"):
                st.caption("(No se pudo consultar a Claude; solo se comparó con la respuesta modelo.)")

            if st.button("➡️ Continuar", use_container_width=True):
                st.session_state.pending_feedback = None
                st.session_state.current_item_index += 1
                st.rerun()
            return

        # Answering phase
        answer_key = f"answer_{item['id']}"
        hint_key = f"hint_level_{item['id']}"
        hint_level = st.session_state.get(hint_key, 0)

        if item.get("choices"):
            # Recognition item: pick the right form out of same-topic near-misses.
            with st.form(key=f"answer_form_{item['id']}"):
                user_answer = st.radio("Elige la forma correcta:", item["choices"],
                                       index=None, key=f"choice_{item['id']}")
                submitted = st.form_submit_button("✅ Submit Answer", use_container_width=True)
            user_answer = user_answer or ""
        else:
            if hint_level:
                st.info(f"💡 Pista: `{make_hint(item['target_form'], hint_level)}`")
            # Wrapped in a form so pressing Enter submits it (Enter fires the
            # form's FIRST submit button, so Submit must come before the accents).
            # The accent keys are submit buttons too: a plain st.button outside
            # the form would rerun without the half-typed text, wiping it out.
            with st.form(key=f"answer_form_{item['id']}"):
                user_answer = st.text_input("Your answer:", key=answer_key)
                submitted = st.form_submit_button("✅ Submit Answer", use_container_width=True)
                accent_cols = st.container(key="row_accents").columns(len(ACCENT_KEYS))
                for col, ch in zip(accent_cols, ACCENT_KEYS):
                    with col:
                        st.form_submit_button(ch, use_container_width=True,
                                              on_click=_append_accent, args=(answer_key, ch))

        if submitted:
            is_correct, matched_form, needs_accent_fix = check_answer(user_answer, item)
            review, unavailable = None, False
            if not is_correct and user_answer.strip() and grading.eligible(item) and _chat_available():
                review = _claude_review(item, user_answer)
                unavailable = review is None
                if review:
                    is_correct = review["correct"]
            _record_answer(item, user_answer, is_correct, hinted=hint_level > 0,
                           accent_fix=matched_form if needs_accent_fix else None,
                           ai_review=review, ai_unavailable=unavailable)
            st.rerun()

        col2, col3 = st.container(key="row_answer_tools").columns(2)

        with col2:
            can_hint = not item.get("choices") and hint_level < len(item["target_form"]) - 1
            if st.button("💡 Pista (una letra más)", use_container_width=True, disabled=not can_hint):
                st.session_state[hint_key] = hint_level + 1
                st.rerun()

        with col3:
            # "I don't know" shows the answer and counts as a miss, so the item
            # lands in the review queue instead of silently disappearing.
            if st.button("🤷 No sé (mostrar)", use_container_width=True):
                _record_answer(item, "", False, revealed=True)
                st.rerun()

ACCENT_KEYS = ["á", "é", "í", "ó", "ú", "ñ", "ü", "¿", "¡"]

def _append_accent(answer_key, ch):
    """Form-button callback: runs after the form's typed text has landed in
    session state, and before the widget is re-created, so it may edit it."""
    st.session_state[answer_key] = st.session_state.get(answer_key, "") + ch

def make_hint(target, level):
    """Reveal the first `level` letters of the answer and mask the rest,
    keeping spaces and punctuation so the shape of the answer shows:
    make_hint('se lo', 1) -> 's_ __'."""
    out, shown = [], 0
    for ch in target:
        if ch.isalpha():
            out.append(ch if shown < level else "_")
            shown += 1
        else:
            out.append(ch)
    return "".join(out)

def _claude_review(item, answer):
    """Claude's verdict on a sentence that missed the model answer, cached per
    (model answer, typed answer) so a repeat answer costs no second call."""
    cache = st.session_state.setdefault("ai_verdicts", {})
    key = (item["target_form"], _normalize_for_grading(_loose(answer)))
    if key not in cache:
        with st.spinner("Revisando tu frase con Claude…"):
            verdict = grading.judge(conversation.get_client(_anthropic_secret()), item, answer)
        if verdict is None:
            return None  # don't cache failures; the next try may work
        cache[key] = verdict
    return cache[key]

def _record_answer(item, user_answer, is_correct, hinted=False, revealed=False, accent_fix=None,
                   ai_review=None, ai_unavailable=False):
    """Score one answer, log it for spaced repetition, and queue its feedback.
    An answer that needed a hint still scores, but goes to the review queue as
    a miss: getting there with help isn't the same as knowing it."""
    st.session_state.answers.append({
        "item_id": item["id"],
        "user_answer": user_answer,
        "correct_answer": item["target_form"],
        "is_correct": is_correct,
        "hinted": hinted,
        "exercise_type": item.get("exercise_type"),
        "module": item.get("module"),
    })
    progress.record_attempt(item, is_correct and not hinted)
    st.session_state.total_questions += 1
    if is_correct:
        st.session_state.score += 1
    st.session_state.pending_feedback = {
        "item_id": item["id"],
        "is_correct": is_correct,
        "revealed": revealed,
        "hinted": hinted,
        "target_form": item["target_form"],
        "explanation": item.get("explanation", ""),
        "accent_fix": accent_fix,
        "user_answer": user_answer,
        "ai_review": ai_review,
        "ai_unavailable": ai_unavailable,
    }

def get_module_concept(module_type):
    """Return {'overview': str, 'uses': [...]} explaining the grammar concept
    behind a module, pulled straight from the underlying grammar JSON (the
    lesson data already contains rule write-ups, not just drill items).
    Returns None for pure-vocabulary modules with no grammar rule to explain."""
    try:
        if module_type == "imperativo":
            d = load_grammar("imperative_complete.json")["imperative_system"]
            return {"overview": d["overview"], "uses": []}
        elif module_type == "pronombres":
            d = load_grammar("double_pronouns.json")["double_pronouns"]
            extra = d["key_rule_le_to_se"]
            ex = extra["examples"][0]
            overview = d["rule_summary"] + " " + extra["rule"]
            uses = [{"name": "Ejemplo", "description": f"{ex['correct']} — {ex['english']} (en vez de: {ex['wrong']})"}]
            return {"overview": overview, "uses": uses}
        elif module_type in ("stem_changes", "cambios"):
            d = load_grammar("stem_changing_verbs.json")["stem_changing_present_tense"]
            uses = [{"name": g["name"], "description": g["rule"]}
                    for g in [d["grupo_1_e_ie"], d["grupo_2_e_i"], d["grupo_3_o_ue"]]]
            return {"overview": d["overview"], "uses": uses}
        elif module_type in ("imperfecto", "pasado"):
            d = load_grammar("imperfect_complete.json")["imperfect_tense"]
            return {"overview": d["overview"], "uses": d["uses"]}
        elif module_type in ("preterito", "preterite"):
            d = load_grammar("preterite_complete.json")["preterite_tense"]
            patron = d["verbos_patron_fuerte"]
            semi = d["verbos_semi_irregulares"]
            uses = [
                {"name": "Verbos regulares", "description": "hablar → hablé/hablaste/habló/hablamos/hablasteis/hablaron. comer/vivir → -í/-iste/-ió/-imos/-isteis/-ieron.",
                 "example": "hablé", "english": "I spoke"},
                {"name": "Totalmente irregulares", "description": "dar, ser, ir don't follow any pattern and share no ending family with regular verbs.",
                 "example": "fui", "english": "I was / I went"},
                {"name": patron["grupo_1_uv"]["name"], "description": "estar, tener, andar: stem ends in -uv, then the shared endings -e/-iste/-o/-imos/-isteis/-ieron.",
                 "example": "estuve", "english": "I was (location/state)"},
                {"name": patron["grupo_2_i"]["name"], "description": "querer, venir, hacer: stem ends in -i (hacer's él/ella/usted form is the irregular 'hizo').",
                 "example": "quise", "english": "I wanted"},
                {"name": patron["grupo_3_u"]["name"], "description": "poner, poder, saber, caber, haber: stem ends in -u.",
                 "example": "supe", "english": "I found out / knew"},
                {"name": patron["grupo_4_j"]["name"], "description": patron["grupo_4_j"]["note"],
                 "example": "dijeron", "english": "they said"},
                {"name": "Cambios ortográficos (-car/-gar/-zar)", "description": "Spelling-only change in the YO form to keep the infinitive's sound: c→qu, g→gu, z→c.",
                 "example": "practiqué", "english": "I practiced"},
                {"name": semi["grupo_1_e_o"]["name"], "description": "e→i or o→u, but ONLY in the 3rd person (both singular and plural) — every other form is fully regular.",
                 "example": "pidió / durmieron", "english": "he asked for / they slept"},
                {"name": semi["grupo_2_i_a_y"]["name"], "description": semi["grupo_2_i_a_y"]["note"],
                 "example": "leyó / construyeron", "english": "he read / they built"},
            ]
            return {"overview": d["overview"], "uses": uses}
        elif module_type in ("pluscuamperfecto", "pluscuam"):
            d = load_grammar("pluscuamperfecto.json")["pluscuamperfecto"]
            return {"overview": d["overview"], "uses": d["uses"]}
        elif module_type in ("por_para", "porpara"):
            d = load_grammar("prepositions_por_para.json")["por_vs_para"]
            return {"overview": d["overview"], "uses": d["para"]["uses"] + d["por"]["uses"]}
        elif module_type in ("demostrativos", "distancias"):
            d = load_grammar("demonstratives.json")["demonstratives"]
            uses = []
            for key in ["este_this", "ese_that", "aquel_that_over_there"]:
                g = d.get(key)
                if g:
                    detail = f"Formas: {', '.join(g['forms'].values())}" if g.get("forms") else g.get("note", "")
                    uses.append({"name": g["meaning"], "description": detail})
            overview = ("Los demostrativos indican la distancia entre el hablante y el objeto: "
                        "this/these (aquí), that/those (ahí), that/those over there (allá).")
            return {"overview": overview, "uses": uses}
        elif module_type == "adjetivos":
            d = load_grammar("adjectives.json")["shortened_adjectives"]
            overview = d["rule"] + (" " + d["note"] if "note" in d else "")
            return {"overview": overview, "uses": []}
        elif module_type == "reflexivos":
            d = load_grammar("reflexive_verbs.json")["reflexive_verbs"]
            return {"overview": d["definition"], "uses": []}
        elif module_type == "participios":
            d = load_grammar("perfect_complete.json")["perfect_tense"]
            return {"overview": d["overview"], "uses": d["uses"]}
        elif module_type in ("futuro_irregular", "futuro"):
            d = load_grammar("future_complete.json")["future_simple"]
            return {"overview": d["overview"], "uses": d["uses"]}
        elif module_type in ("estructuras", "preguntas"):
            d = load_grammar("verb_infinitive_structures.json")["verb_infinitive_structures"]
            return {"overview": d["overview"], "uses": []}
        elif module_type == "rutina":
            d = load_grammar("present_tense_routine.json")["present_tense_routine"]
            return {"overview": d["overview"], "uses": [{"name": "Uso", "description": d["rule"]}]}
        elif module_type in ("ir_gerundio", "gerundio"):
            d = load_grammar("ir_gerundio.json")["ir_gerundio"]
            return {"overview": d["overview"], "uses": d["meaning_and_use"]}
        elif module_type in ("condicional", "conditional"):
            d = load_grammar("conditional_complete.json")["conditional_simple"]
            stems = ", ".join(f"{v['infinitive']} → {v['stem']}" for v in d["irregular_stems"]["verbs"])
            uses = [{"name": "Formación", "description": f"{d['construction']['rule']}. {d['construction']['note']}"},
                    {"name": "Raíces irregulares", "description": stems}] + d["uses"]
            return {"overview": d["overview"], "uses": uses}
        elif module_type in ("subjuntivo", "subjunctive"):
            d = load_grammar("subjunctive.json")["subjunctive"]
            uses = [{"name": "Formación", "description": d["construction"]}]
            for g in d["groups"]:
                sample = ", ".join(f"{v['infinitive']} → {v['forms']['yo']}" for v in g["verbs"][:6])
                uses.append({"name": g["name"], "description": f"{g['rule']} ({sample}...)"})
            uses += [{"name": f"Cuándo: {t['name']}", "description": t["examples"]} for t in d["triggers"]]
            return {"overview": d["overview"], "uses": uses}
        elif module_type in ("ser_estar", "serestar"):
            d = load_grammar("ser_estar.json")["ser_estar"]
            changes = "; ".join(f"{m['adjective']}: ser = {m['ser']}, estar = {m['estar']}" for m in d["meaning_change"])
            uses = d["uses"] + [{"name": "Cambian de significado", "description": changes}]
            return {"overview": d["overview"], "uses": uses}
        elif module_type in ("estar_gerundio", "progresivo"):
            d = load_grammar("estar_gerundio.json")["estar_gerundio"]
            uses = [{"name": "Formación (regular)", "description": f"{d['formation']['ar']}; {d['formation']['er_ir']}"}]
            for group in d["irregular_groups"]:
                pairs = ", ".join(f"{v['infinitive']} → {v['gerund']}" for v in group["verbs"])
                uses.append({"name": f"Irregulares {group['name']}", "description": f"{group['rule']} {pairs}"})
            uses.append({"name": "Sin forma progresiva", "description": d["not_used_with_estar"]["note"]})
            for tense, label in _TENSE_LABELS.items():
                forms = ", ".join(d["estar_forms"][tense].values())
                uses.append({"name": f"Estar + gerundio: {label}",
                             "description": f"{d['tense_notes'][tense]} (estar: {forms})"})
            return {"overview": f"{d['overview']} {d['construction']}", "uses": uses}
        elif module_type == "indefinidos":
            d = load_grammar("indefinite_pronouns.json")["indefinite_and_negative_pronouns"]
            return {"overview": d["overview"], "uses": []}
        elif module_type == "preposiciones":
            overview = ("Preposiciones adicionales (más allá de por/para), cada una con un "
                        "significado espacial, temporal o lógico específico.")
            return {"overview": overview, "uses": []}
        else:
            return None
    except (KeyError, IndexError, FileNotFoundError):
        return None

def _render_module_concept(module_type):
    """Render the grammar-concept explanation block at the top of Repaso, if this
    module has one (pure-vocabulary modules like números/lugares/vocabulario don't)."""
    concept = get_module_concept(module_type)
    if not concept:
        return
    st.markdown("### 📚 El concepto")
    st.markdown(concept["overview"])
    for use in concept.get("uses", []):
        title = use.get("name") or use.get("use") or ""
        spanish_name = use.get("spanish_name") or use.get("spanish_pattern") or ""
        desc = use.get("description") or use.get("explanation") or ""
        st.markdown(f"**• {title}**" + (f" _({spanish_name})_" if spanish_name else ""))
        if desc:
            st.caption(desc)
        examples = use.get("examples")
        example = examples[0] if examples else use
        sp = example.get("spanish") or example.get("example")
        en = example.get("english") or example.get("example_english")
        if sp:
            st.markdown(f"  *{sp}*" + (f" — {en}" if en else ""))
    _render_lt_tracks(module_type)
    st.markdown("---")

def _render_lt_tracks(module_type):
    """Which Language Transfer tracks explain this module's grammar."""
    try:
        tracks = external.tracks_for_module(module_type)
        links = external.load_lt()["_meta"]["links"]
    except (OSError, ValueError, KeyError):
        return
    if tracks:
        st.markdown(f"**🎧 Language Transfer:** pistas {external.ranges(tracks)} · "
                    f"[notas por pista]({links['track_notes']}) · [curso]({links['course']})")

def _render_repaso_entry(item, heading=None):
    """Render one item as a fully-visible bilingual explanation card — no
    hide/reveal, no right-or-wrong framing. Just the material laid out."""
    if heading:
        st.markdown(heading)
    st.caption(f"Contexto: {item['prompt']}")
    st.markdown(f"🇪🇸 **Español:** {item['target_form']}")
    if item.get("explanation"):
        st.markdown(f"📝 **Explicación:** {item['explanation']}")

def run_repaso(module_type="imperativo"):
    """Self-paced review: read through a module's material — Spanish, its
    English/grammar explanation, always fully visible. No timer, no typing,
    no scoring, no guess-then-reveal step — this is study material, not a quiz."""
    st.title("📖 Repaso")
    st.markdown(f"**Módulo:** `!repasar {module_type}`")

    _render_module_concept(module_type)

    items_key = f"repaso_items_{module_type}"
    # "fallos" mirrors the live review queue, so it must not be cached for the session.
    if items_key not in st.session_state or module_type == "fallos":
        st.session_state[items_key] = get_drill_items(module_type)
    items = st.session_state[items_key]

    if not items:
        st.warning("No hay elementos para repasar en este módulo.")
        return

    view = st.radio(
        "Vista:", ["🗂️ Una por una", "📋 Lista completa"],
        horizontal=True, key=f"repaso_view_{module_type}"
    )

    if view == "📋 Lista completa":
        for i, item in enumerate(items, start=1):
            _render_repaso_entry(item, heading=f"**{i}.**")
            st.markdown("---")
        return

    # One-at-a-time mode — everything visible immediately, just paged.
    idx_key = f"repaso_idx_{module_type}"
    st.session_state.setdefault(idx_key, 0)

    idx = st.session_state[idx_key] % len(items)
    item = items[idx]

    st.progress((idx + 1) / len(items))
    st.caption(f"{idx + 1} de {len(items)}")

    _render_repaso_entry(item)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Anterior", use_container_width=True):
            st.session_state[idx_key] = (idx - 1) % len(items)
            st.rerun()
    with col2:
        if st.button("Siguiente ➡️", use_container_width=True):
            st.session_state[idx_key] = (idx + 1) % len(items)
            st.rerun()

    if st.button("🔀 Barajar de nuevo"):
        st.session_state[items_key] = get_drill_items(module_type)
        st.session_state[idx_key] = 0
        st.rerun()

def run_rol(tema=None):
    """Show a scenario card and, when the Claude API is configured, run the
    roleplay right under it; otherwise the card is context to take to a
    chat with Claude."""
    st.title("🎭 Roleplay Scenario")

    # Pin the pick for this session: with no tema, find_scenario chooses at
    # random, and a fresh pick on every rerun would swap the scenario mid-chat.
    pin_key = f"rol_scenario_{tema}"
    if pin_key not in st.session_state:
        picked = find_scenario(tema)
        st.session_state[pin_key] = picked["id"] if picked else None
    scenario = next((s for s in load_scenarios() if s["id"] == st.session_state[pin_key]), None)

    if scenario is None:
        st.error(f"❌ No scenario found for tema '{tema}'.")
        all_scenarios = load_scenarios()
        temas = sorted(set(s["tema"] for s in all_scenarios))
        st.markdown("**Available temas:** " + ", ".join(f"`{t}`" for t in temas))
        return

    st.markdown(f"## {scenario['title']}")
    st.caption(f"Tema: {scenario['tema']} | Difficulty: {scenario['difficulty']} | Register: {scenario['persona']['formality']}")

    st.markdown("### 📍 Contexto")
    st.write(scenario["context"])

    st.markdown("### 🎭 Tu interlocutor/a")
    p = scenario["persona"]
    st.write(f"**{p['name']}** ({p['role']}) — {p['personality']}")

    st.markdown("### 🎯 Tu objetivo")
    st.write(scenario["user_objective"])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📚 Gramática objetivo")
        for g in scenario["target_grammar"]:
            st.markdown(f"- `{g}`")
    with col2:
        st.markdown("### 🗣️ Vocabulario clave")
        for v in scenario["required_vocabulary"]:
            st.markdown(f"- {v}")

    st.markdown("### ✅ Criterios de éxito")
    for c in scenario["success_criteria"]:
        st.markdown(f"- {c}")

    st.markdown("### 💬 Frase de apertura")
    st.info(f"**{p['name']}:** {scenario['opening_line']}")

    st.markdown("---")
    if _chat_available():
        st.markdown("### 🗣️ Conversación")
        _render_chat(f"chat_rol_{scenario['id']}", conversation.system_prompt(scenario))
    else:
        st.markdown(
            "**Cómo usar esta tarjeta:** copia la frase de apertura (o escribe `!rol " + scenario["tema"] +
            "`) en un chat con Claude y continuará el rol en español, corrigiendo tus errores al final "
            "de cada respuesta."
        )
        _chat_setup_help()

    if st.button("🔄 Otro escenario aleatorio"):
        st.session_state.pop(f"chat_rol_{scenario['id']}", None)
        st.session_state[pin_key] = _another_scenario(tema, scenario["id"])["id"]
        st.rerun()

_HABLAR_STARTERS = [
    "Cuéntame sobre tu día. ¿Qué has hecho hasta ahora?",
    "¿Qué planes tienes para el fin de semana?",
    "Describe tu comida favorita y por qué te gusta.",
    "Habla sobre un viaje que hiciste, o uno que quieres hacer.",
    "¿Cómo era tu rutina diaria cuando eras niño/a?",
    "Cuéntame sobre alguien importante en tu familia.",
    "¿Qué hiciste el fin de semana pasado?",
    "Si pudieras vivir en cualquier ciudad del mundo, ¿cuál elegirías y por qué?",
]

def run_hablar():
    """Freeform conversation partner. With Claude API credentials configured
    the conversation happens right here; otherwise this screen offers a topic
    to take to a chat with Claude."""
    st.title("🗣️ Compañero de Conversación")
    st.markdown(
        "Conversación libre en español, sin guion ni objetivo fijo: respuestas "
        "**100% en español**, de 2 a 4 frases, con tus errores corregidos al final."
    )

    idx_key = "hablar_starter_idx"
    st.session_state.setdefault(idx_key, random.randrange(len(_HABLAR_STARTERS)))
    topic = _HABLAR_STARTERS[st.session_state[idx_key]]

    if st.button("🔀 Otro tema (empieza de nuevo)"):
        st.session_state[idx_key] = random.randrange(len(_HABLAR_STARTERS))
        st.session_state.pop("chat_hablar", None)
        st.rerun()

    if _chat_available():
        # The topic is part of the system prompt, which must stay fixed for
        # the whole conversation, so changing it starts a new conversation.
        system = conversation.system_prompt() + f'\n\nYou opened the conversation by asking: "{topic}"'
        with st.chat_message("assistant"):
            st.markdown(topic)
        _render_chat("chat_hablar", system)
    else:
        st.markdown("### 💬 Si no sabes por dónde empezar")
        st.info(topic)
        st.markdown(
            "Copia el tema (o escribe el tuyo) en un chat con Claude y seguirá la "
            "conversación en español. Para algo más estructurado, usa `!rol [tema]`."
        )
        _chat_setup_help()

def _anthropic_secret():
    """ANTHROPIC_API_KEY from .streamlit/secrets.toml, if there is one."""
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:  # no secrets file at all
        return None

def _chat_available():
    return conversation.credentials_configured(_anthropic_secret())

def _chat_setup_help():
    with st.expander("💡 Chatear aquí mismo, sin salir de la app"):
        st.markdown(
            "La app puede llevar la conversación directamente si tiene acceso a la API de Claude:\n\n"
            "1. `pip install -r requirements.txt` (incluye el paquete `anthropic`).\n"
            "2. Pon tu clave en la variable de entorno `ANTHROPIC_API_KEY`, o en "
            "`.streamlit/secrets.toml` como `ANTHROPIC_API_KEY = \"...\"`.\n"
            "3. Reinicia la app.\n\n"
            "Cada mensaje es una llamada a la API, con su coste."
        )

def _render_chat(conv_key, system):
    """A chat thread stored in session state under conv_key. History is only
    ever appended to (see conversation.py for why); a failed turn drops the
    unanswered user message, which is the tail and so edits nothing earlier."""
    history = st.session_state.setdefault(conv_key, [])
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"] if msg["role"] == "user" else conversation.assistant_text(msg["content"]))

    prompt = st.chat_input("Escribe en español…")
    if history and st.button("🧹 Nueva conversación"):
        st.session_state.pop(conv_key, None)
        st.rerun()
    if not prompt:
        return

    history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    result = {}
    with st.chat_message("assistant"):
        try:
            client = conversation.get_client(_anthropic_secret())
            st.write_stream(conversation.stream_reply(client, system, history, result))
        except conversation.ChatError as e:
            history.pop()
            st.error(str(e))
            return
    history.append({"role": "assistant", "content": result["content"]})

def _pause_drill():
    """Stop the drill clock while a side screen (Pausa, Resumen) is open, so
    reading an explanation doesn't eat into the drill."""
    if st.session_state.get("drill_active") and not st.session_state.get("paused_at"):
        st.session_state.paused_at = datetime.now()

def _resume_drill():
    """Restart the clock where it stopped, by moving the start time forward
    by however long the drill was paused."""
    paused_at = st.session_state.pop("paused_at", None)
    if paused_at and st.session_state.get("drill_start_time"):
        st.session_state.drill_start_time += datetime.now() - paused_at

def run_pausa():
    """Step out of the current drill to see its grammar rule explained —
    reuses the same concept lookup that powers Repaso."""
    st.title("⏸️ Pausa")
    module_type = st.session_state.get("drill_module")

    if not module_type or not st.session_state.get("drill_active"):
        st.info(
            "No hay ningún drill activo ahora mismo. Empieza uno con "
            "`!drill [módulo]` y, mientras lo haces, escribe `!pausa` para "
            "salir del modo inmersión y ver la regla explicada en inglés."
        )
        return

    _pause_drill()
    st.caption(f"`!drill {module_type}` en pausa — el cronómetro se detiene mientras lees esto.")

    concept = get_module_concept(module_type)
    if concept:
        _render_module_concept(module_type)
    else:
        st.info(
            f"'{module_type}' es un módulo de vocabulario — no hay una regla "
            f"gramatical que explicar, solo palabras para repasar. Prueba "
            f"`!repasar {module_type}` para verlas todas con su traducción."
        )

    if st.button("▶️ Volver al drill"):
        st.session_state.active_command = f"!drill {module_type}"
        st.rerun()

def run_resumen():
    """End-of-session diagnostic: how the current drill has gone so far and
    which items to go back and review."""
    st.title("📋 Resumen de la Sesión")

    if not st.session_state.get("drill_active") or not st.session_state.get("answers"):
        st.info(
            "Todavía no has respondido ninguna pregunta en esta sesión. "
            "Empieza un drill con `!drill [módulo]`, contesta algunas "
            "preguntas, y luego escribe `!resumen` para ver tu progreso."
        )
        return

    _pause_drill()
    st.caption("⏸️ El cronómetro del drill está en pausa.")

    total = st.session_state.get("total_questions", 0)
    score = st.session_state.get("score", 0)
    accuracy = (score / total * 100) if total else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Correctas", score)
    with col2:
        st.metric("Total", total)
    with col3:
        st.metric("Precisión", f"{accuracy:.0f}%")

    render_breakdown(st.session_state.answers)

    misses = [a for a in st.session_state.answers if not a["is_correct"]]
    if misses:
        st.markdown("### ❌ Para repasar")
        for m in misses:
            shown_answer = m["user_answer"].strip() or "(en blanco)"
            st.markdown(f"- Tu respuesta: *{shown_answer}* → Correcta: **{m['correct_answer']}**")
    else:
        st.success("¡Sin errores todavía en esta sesión!")

    if st.button("▶️ Volver al drill"):
        st.session_state.active_command = f"!drill {st.session_state.drill_module}"
        st.rerun()

_DIRECTIONS = {"Español → inglés": "es_en", "Inglés → español": "en_es", "Mezcla": "mix"}
_DECK_SIZES = {"10": 10, "20": 20, "30": 30, "Todas": 0}

def _start_flashcards(card_ids, direction):
    st.session_state.fc = {
        "queue": list(card_ids),
        "dirs": {cid: (random.choice(["es_en", "en_es"]) if direction == "mix" else direction) for cid in card_ids},
        "missed": [],        # ids marked "otra vez" at least once, in order
        "done": 0,
        "total": len(card_ids),
        "flips": 0,          # bumps the card's checkbox id, so each new card starts face up
    }

def run_tarjetas():
    """Flashcards over the vocabulary from the class screenshots (one deck per
    topic file). Tap the card to flip it, then say whether you knew it: a
    miss comes back a few cards later in the same session, and every answer
    goes into the spaced-repetition log, so missed words also show up in
    "!drill fallos" and the review counter."""
    st.title("🃏 Tarjetas")
    cards = {c["id"]: c for c in flashcards.load_cards()}
    session = st.session_state.get("fc")

    if session is None:
        first, last = flashcards.lesson_range(cards.values())
        st.caption(f"{len(cards):,} palabras y frases de tus clases (lecciones {first}–{last}).".replace(",", "."))
        pool = list(cards.values())
        counts = flashcards.decks(pool)
        if st.radio("Elegir por", ["Tema", "Lección"], horizontal=True) == "Tema":
            # Empty means every topic, so the picker starts as one line, not 37 chips.
            chosen = st.multiselect("Temas", list(counts), placeholder="Todos los temas (o elige algunos)",
                                    format_func=lambda d: f"{flashcards.deck_label(d)} ({counts[d]})") or list(counts)
        else:
            # Default to the last ten lessons: the newest vocabulary.
            lo, hi = st.slider("Lecciones", first, last, (max(first, last - 9), last))
            pool = [c for c in pool if c["lesson_num"] is not None and lo <= c["lesson_num"] < hi + 1]
            chosen = list(counts)
            st.caption(f"{len(pool)} palabras y frases aparecieron por primera vez en las lecciones {lo}–{hi}.")
        c1, c2 = st.container(key="row_fc_setup").columns(2)
        direction = c1.radio("Dirección", list(_DIRECTIONS), index=0)
        size = c2.radio("Tarjetas", list(_DECK_SIZES), index=1, horizontal=True)
        due_first = st.checkbox("Primero las que tengo pendientes de repaso", value=True)
        if st.button("🃏 Empezar", use_container_width=True, disabled=not pool):
            due = progress.due_keys() if due_first else set()
            key_of = lambda c: progress.card_key(flashcards.quiz_item(c, split_alternates))
            deck = flashcards.build_deck(pool, set(chosen), _DECK_SIZES[size], due, key_of)
            _start_flashcards([c["id"] for c in deck], _DIRECTIONS[direction])
            st.rerun()
        return

    queue = [cid for cid in session["queue"] if cid in cards]  # tolerate edited data files
    session["queue"] = queue
    if not queue:
        total, missed = session["total"], session["missed"]
        st.success(f"✅ ¡Mazo terminado! {total - len(missed)} de {total} a la primera.")
        if missed:
            st.markdown("### 🔁 Para repasar")
            for cid in missed:
                if cid in cards:
                    st.markdown(f"- **{cards[cid]['spanish']}** — {cards[cid]['english']}")
        a, b = st.container(key="row_fc_end").columns(2)
        if missed and a.button(f"🔁 Otra vez las falladas ({len(missed)})", use_container_width=True):
            _start_flashcards([cid for cid in missed if cid in cards],
                              "mix" if len(set(session["dirs"].values())) > 1 else next(iter(session["dirs"].values())))
            st.rerun()
        if b.button("🃏 Nuevo mazo", use_container_width=True):
            st.session_state.pop("fc", None)
            st.rerun()
        return

    card = cards[queue[0]]
    st.progress(session["done"] / session["total"])
    st.caption(f"{flashcards.deck_label(card['deck'])} · {session['done']} de {session['total']} sabidas · quedan {len(queue)}")
    # variant alternates per card so the browser can't reuse the previous
    # card's (ticked) checkbox; see flashcards.card_html.
    st.markdown(flashcards.CARD_CSS + flashcards.card_html(card, session["dirs"][card["id"]],
                                                           f"fc-flip-{session['flips']}", session["flips"]),
                unsafe_allow_html=True)

    again, knew = st.container(key="row_fc_grade").columns(2)
    if again.button("🔁 Otra vez", use_container_width=True):
        progress.record_attempt(flashcards.quiz_item(card, split_alternates), False)
        if card["id"] not in session["missed"]:
            session["missed"].append(card["id"])
        flashcards.requeue(queue, 0)
        session["flips"] += 1
        st.rerun()
    if knew.button("✅ Lo sabía", use_container_width=True):
        progress.record_attempt(flashcards.quiz_item(card, split_alternates), True)
        queue.pop(0)
        session["done"] += 1
        session["flips"] += 1
        st.rerun()
    if st.button("⏹ Terminar"):
        st.session_state.pop("fc", None)
        st.rerun()

def _lt_progress_file():
    return external.progress_path(progress.db_path())

def _toggle_lt_track(track, key):
    """Checkbox callback: save the tick right away, so it survives a restart."""
    path = _lt_progress_file()
    done = external.load_done(path)
    (done.add if st.session_state[key] else done.discard)(track)
    if not external.save_done(path, done):
        st.session_state["lt_save_failed"] = True

def run_lt():
    """Listening tracker for Language Transfer – Complete Spanish: the 90
    tracks with the topics each teaches, ticked off as you listen. Ticks are
    saved to data/progress/lt_progress.json, not just the session."""
    st.title("🎧 Language Transfer")
    data = external.load_lt()
    links = data["_meta"]["links"]
    done = external.load_done(_lt_progress_file())
    tracks = data["tracks"]
    nxt = external.next_track(done, len(tracks))
    st.progress(len(done) / len(tracks))
    st.markdown(f"**{len(done)} / {len(tracks)} pistas**" + (f" · siguiente: **{nxt}**" if nxt else " · ¡curso completo! 🎉"))
    st.caption(f"[Curso gratis]({links['course']}) · [Notas por pista]({links['track_notes']}) · "
               f"[Transcripción (PDF)]({links['transcript']})")
    if st.session_state.pop("lt_save_failed", False):
        st.warning("No se pudo guardar el progreso en el disco.")

    gaps_only = st.toggle("Solo pistas con temas que tus clases aún no han visto")
    if gaps_only:
        st.caption("Para escuchar antes de que lleguen a clase: subjuntivo, 'would have', 'what if', se, gustar…")
    for start in range(0, len(tracks), 10):
        block = [t for t in tracks[start:start + 10] if not gaps_only or external.is_gap_track(t, data)]
        if not block:
            continue
        first, last = tracks[start]["track"], tracks[min(start + 9, len(tracks) - 1)]["track"]
        ticked = sum(1 for t in block if t["track"] in done)
        with st.expander(f"Pistas {first}–{last} ({ticked}/{len(block)})", expanded=nxt is not None and first <= nxt <= last):
            for t in block:
                labels = external.topic_labels(t, data) or [t.get("kind", "")]
                title = t["title"] or " · ".join(label for label in labels if label)
                badge = " 🆕" if external.is_gap_track(t, data) else ""
                key = f"lt_{t['track']}"
                st.session_state[key] = t["track"] in done
                st.checkbox(f"**{t['track']}** — {title}{badge}", key=key,
                            on_change=_toggle_lt_track, args=(t["track"], key))
    st.caption("🆕 = tema que tus clases todavía no han cubierto.")

def _module_label(module):
    """'preterito' -> '📜 Pretérito irregular', using the menu's own labels."""
    for label, cmd in DRILL_COMMANDS:
        if cmd in (f"!drill {module}", f"!{module}"):
            return label
    return module.replace("_", " ")

def run_progreso():
    """Long-term view built from the attempt log: streak, weekly accuracy,
    daily volume, where cards sit in the Leitner boxes, and per-topic accuracy
    with the weakest topics first."""
    st.title("📈 Mi progreso")
    data = progress.stats()
    if data is None:
        st.warning("No se pudo leer el registro de progreso.")
        return
    if not data["total"]:
        st.info("Todavía no hay intentos registrados. Haz un drill y vuelve aquí.")
        return

    week_right, week_total = data["week"]
    prev_right, prev_total = data["prev_week"]
    week_pct = 100 * week_right / week_total if week_total else None
    prev_pct = 100 * prev_right / prev_total if prev_total else None

    c1, c2, c3, c4 = st.container(key="grid2_stats").columns(4)
    c1.metric("🔥 Racha", f"{data['streak']} {'día' if data['streak'] == 1 else 'días'}")
    c2.metric("Intentos", data["total"])
    c3.metric("Precisión (7 días)", f"{week_pct:.0f}%" if week_pct is not None else "—",
              delta=f"{week_pct - prev_pct:+.0f} pts vs. semana anterior"
              if week_pct is not None and prev_pct is not None else None)
    c4.metric("Para repasar hoy", data["due"])
    if data["due"] and st.button(f"🔁 Repasar ahora ({data['due']})", use_container_width=True):
        _set_active_command("!drill fallos")

    st.markdown("### 🔁 Repaso espaciado")
    boxes = data["boxes"]
    b1, b2, b3, b4 = st.container(key="grid2_boxes").columns(4)
    b1.metric("Por repasar", boxes.get(0, 0), help="Fallado la última vez: vuelve enseguida.")
    b2.metric("Aprendiendo", boxes.get(1, 0), help="Un acierto: vuelve en 1 día.")
    b3.metric("Consolidando", boxes.get(2, 0), help="Dos aciertos seguidos: vuelve en 1 semana.")
    b4.metric("Dominadas", boxes.get(3, 0), help="Tres o más aciertos seguidos: cada 2 semanas.")

    st.markdown("### 📅 Intentos por día (últimas 2 semanas)")
    st.bar_chart({"Día": [d.strftime("%d/%m") for d, _ in data["daily"]],
                  "Intentos": [n for _, n in data["daily"]]},
                 x="Día", y="Intentos", height=220)

    st.markdown("### 📚 Por tema (lo más flojo primero)")
    st.dataframe(
        {
            "Tema": [_module_label(m) for m, _, _, _ in data["by_module"]],
            "Precisión": [round(100 * c / t) for _, c, t, _ in data["by_module"]],
            "Aciertos": [f"{c}/{t}" for _, c, t, _ in data["by_module"]],
            "Última vez": [last.strftime("%d/%m") for _, _, _, last in data["by_module"]],
        },
        hide_index=True,
        use_container_width=True,
        column_config={"Precisión": st.column_config.ProgressColumn(
            "Precisión", min_value=0, max_value=100, format="%d%%")},
    )

def parse_command(command_input):
    """Parse CLI-style commands."""
    parts = command_input.strip().split()

    if not parts:
        return None

    if parts[0] in ("!drill", "!repasar"):
        # 'Pretérito' -> 'preterito', so a capital or an accent isn't a typo.
        module = _normalize_for_grading(parts[1]) if len(parts) > 1 else "imperativo"
        return (parts[0][1:], module)
    elif parts[0] == "!hablar":
        return ("hablar", None)
    elif parts[0] == "!rol":
        tema = " ".join(parts[1:]) if len(parts) > 1 else "default"
        return ("rol", tema)
    elif parts[0] == "!pausa":
        return ("pausa", None)
    elif parts[0] == "!resumen":
        return ("resumen", None)
    elif parts[0] == "!progreso":
        return ("progreso", None)
    elif parts[0] == "!tarjetas":
        return ("tarjetas", None)
    elif parts[0] == "!lt":
        return ("lt", None)

    return None

def dispatch_command(command_str):
    """Run whichever command string is active (from typing or a button tap)."""
    parsed = parse_command(command_str)

    if not parsed:
        st.error("❌ Command not recognized. Try: `!drill imperativo`")
        return

    command_type, arg = parsed

    if command_type in ("drill", "repasar") and arg not in KNOWN_MODULES:
        # Without this an unknown name silently ran the imperative drill under
        # the typo's header, and logged its answers under the typo too.
        st.error(f"❌ No existe el módulo `{arg}`.")
        st.markdown("**Módulos:** " + ", ".join(f"`{cmd.split()[1]}`" for _, cmd in DRILL_COMMANDS
                                                if cmd.startswith("!drill ")))
        return

    if command_type == "drill":
        run_drill(module_type=arg)
    elif command_type == "repasar":
        run_repaso(module_type=arg)
    elif command_type == "hablar":
        run_hablar()
    elif command_type == "rol":
        run_rol(tema=arg)
    elif command_type == "pausa":
        run_pausa()
    elif command_type == "resumen":
        run_resumen()
    elif command_type == "progreso":
        run_progreso()
    elif command_type == "tarjetas":
        run_tarjetas()
    elif command_type == "lt":
        run_lt()

def render_landing():
    st.markdown("""
    # 🚀 Spanish Learning System

    Welcome to your personalized B1→B2 Spanish learning environment.

    ## Module Overview

    - **Imperatives** — Formal/informal commands, clitic attachment
    - **Pronoun Mechanics** — Direct/indirect object pronouns, reflexives
    - **Aspect & Tense** — Preterite vs. Imperfect storytelling
    - **Vocabulary** — Thematic word lists by domain
    - **Scenarios** — Real-world roleplay with task objectives
    - **Readings** — Annotated short stories and dialogues
    """)

def main():
    """Main entrypoint. Layout adapts to device: a tap-friendly button menu
    on mobile (iOS/Android), a compact CLI-style sidebar on desktop."""
    mobile = is_mobile()

    st.set_page_config(
        page_title="Spanish Learning System",
        page_icon="🎯",
        layout="centered" if mobile else "wide",
    )
    inject_responsive_css()

    if "active_command" not in st.session_state:
        st.session_state.active_command = None

    if mobile:
        # During an activity the page has its own title; a second one above
        # it only pushes the question further down a phone screen.
        if not st.session_state.active_command:
            st.title("🎯 Spanish Learning System")

        if st.session_state.active_command:
            if st.button("🏠 Home", use_container_width=True):
                st.session_state.active_command = None
                st.session_state.drill_active = False
                st.rerun()
            dispatch_command(st.session_state.active_command)
        else:
            render_landing()
            render_command_menu(columns=1)

            with st.expander("⌨️ Advanced: type a command"):
                st.text_input("Command:", placeholder="!drill imperativo", key="mobile_typed_cmd",
                              on_change=_on_typed_command, args=("mobile_typed_cmd",))

    else:
        inject_wide_sidebar_css()
        st.sidebar.title("🎯 Spanish Learning System")

        if st.session_state.active_command:
            if st.sidebar.button("🏠 Home"):
                st.session_state.active_command = None
                st.session_state.drill_active = False
                st.rerun()

        st.sidebar.markdown("**Quick Commands:**")
        with st.sidebar:
            render_command_menu(columns=2)

        st.sidebar.markdown("---")
        st.sidebar.text_input("Or type a command:", placeholder="!drill imperativo", key="desktop_typed_cmd",
                              on_change=_on_typed_command, args=("desktop_typed_cmd",))

        if st.session_state.active_command:
            dispatch_command(st.session_state.active_command)
        else:
            render_landing()

if __name__ == "__main__":
    main()
