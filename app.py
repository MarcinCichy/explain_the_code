import os
import json
import re
import openai

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

CONVERSATIONS_FILE = "conversations.json"


# ========================================
#  Funkcje wczytywania/zapisywania
# ========================================

def load_conversations():
    """Wczytuje konwersacje z pliku JSON."""
    try:
        with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_conversations(convs):
    """Zapisuje konwersacje do pliku JSON."""
    with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(convs, f, indent=4, ensure_ascii=False)


# ========================================
#  Funkcje dzielenia kodu i ChatGPT
# ========================================

def smart_split_code_snippet(code_snippet):
    """
    Inteligentnie dzieli kod na logiczne sekcje przy użyciu AI.

    Funkcja wysyła kod do modelu OpenAI, prosząc o podział kodu na logiczne sekcje.
    Odpowiedź powinna być w formacie JSON – lista obiektów, gdzie każdy obiekt posiada
    klucze "title" (krótki tytuł sekcji) oraz "code" (fragment kodu należący do tej sekcji).

    W przypadku niepowodzenia parsowania lub wystąpienia błędu (np. przekroczenia limitu),
    zwraca całość kodu jako jedną sekcję lub komunikat o błędzie.
    """
    prompt = (
        "Podziel poniższy kod na logiczne sekcje, które oddzielają różne zagadnienia programowania. "
        "Dla każdej sekcji podaj krótki tytuł oraz fragment kodu należący do tej sekcji. "
        "Zwróć wyłącznie czysty JSON bez żadnych dodatkowych komentarzy ani objaśnień. "
        "Format odpowiedzi: [{\"title\": \"<tytuł>\", \"code\": \"<fragment kodu>\"}, ...]\n\n"
        "Kod:\n\n" + code_snippet
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Jesteś ekspertem w nauczaniu programowania."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )
        result = response['choices'][0]['message']['content'].strip()
        if not result:
            raise ValueError("Odpowiedź API jest pusta.")
        sections = json.loads(result)
    except Exception as e:
        err_str = str(e).lower()
        if "limit" in err_str or "koszt" in err_str or "quota" in err_str:
            print("Osiągnięto limit kosztów podczas podziału kodu:", e)
            sections = [{"title": "Błąd API", "code": "Osiągnięto limit kosztów. Proszę spróbować później."}]
        else:
            print("Błąd podczas inteligentnego podziału kodu:", e)
            sections = [{"title": "Cały kod", "code": code_snippet}]
    return sections


def further_split_if_too_large(block, max_lines=20):
    """
    Jeśli blok ma więcej niż max_lines linii, dzielimy go na mniejsze kawałki.
    """
    lines = block.split('\n')
    if len(lines) <= max_lines:
        return [block]
    chunks = []
    for i in range(0, len(lines), max_lines):
        subblock = lines[i:i + max_lines]
        chunks.append('\n'.join(subblock))
    return chunks


def get_explanation_for_block(block):
    """
    Pyta ChatGPT o wyjaśnienie pojedynczego fragmentu kodu.
    """
    system_message = (
        "Jesteś przyjaznym nauczycielem programowania dla 13-letniego dziecka. "
        "Otrzymasz fragment kodu w Pythonie i poproszę Cię, abyś wyjaśnił, co on robi, "
        "krok po kroku, w prostych słowach. Możesz przytaczać fragmenty kodu, "
        "cytuj te fragmenty kodu, które omawiasz, "
        "ale tłumacz w jasny, przyjazny sposób."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": block}
            ],
            temperature=0.2
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        err_str = str(e).lower()
        if "limit" in err_str or "koszt" in err_str or "quota" in err_str:
            return "Niestety, nie mogę teraz korzystać z API z powodu osiągniętego limitu kosztów. Proszę spróbować później."
        else:
            return f"Błąd podczas uzyskiwania wyjaśnienia: {str(e)}"


def analyze_code_snippet(code_snippet):
    """
    Dzieli kod na mniejsze fragmenty przy użyciu inteligentnego podziału,
    pyta ChatGPT o wyjaśnienie każdego fragmentu i łączy wyniki w jeden string.

    Każda sekcja zawiera najpierw cały kod danej części (umieszczony w bloku kodu),
    a następnie wyjaśnienie.
    """
    # Używamy AI do podziału kodu na logiczne sekcje
    sections = smart_split_code_snippet(code_snippet)

    # Upewnijmy się, że mamy listę słowników:
    fixed_sections = []
    if isinstance(sections, list):
        for sec in sections:
            if isinstance(sec, dict):
                fixed_sections.append(sec)
            else:
                # Jeśli element nie jest słownikiem, opakowujemy go w słownik
                fixed_sections.append({"title": "Sekcja", "code": sec})
    else:
        fixed_sections = [{"title": "Cały kod", "code": code_snippet}]

    explanations = []
    for section in fixed_sections:
        section_code = section.get("code", "")
        blocks = further_split_if_too_large(section_code, max_lines=20)
        section_explanation = []
        for block in blocks:
            exp_text = get_explanation_for_block(block)
            section_explanation.append(exp_text)
        combined_section_explanation = "\n\n".join(section_explanation)
        # Zamiast dodawania tytułu dodajemy najpierw kod w formie bloku, a potem wyjaśnienie
        explanations.append(f"```python\n{section_code}\n```\n\n{combined_section_explanation}")

    combined_explanation = "\n\n".join(explanations)
    return code_snippet, combined_explanation


# ========================================
#  Endpointy RAG
# ========================================

@app.route("/")
def index():
    convs = load_conversations()
    conv_ids = list(convs.keys())
    return render_template("index.html", conversations=conv_ids)


@app.route("/new_conversation", methods=["POST"])
def new_conversation():
    """
    Tworzy nową konwersację (pustą) z unikalnym ID, nawet jeśli usunięto starsze ID.
    """
    convs = load_conversations()
    if convs:
        max_id = max(int(k) for k in convs.keys())
    else:
        max_id = 0
    new_id = str(max_id + 1)
    convs[new_id] = []  # pusta lista
    save_conversations(convs)
    return jsonify({
        "conversation_id": new_id,
        "conversations": list(convs.keys())
    })


@app.route("/load_conversation", methods=["POST"])
def load_conversation():
    """
    Ładuje listę {code, explanation} z wybranej konwersacji.
    """
    data = request.json
    cid = data.get("conversation_id", "")
    convs = load_conversations()
    messages = convs.get(cid, [])
    return jsonify({
        "conversation_id": cid,
        "messages": messages
    })


@app.route("/delete_conversation", methods=["POST"])
def delete_conversation():
    data = request.json
    cid = data.get("conversation_id", "")
    convs = load_conversations()
    if cid in convs:
        del convs[cid]
        save_conversations(convs)
    return jsonify({
        "status": "deleted",
        "conversation_id": cid,
        "conversations": list(convs.keys())
    })


@app.route("/reset", methods=["POST"])
def reset_chat():
    """
    Obecnie NIC nie usuwa z pliku (zgodnie z wymaganiem).
    To endpoint oryginalny RAG, ale nasz "Reset" w UI
    tylko czyści okna. (Zostawiamy endpoint w spokoju.)
    """
    return jsonify({"status": "local_reset"})


@app.route("/explain", methods=["POST"])
def explain():
    code = request.form.get("code", "")
    conversation_id = request.form.get("conversation_id", "").strip()
    if not code.strip():
        return jsonify({
            "error": "Brak kodu do wyjaśnienia.",
            "code": "",
            "explanation": ""
        })
    if not conversation_id:
        return jsonify({
            "error": "Brak wybranej konwersacji. Utwórz lub wczytaj konwersację.",
            "code": code,
            "explanation": ""
        })
    original_code, combined_expl = analyze_code_snippet(code)
    convs = load_conversations()
    if conversation_id not in convs:
        convs[conversation_id] = []
    convs[conversation_id].append({
        "code": original_code,
        "explanation": combined_expl
    })
    save_conversations(convs)
    return jsonify({
        "error": "",
        "code": original_code,
        "explanation": combined_expl
    })


@app.route("/exit", methods=["POST"])
def exit_app():
    convs = load_conversations()
    summary = {
        "message": "Aplikacja została zamknięta. Dziękujemy za korzystanie!",
        "conversation_count": len(convs),
        "questions_asked": sum(len(conv) for conv in convs.values())
    }
    return jsonify(summary)


if __name__ == "__main__":
    app.run(debug=True)
