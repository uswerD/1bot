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
    data = request.json

    print("Получено от Telegram:", data)

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            answer = "Привет! Я Electronic_bot 🤖"
        else:
            answer = f"Ты написал: {text}"

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": answer
            }
        )

        print("Ответ Telegram:", response.status_code, response.text)

    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
