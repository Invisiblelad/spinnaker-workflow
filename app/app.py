import os
from flask import Flask, jsonify

app = Flask(__name__)

VERSION = os.environ.get("APP_VERSION", "dev")


@app.route("/")
def index():
    return jsonify({
        "message": "Hello from the Spinnaker + Jenkins + Docker + Kubernetes pipeline!",
        "version": VERSION
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)