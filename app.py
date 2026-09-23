
from flask import Flask, request
import os
import requests

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")


@app.route("/")
def hello():
    return "Electronic_bot работает!"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)

    if not data:
        return "OK", 200

    message = data.get("message")

    if not message:
        return "OK", 200

    chat = message.get("chat")
    if not chat:
        return "OK", 200

    chat_id = chat.get("id")
    text = message.get("text", "")

    if not chat_id:
        return "OK", 200

    if text == "/start":
        answer = "Привет! Я Electronic_bot 🤖"
    elif text:
        answer = f"Ты написал: {text}"
    else:
        answer = "Я пока умею отвечать только на текстовые сообщения."

    telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        response = requests.post(
            telegram_url,
            json={
                "chat_id": chat_id,
                "text": answer
            },
            timeout=10
        )

        print(
            "Telegram:",
            response.status_code,
            response.text
        )

    except Exception as e:
        print("Ошибка отправки в Telegram:", e)

    return "OK", 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
