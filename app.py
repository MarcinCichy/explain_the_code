import os
import json
import openai
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

CONVERSATIONS_FILE = "conversations.json"


# ========================================
#  Funkcje pomocnicze
# ========================================

def load_conversations():
    """Wczytuje konwersacje z pliku JSON."""
    try:
        with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_conversations(conversations):
    """Zapisuje konwersacje do pliku JSON."""
    with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as file:
        json.dump(conversations, file, indent=4, ensure_ascii=False)

def split_code_into_blocks(code_snippet):
    """
    Dzieli kod na mniejsze kawałki, np. przy każdej definicji funkcji/klasy.
    Możesz zmodyfikować tę funkcję według własnych kryteriów.
    """
    lines = code_snippet.split('\n')
    blocks = []
    current_block = []

    for line in lines:
        # Jeśli linia zaczyna się od 'def ' lub 'class ' (po spacjach),
        # uznaj to za początek nowego „kawałka” kodu
        if line.strip().startswith('def ') or line.strip().startswith('class '):
            # Jeśli mamy już coś w current_block, dołącz to do blocks
            if current_block:
                blocks.append('\n'.join(current_block))
                current_block = []
        current_block.append(line)

    # Dodaj ostatni blok, jeśli istnieje
    if current_block:
        blocks.append('\n'.join(current_block))

    return blocks

def explain_code(code_snippet):
    """
    Wysyła do modelu OpenAI zapytanie, które prosi o WYJAŚNIENIE kodu w Pythonie
    w prostych słowach, dla dziecka (~13 lat).
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
            {"role": "user", "content": code_snippet}
        ],
        temperature=0.2
    )

    explanation = response['choices'][0]['message']['content']
    return explanation


# ========================================
#  Główne endpointy
# ========================================

@app.route("/")
def index():
    """
    Strona główna. Renderuje layout z 3 panelami:
    - lewy: konwersacje
    - środek: pole do wklejania kodu
    - prawy: obszar wyjaśnienia
    """
    conversations = load_conversations()
    conversation_ids = list(conversations.keys())
    return render_template("index.html", conversations=conversation_ids)

@app.route("/new_conversation", methods=["POST"])
def new_conversation():
    """Rozpocznij nową konwersację."""
    conversations = load_conversations()
    new_id = str(len(conversations) + 1)
    # Każda konwersacja to lista "wiadomości" (np. code + splitted_explanations)
    conversations[new_id] = []
    save_conversations(conversations)

    return jsonify({
        "conversation_id": new_id,
        "conversations": list(conversations.keys())
    })

@app.route("/load_conversation", methods=["POST"])
def load_conversation():
    """Załaduj istniejącą konwersację i jej wiadomości."""
    data = request.json
    conversation_id = data.get("conversation_id")

    conversations = load_conversations()
    messages = conversations.get(conversation_id, [])

    return jsonify({
        "conversation_id": conversation_id,
        "messages": messages
    })

@app.route("/delete_conversation", methods=["POST"])
def delete_conversation():
    """Usuń istniejącą konwersację."""
    data = request.json
    conversation_id = data.get("conversation_id")

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
    """Resetowanie aktualnej rozmowy (czyszczenie wiadomości)."""
    conversation_id = request.form.get("conversation_id", "")
    conversations = load_conversations()

    if conversation_id in conversations:
        conversations[conversation_id] = []  # pusta lista
        save_conversations(conversations)

    return jsonify({"status": "reset", "conversation_id": conversation_id})

@app.route("/explain", methods=["POST"])
def explain():
    """
    Odbiera kod, dzieli go na mniejsze bloki,
    wywołuje ChatGPT dla każdego bloku i łączy wyniki w jedną strukturę.
    Zapisuje do konwersacji.
    """
    code = request.form.get("code", "")
    conversation_id = request.form.get("conversation_id", "")

    if not code.strip():
        return jsonify({"explanations": []})

    # Podziel kod na bloki
    code_blocks = split_code_into_blocks(code)

    splitted_explanations = []
    for block in code_blocks:
        exp = explain_code(block)
        splitted_explanations.append({
            "chunk": block,
            "explanation": exp
        })

    # Zapisz w historii konwersacji
    conversations = load_conversations()
    if conversation_id not in conversations:
        conversations[conversation_id] = []

    # Dodaj nowy element (może to być cały proces analizy jednego wklejenia)
    conversations[conversation_id].append({
        "original_code": code,
        "chunks": splitted_explanations
    })
    save_conversations(conversations)

    return jsonify({"explanations": splitted_explanations})

@app.route("/exit", methods=["POST"])
def exit_app():
    """Zamykanie aplikacji z podsumowaniem."""
    conversations = load_conversations()
    summary = {
        "message": "Aplikacja została zamknięta. Dziękujemy za korzystanie!",
        "conversation_count": len(conversations),
        "questions_asked": sum(len(conv) for conv in conversations.values()),
    }

    return jsonify(summary)


if __name__ == "__main__":
    app.run(debug=True)
