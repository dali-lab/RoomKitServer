from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from auth import require_auth, require_admin, register_auth
from render import render_register_page, render_home_page
from bson.json_util import dumps
from bson.objectid import ObjectId
import ML
import os


app = Flask(__name__)
app.config['MONGO_URI'] = os.environ['MONGO_URI']
mongo = PyMongo(app)
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']


@app.route('/')
def homepage(): return render_home_page()


@app.route('/authenticated', methods=['GET'])
@require_auth(mongo)
def authenticated(): return "Success"


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_register_page()
    else:
        success, admin_key, user_key = register_auth(request.form["project"], request.form["email"], mongo)
        if not success:
            return "Project name taken", 422
        return "Your admin key: '" + admin_key + "'\nYour user key: '" + user_key + "'"


@app.route('/maps')
@require_auth(mongo)
def maps():
    data = mongo.db.maps.find({"projectID": request.auth["id"]})
    array = []
    for i in data:
        array.append({
            "id": str(i["_id"]),
            "name": i["name"],
            "projectID": i["projectID"],
            "uuid": i["uuid"],
            "rooms": i["rooms"]
        })
    return jsonify(array)


@app.route('/maps', methods=['POST'])
@require_admin(mongo=mongo)
def map_post():
    data = request.json
    if "name" not in data or\
            "rooms" not in data or\
            "uuid" not in data or\
            type(data["name"]) is not str or\
            type(data["rooms"]) is not list or\
            type(data["uuid"]) is not str:
        return "name and rooms fields are required", 422

    if mongo.db.maps.find_one({"name": data["name"], "projectID": request.auth["id"]}):
        return "name already taken in this project", 422

    mongo.db.maps.insert({
        "name": data["name"],
        "projectID": request.auth["id"],
        "uuid": data["uuid"],
        "rooms": data["rooms"]
    })

    object = mongo.db.maps.find_one({
        "name": data["name"],
        "projectID": request.auth["id"],
        "uuid": data["uuid"]
    })
    object["id"] = str(object.pop("_id", None))

    return jsonify(object)


@app.route('/maps/<id>', methods=['GET'])
@require_auth(mongo)
def single_map(id):
    map = mongo.db.maps.find_one_or_404({"$or": [{"_id": ObjectId(id)}, {"uuid": id}]})
    return dumps({
        "id": str(map["_id"]),
        "name": map["name"],
        "projectID": map["projectID"],
        "uuid": map["uuid"],
        "rooms": map["rooms"]
    })


@app.route('/maps/<id>', methods=['PUT'])
@require_admin(mongo)
def update_training_data(id):
    if "client_os" not in request.headers:
        return "client_os required", 422

    client_os = request.headers["client_os"]

    map = mongo.db.maps.find_one_or_404({"_id": ObjectId(id)})
    if client_os not in map:
        map[client_os] = {
            "trainingData": []
        }
    trainingData = map[client_os]["trainingData"]

    for data in request.json:
        if data["room"] not in map["rooms"]:
            return "Unknown room", 404
        roomIndex = map["rooms"].index(data["room"])
        this_entry = {"room": roomIndex}
        for item in data["readings"]:
            this_entry[ML.key_for_beacon(item["major"], item["minor"])] = item["strength"]

        if len(this_entry.keys()) <= 1:
            continue
        trainingData.append(this_entry)
    map[client_os]["trainingData"] = trainingData

    mongo.db.maps.update({'_id': map['_id']}, map, True)
    return "Done"


@app.route('/maps/<id>/train', methods=['POST'])
@require_admin(mongo=mongo)
def train(id):
    if "client_os" not in request.headers:
        return "client_os required", 422

    client_os = request.headers["client_os"]

    map = mongo.db.maps.find_one_or_404({"_id": ObjectId(id)})

    if client_os not in map:
        return "No training data available", 422

    model = ML.train(map, client_os)
    string = ML.model_to_str(model)
    map[client_os]["model"] = string
    mongo.db.maps.update({'_id': map['_id']}, map, True)
    return "Done"


@app.route('/maps/<id>', methods=['POST'])
@require_auth(mongo)
def predict(id):
    if "client_os" not in request.headers:
        return "client_os required", 422

    client_os = request.headers["client_os"]

    map = mongo.db.maps.find_one_or_404({"_id": ObjectId(id)})
    if "model" not in map:
        return "Model is not yet train", 300

    if type(request.json) is not list:
        return "Requires list of beacon readings", 422

    model = ML.load_model(map[client_os]["model"])
    if model is None:
        return "Failed to load model", 302

    index = int(ML.predict(model, map, list(request.json), client_os))
    return jsonify({
        "roomIndex": index,
        "room": map["rooms"][index]
    })


if __name__ == "__main__":
    app.run()
