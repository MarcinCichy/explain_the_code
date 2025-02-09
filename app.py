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

def split_code_by_def_class(code_snippet):
    """
    Dzieli kod 'z grubsza' przy liniach rozpoczynających się od 'def' lub 'class'.
    """
    code_snippet = code_snippet.strip('\n')
    pattern = r'(?=^def |^class )'
    blocks = re.split(pattern, code_snippet, flags=re.MULTILINE)
    blocks = [b.strip() for b in blocks if b.strip()]
    return blocks

def further_split_if_too_large(block, max_lines=20):
    """
    Jeśli blok ma więcej niż max_lines linii, dzielimy go na kawałki.
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
    Pyta ChatGPT o wyjaśnienie pojedynczego (małego) fragmentu kodu.
    """
    system_message = (
        "Jesteś przyjaznym nauczycielem programowania dla 13-letniego dziecka. "
        "Otrzymasz fragment kodu w Pythonie i poproszę Cię, abyś wyjaśnił, co on robi, "
        "krok po kroku, w prostych słowach. Możesz przytaczać fragmenty kodu, "
        "ale tłumacz w jasny, przyjazny sposób."
    )
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": block}
        ],
        temperature=0.2
    )
    return response['choices'][0]['message']['content']


def analyze_code_snippet(code_snippet):
    """
    Dzieli kod na mniejsze fragmenty, pyta ChatGPT i łączy wyniki w jeden string (bez duplikowania kodu).
    """
    # 1. Podział wstępny
    blocks = split_code_by_def_class(code_snippet)
    if not blocks:
        blocks = [code_snippet]

    final_blocks = []
    for b in blocks:
        final_blocks.extend(further_split_if_too_large(b, max_lines=20))

    # 2. Wywołanie ChatGPT dla każdego fragmentu i łączenie
    explanations = []
    for small_block in final_blocks:
        exp_text = get_explanation_for_block(small_block)
        # Tym razem NIE dodajemy "```python\n{small_block}\n```" itd.
        # - unikamy podwójnego wyświetlania kodu w prawym panelu.
        explanations.append(exp_text)

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
    # Szukamy maksymalnego ID (jako int), żeby uniknąć duplikatów
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
    tylko czyści okna. (Zostawiamy endopint w spokoju.)
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

    # Zapis w pliku
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
