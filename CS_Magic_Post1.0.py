import os
from datetime import datetime

import streamlit as st
import openai
import time
import json

# API-Key sicher abrufen
API_KEY = st.secrets["openai"]["api_key"]

# OpenAI-API konfigurieren
openai.api_key = API_KEY

# OpenAI-Client initialisieren
client = openai.OpenAI(api_key=API_KEY)

# Titel der App
st.title("Instagram Post Maschine")
st.write("Hallo, lass uns zusammen ein paar tolle Posts für CircleStances generieren :)")

# Text-Input-Feld
Content = st.text_input("Was für einen Post möchtest du erstellen?")

# Speichere den Status des Buttons in session_state
if "button_clicked" not in st.session_state:
    st.session_state.button_clicked = False

# Button zum Absenden
if st.button("Absenden"):
    st.session_state.button_clicked = True  # Merken, dass geklickt wurde

# Warte, bis eine Eingabe UND ein Klick erfolgt ist
if st.session_state.button_clicked and Content:
    st.write("Kein Problem, ich generiere dir Posts, die du verwenden kannst...")

# Assistant IDs
IDEA_GENERATOR_ID = "asst_6w5MxQZZ5YnN05PlyRpwOzUJ"
COPYWRITER_ID = "asst_5mOoOlozg1SI99o1OPrXtXzw"
FEEDBACK_ID = "asst_Hhy61ZANsibJuexQRrWG27LS"
POST_FINALIZER_ID = "asst_LKs01MUQaqFjUxhJgfywocHg"

def create_thread():
    """Erstellt einen neuen Thread für die Assistants."""
    response = client.beta.threads.create()  # ✅ RICHTIGE METHODE für OpenAI v1.63.0
    thread_id = response.id
    print(f"[INFO] Neuer Thread erstellt: {thread_id}")
    return thread_id

def run_assistant(assistant_id, thread_id, message):
    """
    Startet einen Assistant in einem Thread und gibt sowohl den vollständigen Prompt als auch
    die vollständige Antwort aus.
    """
    print(f"\n[PROMPT an Assistant {assistant_id}]")
    print(message)

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions=message
    )

    # Warte auf das Ergebnis
    while True:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        print(f"[DEBUG] Status von {assistant_id}: {run_status.status}")
        if run_status.status == "completed":
            break
        if run_status.status == "failed":
            print(f"[ERROR] Assistant {assistant_id} run failed.")
            return None
        time.sleep(2)  # Kurze Pause, um API-Limits nicht zu überschreiten

    # Ergebnisse abrufen
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    response_text = messages.data[0].content[0].text.value
    print(f"\n[RESPONSE von Assistant {assistant_id}]")
    print(response_text)
    return response_text

def run_assistant_new_thread(assistant_id, message, max_retries=3):
    """
    Erstellt für jeden API-Call einen neuen Thread und versucht bei einem Fehler (failed) bis zu max_retries Mal erneut.
    """
    for attempt in range(max_retries):
        new_thread_id = create_thread()
        print(f"[INFO] Neuer Thread für Assistant {assistant_id} erstellt: {new_thread_id}")
        result = run_assistant(assistant_id, new_thread_id, message)
        if result is not None:
            return result
        print(f"[WARNING] Versuch {attempt + 1} von {max_retries} fehlgeschlagen. Neuer Versuch in 2 Sekunden...")
        time.sleep(2)
    print(f"[ERROR] Assistant {assistant_id} konnte nach {max_retries} Versuchen nicht erfolgreich abgeschlossen werden.")
    return None

# Schritt 1: Ideen generieren
def generate_ideas():
    print("\n[STEP] Generiere Instagram-Content-Ideen...")
    prompt = (
        "Bitte generiere 15 Ideen für deutsche Instagram-Posts für die nachhaltige Fashion Brand CircleStances "
        "Zu diesem Thema: "
        f"{Content}\n\n"
        "Berücksichtige dabei den Brand Brief und Produkte und Beschreibungen von CircleStances "
    )
    print("\n[PROMPT für Ideen]")
    print(prompt)
    ideas = run_assistant_new_thread(IDEA_GENERATOR_ID, prompt)

    if ideas:
        with open("content_ideas.json", "w", encoding="utf-8") as file:
            json.dump({"content": ideas}, file, ensure_ascii=False, indent=2)
        print("[SAVED] Content-Ideen wurden in 'content_ideas.json' gespeichert.\n")
    return ideas

# Schritt 2: Posts schreiben
def generate_posts():
    print("\n[STEP] Erstelle fertige Instagram-Posts basierend auf den Ideen...")
    try:
        with open("content_ideas.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            ideas = data.get("content", "")
    except FileNotFoundError:
        print("[ERROR] Datei 'content_ideas.json' nicht gefunden. Hast du 'generate_ideas()' aufgerufen?")
        return None

    if not ideas:
        print("[ERROR] Der Inhalt aus 'content_ideas.json' ist leer.")
        return None

    prompt = (
        f"{ideas}\n\n"
        "Bitte formuliere aus all diesen Ideen Instagram-Posts, passend zum Brand Brief von CircleStances. "
        "Die Posts sollten 250-350 Zeichen haben und passende Hashtags am Ende. Nutze Emojis wo es passt."
    )
    print("\n[PROMPT für Posts]")
    print(prompt)

    posts = run_assistant_new_thread(COPYWRITER_ID, prompt)

    if posts is None:
        print("[ERROR] Es wurden keine Posts generiert. Möglicherweise gab es einen API-Fehler.")
        return None

    with open("generated_posts.json", "w", encoding="utf-8") as file:
        json.dump({"content": posts}, file, ensure_ascii=False, indent=2)
    print("[SAVED] Generierte Posts wurden in 'generated_posts.json' gespeichert.\n")
    return posts

# Schritt 3: Feedback einholen
def get_feedback():
    print("\n[STEP] Hole Feedback für die generierten Instagram-Posts ein...")
    try:
        with open("generated_posts.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            posts = data.get("content", "")
    except FileNotFoundError:
        print("[ERROR] Datei 'generated_posts.json' nicht gefunden. Hast du 'generate_posts()' aufgerufen?")
        return None

    prompt = (
        f"{posts}\n\n"
        "Bitte prüfe wie gut die Posts, diese Posts zum Brand Brief und der Tonalität von CircleStances passen, "
        "Bitte gib einen Score von 0,1-9,9 an und ordne sie entsprechend ihrer Reihenfolge von gut bis schlecht. "
        "Sei kritisch. Bitte gib 7 Posts aus, die sehr gut sind! "
        "Achte darauf, dass sie eine gewisse Diversität abbilden, also ein guter Mix für mehrere Wochen sind. "
        "Es sollte mindestens ein Post dabei sein, der ein bestimmtes Produkt vorstellt. "
        "Bitte schreibe den kompletten Post und füge die jeweilige Bewertung und Verbesserungsvorschläge hinzu."
    )
    print("\n[PROMPT für Feedback]")
    print(prompt)
    feedback = run_assistant_new_thread(FEEDBACK_ID, prompt)

    if feedback:
        with open("feedback.json", "w", encoding="utf-8") as file:
            json.dump({"content": feedback}, file, ensure_ascii=False, indent=2)
        print("[SAVED] Feedback wurde in 'feedback.json' gespeichert.\n")
    return feedback

# Schritt 4: Verbesserte Posts erstellen
def refine_posts():
    print("\n[STEP] Wende das Feedback auf die besten Posts an...")
    try:
        with open("feedback.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            feedback = data.get("content", "")
    except FileNotFoundError:
        print("[ERROR] Datei 'feedback.json' nicht gefunden. Hast du 'get_feedback()' aufgerufen?")
        return None

    prompt = (
        f"{feedback}\n\n"
        "Bitte arbeite das Feedback zu den jeweiligen Posts in die Posts ein und schreibe sie neu. "
        "Die Posts sollten etwas länger sein. Bitte zwischen 300 und 450 Zeichen. Nnutze Emojis wo es sinnvoll ist. "
        "Berücksichtige auch, dass die Ansprache zum Brand Voicing von CircleStances passt. "
        "Gib die fertigen Posts in absteigender Reihenfolge von gut bis schlecht aus. "
    )
    print("\n[PROMPT für verbesserte Posts]")
    print(prompt)
    refined_posts = run_assistant_new_thread(POST_FINALIZER_ID, prompt)

    if refined_posts:
        with open("final_posts.json", "w", encoding="utf-8") as file:
            json.dump({"content": refined_posts}, file, ensure_ascii=False, indent=2)
        print("[SAVED] Überarbeitete Posts wurden in 'final_posts.json' gespeichert.\n")
    return refined_posts

# Den gesamten Workflow ausführen
def main():
    print("\n[START] Starte den Instagram-Post-Workflow...\n")

    ideas = generate_ideas()
    if ideas:
        posts = generate_posts()
    else:
        print("[ERROR] Keine Ideen generiert. Beende Workflow.")
        return

    if posts:
        feedback = get_feedback()
    else:
        print("[ERROR] Keine Posts generiert. Beende Workflow.")
        return

    if feedback:
        refined_posts = refine_posts()
    else:
        print("[ERROR] Kein Feedback erhalten. Beende Workflow.")
        return

    # Anstatt die finalen Posts als .txt-Datei zu speichern, werden sie hier direkt in Streamlit angezeigt.
    st.subheader("📄 Finale Instagram-Posts")
    st.text_area("Finale Posts", refined_posts, height=400)

    print("\n--- FINALER OUTPUT ---\n")
    print(refined_posts)
    print("\n[END] Der Workflow ist abgeschlossen!\n")

if __name__ == "__main__":
    print(f"OpenAI Version: {openai.__version__}")
    test_thread_id = create_thread()
    print(f"Erstellter Thread: {test_thread_id}")
    main()
