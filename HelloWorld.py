from flask import Flask
from flask_pymongo import PyMongo

app = Flask(__name__)
mongo = PyMongo(app)


@app.route('/')
def hello_world():
    return 'Hello, World!'
