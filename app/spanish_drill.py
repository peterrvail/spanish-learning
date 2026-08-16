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

def main():
    """Main CLI interface."""
    st.set_page_config(page_title="Spanish Learning System", layout="wide")

    # Sidebar: Command input
    st.sidebar.title("🎯 Spanish Learning System")
    st.sidebar.markdown("**Quick Commands:**")
    st.sidebar.markdown("""
    - `!drill imperativo` — Imperative conjugation
    - `!drill pronombres` — Double object pronouns
    - `!drill cambios` — Stem-changing verbs
    - `!drill pasado` — Imperfect tense usage
    - `!drill preterito` — Irregular preterite verbs
    - `!drill pluscuam` — Past perfect (pluscuamperfecto)
    - `!drill ejercicio` — Preterite fill-in-the-blank homework
    - `!hablar` — Conversational partner mode
    - `!rol [tema]` — Roleplay scenario (restaurante, transporte, vecinos, salud, narrativa, viajes, compras, convivencia)
    - `!pausa` — Step out for English explanation
    - `!resumen` — Session summary
    """)

    # Command input
    command_input = st.sidebar.text_input("Enter command:", placeholder="!drill imperativo")

    # Check for command
    if command_input:
        parsed = parse_command(command_input)

        if parsed:
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
        else:
            st.error("❌ Command not recognized. Try: `!drill imperativo`")
    else:
        # Default landing page
        st.markdown("""
        # 🚀 Spanish Learning System

        Welcome to your personalized B1→B2 Spanish learning environment.

        ## Getting Started

        1. **Enter a command** in the sidebar to start practicing
        2. Try: `!drill imperativo` for a 5-minute imperative conjugation drill
        3. Or explore other modes: `!hablar`, `!rol`, etc.

        ## Module Overview

        - **Imperatives** — Formal/informal commands, clitic attachment
        - **Pronoun Mechanics** — Direct/indirect object pronouns, reflexives
        - **Aspect & Tense** — Preterite vs. Imperfect storytelling
        - **Vocabulary** — Thematic word lists by domain
        - **Scenarios** — Real-world roleplay with task objectives
        - **Readings** — Annotated short stories and dialogues

        """)

if __name__ == "__main__":
    main()
