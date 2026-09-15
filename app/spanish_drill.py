import streamlit as st
import json
import random
import re
import unicodedata
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
        ("☀️ Rutina diaria (presente)", "!drill rutina"),
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
        ("🧩 Otras preposiciones", "!drill preposiciones"),
        ("👉 Demostrativos", "!drill demostrativos"),
        ("🔤 Adjetivos cortos", "!drill adjetivos"),
        ("🪞 Reflexivos/Recíprocos", "!drill reflexivos"),
        ("🚫 Indefinidos/Negativos", "!drill indefinidos"),
        ("🗣️ Estructuras + preguntas", "!drill estructuras"),
    ],
    "Vocabulario": [
        ("📚 Mis lecciones", "!drill vocabulario"),
        ("🌍 Común (general)", "!drill vocab_comun"),
        ("🔀 Mezcla", "!drill vocab_mezcla"),
        ("🔢 Números", "!drill numeros"),
        ("🧭 Adverbios", "!drill adverbios"),
        ("📍 Lugares", "!drill lugares"),
    ],
    "👵 De mi Suegra": [
        ("🚂 Ir + Gerundio", "!drill gerundio"),
    ],
}
# Flat list kept for backward-compatible lookups (parse_command etc.)
DRILL_COMMANDS = [item for group in DRILL_CATEGORIES.values() for item in group]
# Pure-vocabulary drills: recalling one exact word is the whole exercise, so
# "I don't know" should reveal the answer and move on rather than nudge with a hint.
VOCAB_MODULE_TYPES = {"vocabulario", "comunes", "vocab_comun", "vocab_mezcla", "numeros", "adverbios", "lugares"}
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

def is_mobile():
    """Detect iOS/mobile via the request's User-Agent (server-side, no JS needed)."""
    try:
        ua = st.context.headers.get("User-Agent", "") or ""
    except Exception:
        ua = ""
    ua = ua.lower()
    return any(token in ua for token in ["iphone", "ipad", "ipod", "android", "mobile"])

def inject_wide_sidebar_css():
    """Widen the desktop sidebar so category names and buttons aren't cramped."""
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            width: 420px !important;
        }
        section[data-testid="stSidebar"] > div {
            width: 420px !important;
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
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def _set_active_command(cmd):
    st.session_state.active_command = cmd
    st.session_state.drill_active = False
    st.rerun()

def _render_button_grid(commands, columns, key_prefix):
    """Render a grid of drill/roleplay buttons. Drills whose module has a grammar
    concept to explain (see get_module_concept) also get a 📖 Repasar icon;
    pure-vocabulary drills and roleplay commands don't, since there's nothing to
    review beyond the quiz itself."""
    cols = st.columns(columns)
    for i, (label, cmd) in enumerate(commands):
        with cols[i % columns]:
            module = cmd.split(" ", 1)[1] if cmd.startswith("!drill ") else None
            has_concept = module is not None and get_module_concept(module) is not None
            if has_concept:
                bcol, rcol = st.columns([6, 1])
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

def is_correct_answer(user_answer, item):
    """Check a typed answer against every accepted form for this item,
    accent-insensitive. Falls back to target_form alone when an item has no
    accepted_forms list."""
    accepted = item.get("accepted_forms") or [item["target_form"]]
    normalized_user = _normalize_for_grading(user_answer)
    return any(normalized_user == _normalize_for_grading(a) for a in accepted)

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
            items.append({
                "id": len(items),
                "prompt": f"Conjugate '{v['infinitive']}' ({v['english']}) in the YO form. Pattern: {group['rule']}",
                "target_form": v["yo_form"],
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
            "exercise_type": "imperfect",
            "explanation": f"{p['spanish']} — {p['use_type']}"
        })
    for use in tense["uses"]:
        for ex in use["examples"]:
            items.append({
                "id": len(items),
                "prompt": f"Translate to Spanish (imperfect): {ex['english']} [Use type: {use['name']}]",
                "target_form": ex["spanish"],
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
    random.shuffle(items)
    return items[:count]

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
            "exercise_type": "rutina",
            "explanation": f"{ex['spanish']} — {ex['infinitive']}" + (f" ({ex['note']})" if 'note' in ex else "")
        })
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
            "exercise_type": "ir_gerundio",
            "explanation": f"{ex['spanish']} — {ex['base_verb']} → {ex['gerund']}"
        })

    for ex in ig["additional_examples_other_persons"]:
        items.append({
            "id": len(items),
            "prompt": f"Translate to Spanish (ir + gerundio, '{ex['person']}' form): {ex['english']}",
            "target_form": ex["spanish"],
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
        prompt = f"Conjugate '{verb['infinitive']}' ({person}, {polarity}): "

        exercise_type = random.choice(["fill_blank", "conjugate"])
        if exercise_type == "fill_blank":
            if polarity == "affirmative":
                if person == "tú":
                    prompt += f"¡{verb['infinitive'].split('r')[0].capitalize()}___! (Speak!)"
                else:
                    prompt += f"{verb['infinitive']} ahora."
            else:
                prompt += f"No ___ así. (Don't do it like that.)"
        else:
            prompt += f"What is the {person} {polarity} form?"

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

def get_drill_items(module_type):
    """Generate the item list for a given module type. Shared by the quiz
    drill runner and the self-paced review (repaso) runner."""
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
    else:
        return get_imperative_drill_items(load_verbs())

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
        st.session_state.drill_items = get_drill_items(module_type)
        st.session_state.current_item_index = 0
        st.session_state.answers = []
        st.session_state.score = 0
        st.session_state.total_questions = 0
        st.session_state.pending_feedback = None

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

    pausa_col, resumen_col = st.columns(2)
    with pausa_col:
        if st.button("⏸️ Pausa (explicar)", use_container_width=True):
            st.session_state.active_command = "!pausa"
            st.rerun()
    with resumen_col:
        if st.button("📋 Resumen", use_container_width=True):
            st.session_state.active_command = "!resumen"
            st.rerun()

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

        pending = st.session_state.get("pending_feedback")

        if pending and pending.get("item_id") == item["id"]:
            # Feedback phase: show the result and wait for the user to move on,
            # at their own pace, instead of a hardcoded sleep.
            if pending["is_correct"] is True:
                st.success(f"✅ Correct! '{pending['target_form']}'")
            elif pending["is_correct"] is False:
                st.error(f"❌ Incorrect. The correct form is: '{pending['target_form']}'")
                if pending.get("explanation"):
                    st.info(f"💡 {pending['explanation']}")
            else:
                reveal = f"✅ {pending['target_form']}"
                if pending.get("explanation"):
                    reveal += f" — {pending['explanation']}"
                st.info(reveal)

            if st.button("➡️ Continuar", use_container_width=True):
                st.session_state.pending_feedback = None
                st.session_state.current_item_index += 1
                st.rerun()
            return

        # Answering phase
        answer_key = f"answer_{item['id']}"

        st.caption("Acentos rápidos:")
        accent_cols = st.columns(7)
        for i, ch in enumerate(["á", "é", "í", "ó", "ú", "ñ", "ü"]):
            with accent_cols[i]:
                if st.button(ch, key=f"accent_{item['id']}_{ch}", use_container_width=True):
                    st.session_state[answer_key] = st.session_state.get(answer_key, "") + ch
                    st.rerun()

        # Wrapped in a form so pressing Enter submits it, same as clicking "Submit Answer".
        with st.form(key=f"answer_form_{item['id']}"):
            user_answer = st.text_input("Your answer:", key=answer_key)
            submitted = st.form_submit_button("✅ Submit Answer", use_container_width=True)

        if submitted:
            is_correct = is_correct_answer(user_answer, item)

            st.session_state.answers.append({
                "item_id": item['id'],
                "user_answer": user_answer,
                "correct_answer": item['target_form'],
                "is_correct": is_correct
            })

            st.session_state.total_questions += 1
            if is_correct:
                st.session_state.score += 1

            st.session_state.pending_feedback = {
                "item_id": item['id'],
                "is_correct": is_correct,
                "target_form": item['target_form'],
                "explanation": item.get('explanation', ''),
            }
            st.rerun()

        col2, col3 = st.columns(2)

        with col2:
            if module_type in VOCAB_MODULE_TYPES:
                if st.button("👁️ Revelar y siguiente", use_container_width=True):
                    st.session_state.pending_feedback = {
                        "item_id": item['id'],
                        "is_correct": None,
                        "target_form": item['target_form'],
                        "explanation": item.get('explanation', ''),
                    }
                    st.rerun()
            else:
                if st.button("💡 Hint", use_container_width=True):
                    st.info(f"💡 Hint: {item['explanation']}")

        with col3:
            if st.button("⏭️ Skip", use_container_width=True):
                st.session_state.current_item_index += 1
                st.rerun()

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
    st.markdown("---")

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
    if items_key not in st.session_state:
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
    """Freeform conversational-partner mode. Like !rol, the conversation
    itself happens in chat with Claude — this screen just sets the stage
    with a topic to start from, instead of a scripted scenario."""
    st.title("🗣️ Compañero de Conversación")
    st.markdown(
        "Conversación libre en español, sin guion ni objetivo fijo. "
        "Escribe directamente en el chat con Claude — responderá **100% en "
        "español**, en turnos de 2 a 4 frases, y corregirá tus errores de "
        "gramática al final de cada respuesta."
    )

    st.markdown("### 💬 Si no sabes por dónde empezar")
    idx_key = "hablar_starter_idx"
    st.session_state.setdefault(idx_key, random.randrange(len(_HABLAR_STARTERS)))
    st.info(_HABLAR_STARTERS[st.session_state[idx_key]])

    if st.button("🔀 Otro tema aleatorio"):
        st.session_state[idx_key] = random.randrange(len(_HABLAR_STARTERS))
        st.rerun()

    st.markdown("---")
    st.markdown(
        "**Cómo usar esto:** copia el tema de arriba (o escribe el tuyo) "
        "directamente en el chat. Claude seguirá la conversación en español "
        "de forma dinámica. Para algo más estructurado, con un objetivo y "
        "vocabulario específicos, usa `!rol [tema]` en su lugar."
    )

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

    st.caption(f"Pausando `!drill {module_type}` — el cronómetro del drill sigue corriendo mientras lees esto.")

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

def parse_command(command_input):
    """Parse CLI-style commands."""
    parts = command_input.strip().split()

    if not parts:
        return None

    if parts[0] == "!drill":
        module = parts[1] if len(parts) > 1 else "imperativo"
        return ("drill", module)
    elif parts[0] == "!repasar":
        module = parts[1] if len(parts) > 1 else "imperativo"
        return ("repasar", module)
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
        inject_wide_sidebar_css()
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
