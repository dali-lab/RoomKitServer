from flask import Flask, request, jsonify
from auth import require_auth

app = Flask(__name__)


@app.route('/')
def hello_world():
    return 'Hello, World!'


@app.route('/echo', methods=['GET', 'POST'])
def echo():
    if request.method == 'POST':
        return jsonify(request.json)
    else:
        return "echo"


@app.route('/authorized', methods=['POST'])
@require_auth
def authorized():
    return "Authorized! Good going"
