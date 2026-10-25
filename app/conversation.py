"""In-app Spanish conversation partner backed by the Claude API.

Kept free of Streamlit so it can be tested with a fake client. The page code
in spanish_drill.py owns the history list and passes it in.

History is append-only: each assistant turn is stored as the full list of
content blocks the API returned (thinking blocks included) and replayed
verbatim, and the system prompt never changes within a conversation. Claude
Opus 5.5 rejects or drops replayed thinking blocks whose earlier history was
edited, so nothing here rewrites past turns."""
import os

try:
    import anthropic
except ImportError:  # the drills work without it; only the chat needs it
    anthropic = None

MODEL = "claude-opus-5-5"
# On a safety-classifier decline, the API re-runs the request on the model
# Anthropic recommends for that refusal category instead of just refusing.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_BASE_PROMPT = """You are a friendly Spanish conversation partner for an adult learner moving from B1 to B2. Have a real conversation with them in Spanish.

How to reply:
- Write your reply only in Spanish, 2 to 4 sentences, the way a native speaker from Spain or Latin America would talk to a friend. Use B1-B2 vocabulary; if you need a rarer word, gloss it in parentheses.
- Keep the conversation moving: react to what they said and usually end with a question.
- Give them reasons to use the grammar they are drilling: preterite vs. imperfect, the pluscuamperfecto, imperatives, double object pronouns (se lo, me la), por vs. para, and stem-changing verbs. Do this through the questions you ask, not by announcing it.
- If they write in English or get stuck, answer in Spanish and show them how to say what they meant.

After your reply, if their last message had mistakes, add a blank line and then a block that starts with "📝 Correcciones:". List at most the 3 most important mistakes as a Markdown bullet list, one bullet each: "- ~~what they wrote~~ → **corrected form** — a short reason in English". Accent-only slips count only if they change meaning (e.g. hablo/habló). If their message had no real mistakes, leave the block out entirely; don't praise every message."""


def credentials_configured(secret_key=None):
    """Best-effort check that the SDK will find credentials. The client
    constructs fine without any and only fails on the first request, so
    check up front and show setup help instead of an error mid-chat."""
    if anthropic is None:
        return False
    if secret_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    # A profile from `ant auth login`, which the SDK also reads.
    config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return bool(os.environ.get("ANTHROPIC_PROFILE")) or os.path.isdir(os.path.join(config_home, "anthropic"))


def get_client(api_key=None):
    """A client, using an explicit key if given (e.g. from Streamlit secrets),
    else the SDK's normal credential lookup."""
    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


def system_prompt(scenario=None):
    """Free conversation, or a roleplay built from a scenario card."""
    if not scenario:
        return _BASE_PROMPT
    p = scenario["persona"]
    return _BASE_PROMPT + f"""

This conversation is a roleplay. Stay in character the whole time.
- You are {p['name']}, {p['role']}. Personality: {p['personality']}. Register: {p['formality']}.
- Situation: {scenario['context']}
- The learner's goal: {scenario['user_objective']}
- Grammar to draw out: {', '.join(scenario['target_grammar'])}
- Vocabulary they should get to use: {', '.join(scenario['required_vocabulary'])}
- The learner succeeds when: {'; '.join(scenario['success_criteria'])}
- You have already opened with: "{scenario['opening_line']}" Their first message answers that.

When the learner has met every success criterion, add a final line after any corrections: "✅ ¡Objetivo cumplido!" plus one sentence in English on what they did well."""


def assistant_text(content):
    """The visible text of a stored assistant turn (skips thinking/fallback blocks)."""
    return "".join(b.get("text", "") for b in content if b.get("type") == "text")


class ChatError(Exception):
    """A failure to show the learner, already worded for them."""


def stream_reply(client, system, history, result):
    """Yield the reply's text as it streams; afterwards result["content"] holds
    the full content blocks to append to history. Raises ChatError on refusal
    or API failure; the caller should then drop the unanswered user turn."""
    try:
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=16000,
            system=system,
            messages=history,
            # Chat turns are short and latency matters; low effort is plenty.
            output_config={"effort": "low"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            for text in stream.text_stream:
                yield text
            final = stream.get_final_message()
    except anthropic.AuthenticationError:
        raise ChatError("La clave de la API de Claude no es válida. Revisa ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        raise ChatError("Demasiadas peticiones ahora mismo. Espera un momento y vuelve a intentarlo.")
    except anthropic.APIStatusError as e:
        raise ChatError(f"Error de la API de Claude ({e.status_code}). Inténtalo de nuevo.")
    except anthropic.APIConnectionError:
        raise ChatError("No hay conexión con la API de Claude. Comprueba tu conexión a internet.")
    except TypeError as e:
        # The SDK has no typed error for "no credentials at all" (e.g. a stale
        # ~/.config/anthropic folder made credentials_configured() say yes).
        if "authentication method" not in str(e):
            raise
        raise ChatError("No se encontró la clave de la API de Claude. Configura ANTHROPIC_API_KEY.")

    if final.stop_reason == "refusal":
        raise ChatError("Claude no ha podido responder a ese mensaje. Prueba a decirlo de otra forma.")
    result["content"] = [block.to_dict() for block in final.content]
