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
    print("=== WEBHOOK START ===")

    print("RAW DATA:", request.data)

    data = request.get_json(silent=True)

    print("JSON DATA:", data)

    return "OK", 200
    }
        )

        print("Ответ Telegram:", response.status_code, response.text)

    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
