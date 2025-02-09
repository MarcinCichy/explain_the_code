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
#  Pomocnicze: wczytywanie/zapisywanie konwersacji
# ========================================

def load_conversations():
    try:
        with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_conversations(convs):
    with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(convs, f, indent=4, ensure_ascii=False)


# ========================================
#  Dzielenie kodu i zapytanie do ChatGPT
# ========================================

def split_code_by_def_class(code_snippet):
    """
    Dzieli kod 'z grubsza' przy liniach rozpoczynających się od 'def' lub 'class'.
    """
    code_snippet = code_snippet.strip('\n')
    pattern = r'(?=^def |^class )'
    blocks = re.split(pattern, code_snippet, flags=re.MULTILINE)
    # Usuwamy puste
    blocks = [b.strip() for b in blocks if b.strip()]
    return blocks

def further_split_if_too_large(block, max_lines=20):
    """
    Jeśli dany blok ma więcej niż max_lines linii, rozbijamy go na mniejsze fragmenty.
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
    Pyta ChatGPT o wyjaśnienie pojedynczego małego bloku kodu.
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
    Dzieli kod na mniejsze fragmenty (def/class, plus ewentualnie co 20 linii),
    a następnie scala odpowiedzi ChatGPT w jedną całość.
    Zwraca 2 rzeczy:
      - oryginalny kod (code_snippet)
      - złączone wyjaśnienie (string)
    """
    # 1. Podział
    blocks = split_code_by_def_class(code_snippet)
    if not blocks:
        # Jeśli kod nie zawiera def/class, potraktuj cały
        blocks = [code_snippet]

    final_blocks = []
    for b in blocks:
        final_blocks.extend(further_split_if_too_large(b, max_lines=20))

    # 2. Wyjaśnienie każdego fragmentu
    explanations = []
    for small_block in final_blocks:
        exp_text = get_explanation_for_block(small_block)
        # Możemy dodać nagłówek, np. "### Fragment kodu:\n" itd.
        # Albo od razu łączyć. Tu zrobimy po prostu w stylu:
        # "```python\n{small_block}\n```\n{exp_text}\n\n"
        chunk_result = f"```python\n{small_block}\n```\n{exp_text}\n\n"
        explanations.append(chunk_result)

    # 3. Sklejamy wszystkie fragmenty
    combined_explanation = "\n".join(explanations)
    return code_snippet, combined_explanation


# ========================================
#  Endpointy (jak w pierwotnym RAG-u, ale z "code" + "explanation")
# ========================================

@app.route("/")
def index():
    """Strona główna. Renderuje trzy panele."""
    conversations = load_conversations()
    conv_ids = list(conversations.keys())
    return render_template("index.html", conversations=conv_ids)

@app.route("/new_conversation", methods=["POST"])
def new_conversation():
    """
    Tworzy nową konwersację (pustą listę wiadomości).
    """
    conversations = load_conversations()
    new_id = str(len(conversations) + 1)
    conversations[new_id] = []  # pusta lista
    save_conversations(conversations)
    return jsonify({
        "conversation_id": new_id,
        "conversations": list(conversations.keys())
    })

@app.route("/load_conversation", methods=["POST"])
def load_conversation():
    """
    Ładuje wiadomości (lista obiektów: {code, explanation}) z wybranej konwersacji.
    """
    data = request.json
    conversation_id = data.get("conversation_id", "")
    conversations = load_conversations()
    messages = conversations.get(conversation_id, [])
    return jsonify({
        "conversation_id": conversation_id,
        "messages": messages
    })

@app.route("/delete_conversation", methods=["POST"])
def delete_conversation():
    """
    Usuwa daną konwersację z pliku.
    """
    data = request.json
    conversation_id = data.get("conversation_id", "")
    conversations = load_conversations()
    if conversation_id in conversations:
        del conversations[conversation_id]
        save_conversations(conversations)
    return jsonify({
        "status": "deleted",
        "conversation_id": conversation_id,
        "conversations": list(conversations.keys())
    })

@app.route("/reset", methods=["POST"])
def reset_chat():
    """
    Resetuje (czyści) bieżącą konwersację (ustawia pustą listę).
    """
    conversation_id = request.form.get("conversation_id", "")
    conversations = load_conversations()
    if conversation_id in conversations:
        conversations[conversation_id] = []
        save_conversations(conversations)

    return jsonify({"status": "reset", "conversation_id": conversation_id})

@app.route("/explain", methods=["POST"])
def explain():
    """
    Odbiera kod (parametr 'code') i conversation_id.
    - Jeśli conversation_id jest pusty (lub nie istnieje),
      zwraca komunikat, że trzeba najpierw wybrać/utworzyć konwersację.
    - W przeciwnym razie analizuje kod, tworzy {code, explanation} i zapisuje w danej konwersacji.
    Zwraca JSON z tym {code, explanation}, by front-end mógł wyświetlić.
    """
    code = request.form.get("code", "")
    conversation_id = request.form.get("conversation_id", "").strip()

    if not code.strip():
        return jsonify({"error": "Brak kodu do wyjaśnienia.", "code": "", "explanation": ""})

    if not conversation_id:
        return jsonify({"error": "Brak wybranej konwersacji. Utwórz lub wczytaj konwersację.",
                        "code": code, "explanation": ""})

    # Analiza kodu
    original, combined_explanation = analyze_code_snippet(code)

    # Zapisz w konwersacji
    conversations = load_conversations()
    if conversation_id not in conversations:
        conversations[conversation_id] = []

    # Dodaj nową wiadomość
    conversations[conversation_id].append({
        "code": original,
        "explanation": combined_explanation
    })
    save_conversations(conversations)

    return jsonify({
        "error": "",
        "code": original,
        "explanation": combined_explanation
    })

@app.route("/exit", methods=["POST"])
def exit_app():
    """
    Zwraca podsumowanie (liczba konwersacji i sumaryczna liczba 'wiadomości' we wszystkich konwersacjach).
    """
    conversations = load_conversations()
    summary = {
        "message": "Aplikacja została zamknięta. Dziękujemy za korzystanie!",
        "conversation_count": len(conversations),
        "questions_asked": sum(len(conv) for conv in conversations.values())
    }
    return jsonify(summary)

if __name__ == "__main__":
    app.run(debug=True)
