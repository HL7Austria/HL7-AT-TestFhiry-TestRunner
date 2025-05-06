from flask import Flask, jsonify, request
import os
import json

app = Flask(__name__)
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "test_script_json_files", "TestScript-testscript-json")

@app.route("/scripts", methods=["GET"])
def list_scripts():
    files = [f for f in os.listdir(SCRIPT_PATH) if f.endswith(".json")]
    return jsonify(files)

@app.route("/scripts/<filename>", methods=["GET"])
def get_script(filename):
    full_path = os.path.join(SCRIPT_PATH, filename)
    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404
    with open(full_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/scripts/<filename>/summary", methods=["GET"])
def get_script_summary(filename):
    full_path = os.path.join(SCRIPT_PATH, filename)
    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404
    with open(full_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    summary = {
        "id": data.get("id"),
        "name": data.get("name"),
        "description": data.get("description"),
        "test_count": len(data.get("test", []))
    }
    return jsonify(summary)

if __name__ == "__main__":
    app.run(debug=True)
