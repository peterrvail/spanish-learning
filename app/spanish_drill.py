import streamlit as st
import json
import random
import time
from datetime import datetime, timedelta
import os

# Load data
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
VERBS_FILE = os.path.join(DATA_DIR, "verbs", "verbs.json")
GRAMMAR_DIR = os.path.join(DATA_DIR, "grammar")
SCENARIOS_FILE = os.path.join(DATA_DIR, "scenarios", "scenarios.json")
EXERCISES_DIR = os.path.join(DATA_DIR, "exercises")

# Commands available from both the mobile button menu and the desktop sidebar
DRILL_CATEGORIES = {
    "Verbos y Tiempos": [
        ("⚡ Imperativo", "!drill imperativo"),
        ("🔄 Cambios de raíz", "!drill cambios"),
        ("⏳ Pasado (imperfecto)", "!drill pasado"),
        ("📜 Pretérito irregular", "!drill preterito"),
        ("⏮ Pluscuamperfecto", "!drill pluscuam"),
        ("🔮 Futuro irregular", "!drill futuro"),
        ("✅ Participios", "!drill participios"),
        ("📝 Ejercicio (homework)", "!drill ejercicio"),
    ],
    "Gramática": [
        ("🔀 Pronombres dobles", "!drill pronombres"),
        ("↔️ Por vs. Para", "!drill por_para"),
        ("👉 Demostrativos", "!drill demostrativos"),
        ("🔤 Adjetivos cortos", "!drill adjetivos"),
        ("🪞 Reflexivos", "!drill reflexivos"),
        ("🗣️ Estructuras + preguntas", "!drill estructuras"),
    ],
    "Vocabulario": [
        ("🔢 Números", "!drill numeros"),
        ("🧭 Adverbios", "!drill adverbios"),
        ("📍 Lugares", "!drill lugares"),
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

def is_mobile():
    """Detect iOS/mobile via the request's User-Agent (server-side, no JS needed)."""
    try:
        ua = st.context.headers.get("User-Agent", "") or ""
    except Exception:
        ua = ""
    ua = ua.lower()
    return any(token in ua for token in ["iphone", "ipad", "ipod", "android", "mobile"])

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
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def _render_button_grid(commands, columns, key_prefix):
    cols = st.columns(columns)
    for i, (label, cmd) in enumerate(commands):
        with cols[i % columns]:
            if st.button(label, use_container_width=True, key=f"{key_prefix}_{cmd}"):
                st.session_state.active_command = cmd
                st.session_state.drill_active = False
                st.rerun()

def render_command_menu(columns=2):
    """Tap-friendly, categorized grid of drill/roleplay buttons. Sets st.session_state.active_command."""
    for category_name, commands in DRILL_CATEGORIES.items():
        st.markdown(f"#### {category_name}")
        _render_button_grid(commands, columns, key_prefix="menu")

    st.markdown("#### 🎭 Roleplay")
    _render_button_grid(ROL_COMMANDS, columns, key_prefix="menu")

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

def find_scenario(tema):
    scenarios = load_scenarios()
    if not tema or tema == "default":
        return random.choice(scenarios)
    tema_lower = tema.lower().strip()
    # Match by tema, title, or id (partial match allowed)
    for s in scenarios:
        if tema_lower in s["tema"].lower() or tema_lower in s["title"].lower() or tema_lower in s["id"].lower():
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
    """Generate stem-changing verb drill items."""
    data = load_grammar("stem_changing_verbs.json")
    groups = data["stem_changing_present_tense"]
    items = []
    persons = ["yo", "tú", "él_ella_usted", "nosotros", "ellos_ustedes"]
    for group_key in ["grupo_1_e_ie", "grupo_2_e_i", "grupo_3_o_ue"]:
        group = groups[group_key]
        verb_list = group.get("verb_list", [])
        for _ in range(count // 3):
            if not verb_list:
                continue
            v = random.choice(verb_list)
            items.append({
                "id": len(items),
                "prompt": f"Conjugate '{v['infinitive']}' ({v['english']}) in the YO form. Pattern: {group['rule']}",
                "target_form": v.get("yo_form", "(see reference)"),
                "exercise_type": "stem_change",
                "explanation": f"{group['name']}: {v['infinitive']} → {v.get('yo_form', '')}"
            })
    random.shuffle(items)
    return items[:count]

def get_imperfect_drill_items(count=15):
    """Generate imperfect vs preterite contrast drill items."""
    data = load_grammar("imperfect_complete.json")
    practice = data["imperfect_tense"]["practice_sentences"]
    items = []
    for p in practice:
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish (imperfect): {p['english']} [Use type: {p['use_type']}]",
            "target_form": p["spanish"],
            "exercise_type": "imperfect",
            "explanation": f"{p['spanish']} — {p['use_type']}"
        })
    random.shuffle(items)
    return items[:count]

def get_preterite_drill_items(count=15):
    """Generate irregular preterite conjugation drill items."""
    data = load_grammar("preterite_complete.json")
    tense = data["preterite_tense"]
    items = []

    # Group 1: completely irregular
    for v in tense["grupo_completamente_irregulares"]["verbs"]:
        conj = v["conjugation"]
        person = random.choice(list(conj.keys()))
        items.append({
            "id": len(items),
            "prompt": f"Conjugate '{v['infinitive']}' ({v['english']}) in preterite, {person} form.",
            "target_form": conj[person],
            "exercise_type": "preterite",
            "explanation": f"{v['infinitive']} ({person}) → {conj[person]}. {v.get('note', '')}"
        })

    # Group 3: estar/tener/poder
    for v in tense["grupo_3_estar_tener_poder"]["verbs"]:
        items.append({
            "id": len(items),
            "prompt": f"What is the irregular preterite stem of '{v['infinitive']}' ({v['english']})?",
            "target_form": v["stem"],
            "exercise_type": "preterite",
            "explanation": f"{v['infinitive']} → stem: {v['stem']}-"
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
                    "prompt": f"Fill in POR or PARA: {use[key].replace('Para', '___', 1) if use[key].startswith('Para') else use[key]}",
                    "target_form": "para",
                    "exercise_type": "por_para",
                    "explanation": f"{use['use']}: {use[key]} — {use.get('english', '')}"
                })
    for use in ppp["por"]["uses"]:
        items.append({
            "id": len(items),
            "prompt": f"Fill in POR or PARA: {use['example']}",
            "target_form": "por",
            "exercise_type": "por_para",
            "explanation": f"{use['use']}: {use['example']} — {use['english']}"
        })
    for expr in ppp["para"]["idiomatic_expressions"]:
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish (uses PARA): {expr['english']}",
            "target_form": expr["spanish"],
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
                "exercise_type": "demostrativos",
                "explanation": f"{ex['spanish']} — {ex.get('note', group['meaning'])}"
            })

    for pair in data["place_adverbs_pairs"]["pairs"]:
        items.append({
            "id": len(items),
            "prompt": f"Which place adverb means '{pair['english']}' ({pair['distance']})?",
            "target_form": pair["spanish"].split(" / ")[0],
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
            items.append({
                "id": len(items),
                "prompt": f"Translate to Spanish ({category['english_category']}): {w['english']}",
                "target_form": w["spanish"].split(" / ")[0].split(" (")[0],
                "exercise_type": "adverbios",
                "explanation": f"{w['spanish']} — {w['english']}"
            })
    random.shuffle(items)
    return items[:count]

def get_adjetivos_drill_items(count=10):
    """Generate shortened-adjective (apocope) drill items: buen/bueno, mal/malo, etc."""
    data = load_grammar("adjectives.json")
    items = []
    for adj in data["shortened_adjectives"]["affected_adjectives"]:
        items.append({
            "id": len(items),
            "prompt": f"Shortened form of '{adj['full_form']}' before a masculine singular noun?",
            "target_form": adj["shortened_form"],
            "exercise_type": "adjetivos",
            "explanation": f"{adj['full_form']} → {adj['shortened_form']} — {adj['example']} ({adj['english'] if 'english' in adj else ''})"
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
    for _ in range(count - 4):
        v = random.choice(verb_list)
        person = random.choice(list(pronoun_by_person.keys()))
        items.append({
            "id": len(items),
            "prompt": f"Which reflexive pronoun goes with '{person}' for '{v['spanish']}' ({v['english']})?",
            "target_form": pronoun_by_person[person],
            "exercise_type": "reflexivos",
            "explanation": f"{person} → {pronoun_by_person[person]} + {v['spanish'].replace('se', '', 1) if v['spanish'].endswith('se') else v['spanish']}"
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
        })
    random.shuffle(items)
    return items[:count]

def get_futuro_irregular_drill_items(count=12):
    """Generate irregular future/conditional stem drill items."""
    data = load_grammar("future_complete.json")
    stems = data["future_simple"]["irregular_stems"]
    items = []
    for s in stems:
        items.append({
            "id": len(items),
            "prompt": f"Irregular future stem of '{s['infinitive']}' ({s['english']})?",
            "target_form": s["irregular_stem"].rstrip("-"),
            "exercise_type": "futuro_irregular",
            "explanation": f"{s['infinitive']} → {s['irregular_stem']} — e.g. {s['example']}"
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
            items.append({
                "id": len(items),
                "prompt": f"Translate to Spanish: {p['english']}",
                "target_form": p["spanish"].split("/")[0],
                "exercise_type": "lugares",
                "explanation": f"{p['spanish']} — {p['english']}" + (f" ({p.get('gender', '')})" if p.get('gender') else "")
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
    """Generate conjugation drill items focused on imperatives."""
    items = []
    verbs = verbs_data["verbs"]

    persons = ["tú", "usted", "nosotros", "ustedes"]
    polarities = ["affirmative", "negative"]

    for _ in range(count):
        verb = random.choice(verbs)
        person = random.choice(persons)
        polarity = random.choice(polarities)

        # Get the correct conjugation
        imperative_forms = verb["moods"]["imperative"]
        target_form = imperative_forms[polarity].get(person, "")

        if not target_form:
            continue

        # Create prompt
        pronouns = {
            "tú": "you (informal)",
            "usted": "you (formal)",
            "nosotros": "we",
            "ustedes": "you all"
        }

        prompt = f"Conjugate '{verb['infinitive']}' ({person}, {polarity}): "

        # Decide exercise type
        exercise_type = random.choice(["fill_blank", "conjugate", "error_parsing"])

        if exercise_type == "fill_blank":
            if polarity == "affirmative":
                if person == "tú":
                    prompt += f"¡{verb['infinitive'].split('r')[0].capitalize()}___! (Speak!)"
                else:
                    prompt += f"{verb['infinitive']} ahora."
            else:
                prompt += f"No ___ así. (Don't do it like that.)"

        elif exercise_type == "conjugate":
            prompt += f"What is the {person} {polarity} form?"

        elif exercise_type == "error_parsing":
            # Generate a common error
            wrong_form = target_form
            if polarity == "affirmative" and person == "tú":
                # Common error: using present instead of imperative
                wrong_form = verb["moods"]["present_indicative"].get("tú", target_form)

            prompt += f"Is this correct? '{wrong_form}' ✓ or ✗?"

        items.append({
            "id": len(items),
            "prompt": prompt,
            "verb_infinitive": verb["infinitive"],
            "person": person,
            "polarity": polarity,
            "target_form": target_form,
            "exercise_type": exercise_type,
            "explanation": f"The {person} {polarity} imperative of '{verb['infinitive']}' is '{target_form}'."
        })

    return items

def run_drill(module_type="imperativo", duration_seconds=300):
    """Main drill runner."""
    initialize_session()

    # Header
    st.title("⚡ Spanish Drill")
    st.markdown(f"**Module:** `!drill {module_type}` | **Duration:** 5 minutes")

    # Initialize drill if not active
    if not st.session_state.drill_active:
        st.session_state.drill_active = True
        st.session_state.drill_module = module_type
        st.session_state.drill_start_time = datetime.now()

        if module_type == "imperativo":
            verbs_data = load_verbs()
            st.session_state.drill_items = get_imperative_drill_items(verbs_data)
        elif module_type == "pronombres":
            st.session_state.drill_items = get_pronombres_drill_items()
        elif module_type == "stem_changes" or module_type == "cambios":
            st.session_state.drill_items = get_stem_change_drill_items()
        elif module_type == "imperfecto" or module_type == "pasado":
            st.session_state.drill_items = get_imperfect_drill_items()
        elif module_type == "preterito" or module_type == "preterite":
            st.session_state.drill_items = get_preterite_drill_items()
        elif module_type == "pluscuamperfecto" or module_type == "pluscuam":
            st.session_state.drill_items = get_pluscuamperfecto_drill_items()
        elif module_type == "ejercicio" or module_type == "review111":
            st.session_state.drill_items = get_ejercicio_drill_items()
        elif module_type == "por_para" or module_type == "porpara":
            st.session_state.drill_items = get_por_para_drill_items()
        elif module_type == "demostrativos" or module_type == "distancias":
            st.session_state.drill_items = get_demostrativos_drill_items()
        elif module_type == "adverbios":
            st.session_state.drill_items = get_adverbios_drill_items()
        elif module_type == "adjetivos":
            st.session_state.drill_items = get_adjetivos_drill_items()
        elif module_type == "numeros":
            st.session_state.drill_items = get_numeros_drill_items()
        elif module_type == "reflexivos":
            st.session_state.drill_items = get_reflexivos_drill_items()
        elif module_type == "participios":
            st.session_state.drill_items = get_participios_drill_items()
        elif module_type == "futuro_irregular" or module_type == "futuro":
            st.session_state.drill_items = get_futuro_irregular_drill_items()
        elif module_type == "estructuras" or module_type == "preguntas":
            st.session_state.drill_items = get_estructuras_drill_items()
        elif module_type == "lugares":
            st.session_state.drill_items = get_lugares_drill_items()
        else:
            verbs_data = load_verbs()
            st.session_state.drill_items = get_imperative_drill_items(verbs_data)

        st.session_state.current_item_index = 0
        st.session_state.answers = []
        st.session_state.score = 0
        st.session_state.total_questions = 0

    # Calculate time remaining
    elapsed = (datetime.now() - st.session_state.drill_start_time).total_seconds()
    time_remaining = max(0, duration_seconds - elapsed)

    # Timer display
    minutes, seconds = divmod(int(time_remaining), 60)
    progress = max(0, time_remaining / duration_seconds)

    col1, col2 = st.columns([3, 1])
    with col1:
        st.progress(progress)
    with col2:
        st.metric("Time Left", f"{minutes}:{seconds:02d}")

    # Check if drill is complete
    if time_remaining <= 0 or st.session_state.current_item_index >= len(st.session_state.drill_items):
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

        if st.button("🔄 Start New Drill"):
            st.session_state.drill_active = False
            st.rerun()

        return

    # Display current question
    if st.session_state.current_item_index < len(st.session_state.drill_items):
        item = st.session_state.drill_items[st.session_state.current_item_index]

        st.subheader(f"Question {st.session_state.current_item_index + 1} of {len(st.session_state.drill_items)}")

        st.markdown(f"### {item['prompt']}")

        # Answer input
        user_answer = st.text_input("Your answer:", key=f"answer_{item['id']}")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("✅ Submit Answer", use_container_width=True):
                # Simple feedback
                is_correct = user_answer.strip().lower() == item['target_form'].lower()

                st.session_state.answers.append({
                    "item_id": item['id'],
                    "user_answer": user_answer,
                    "correct_answer": item['target_form'],
                    "is_correct": is_correct
                })

                st.session_state.total_questions += 1
                if is_correct:
                    st.session_state.score += 1

                # Show feedback
                if is_correct:
                    st.success(f"✅ Correct! '{item['target_form']}'")
                else:
                    st.error(f"❌ Incorrect. The correct form is: '{item['target_form']}'")
                    st.info(f"💡 {item['explanation']}")

                time.sleep(2)
                st.session_state.current_item_index += 1
                st.rerun()

        with col2:
            if st.button("💡 Hint", use_container_width=True):
                st.info(f"💡 Hint: {item['explanation']}")

        with col3:
            if st.button("⏭️ Skip", use_container_width=True):
                st.session_state.current_item_index += 1
                st.rerun()

def run_rol(tema=None):
    """Display a scenario card for roleplay. The conversation itself happens
    in chat with Claude, using this card as context — Streamlit only selects
    and presents the scenario."""
    st.title("🎭 Roleplay Scenario")

    scenario = find_scenario(tema)

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
    st.markdown(
        "**Cómo usar esta tarjeta:** Este panel selecciona y muestra el escenario, "
        "pero la conversación dinámica ocurre chateando directamente con Claude. "
        "Copia la frase de apertura (o simplemente escribe `!rol " + scenario["tema"] +
        "` en el chat) y Claude continuará el rol dinámicamente en español, "
        "corrigiendo errores de gramática al final de cada respuesta según el protocolo de inmersión."
    )

    if st.button("🔄 Otro escenario aleatorio"):
        st.rerun()

def parse_command(command_input):
    """Parse CLI-style commands."""
    parts = command_input.strip().split()

    if not parts:
        return None

    if parts[0] == "!drill":
        module = parts[1] if len(parts) > 1 else "imperativo"
        return ("drill", module)
    elif parts[0] == "!hablar":
        return ("hablar", None)
    elif parts[0] == "!rol":
        tema = " ".join(parts[1:]) if len(parts) > 1 else "default"
        return ("rol", tema)
    elif parts[0] == "!pausa":
        return ("pausa", None)
    elif parts[0] == "!resumen":
        return ("resumen", None)

    return None

def dispatch_command(command_str):
    """Run whichever command string is active (from typing or a button tap)."""
    parsed = parse_command(command_str)

    if not parsed:
        st.error("❌ Command not recognized. Try: `!drill imperativo`")
        return

    command_type, arg = parsed

    if command_type == "drill":
        run_drill(module_type=arg)
    elif command_type == "hablar":
        st.info("🎤 Conversational Partner mode coming soon...")
    elif command_type == "rol":
        run_rol(tema=arg)
    elif command_type == "pausa":
        st.info("⏸️ Paused. Explanation mode enabled.")
    elif command_type == "resumen":
        st.info("📋 Session summary coming soon...")

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
        st.title("🎯 Spanish Learning System")

        if st.session_state.active_command:
            if st.button("🏠 Home", use_container_width=True):
                st.session_state.active_command = None
                st.session_state.drill_active = False
                st.session_state.pop("mobile_typed_cmd", None)
                st.rerun()
            dispatch_command(st.session_state.active_command)
        else:
            render_landing()
            render_command_menu(columns=1)

            with st.expander("⌨️ Advanced: type a command"):
                typed = st.text_input("Command:", placeholder="!drill imperativo", key="mobile_typed_cmd")
                if typed:
                    st.session_state.active_command = typed
                    st.rerun()

    else:
        st.sidebar.title("🎯 Spanish Learning System")

        if st.session_state.active_command:
            if st.sidebar.button("🏠 Home"):
                st.session_state.active_command = None
                st.session_state.drill_active = False
                st.session_state.pop("desktop_typed_cmd", None)
                st.rerun()

        st.sidebar.markdown("**Quick Commands:**")
        with st.sidebar:
            render_command_menu(columns=2)

        st.sidebar.markdown("---")
        command_input = st.sidebar.text_input("Or type a command:", placeholder="!drill imperativo", key="desktop_typed_cmd")
        if command_input:
            st.session_state.active_command = command_input

        if st.session_state.active_command:
            dispatch_command(st.session_state.active_command)
        else:
            render_landing()

if __name__ == "__main__":
    main()
