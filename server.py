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


@app.route('/maps', methods=['GET', 'POST'])
@require_admin(mongo=mongo)
def maps():
    if request.method == "GET":
        data = mongo.db.maps.find({"projectID": request.auth["id"]})
        for i in data:
            i.pop("trainingData", None)
            i.pop("model", None)
        return dumps(data)
    else:
        data = request.form or request.json
        if "mapName" not in data or\
                "rooms" not in data or\
                "uuid" not in data or\
                type(data["mapName"]) is not str or\
                type(data["rooms"]) is not list or\
                type(data["uuid"]) is not str:
            return "mapName and rooms fields are required"

        if mongo.db.maps.find_one({"mapName": data["mapName"], "projectID": request.auth["id"]}):
            return "mapName already taken in this project", 422

        mongo.db.maps.insert({
            "mapName": data["mapName"],
            "projectID": request.auth["id"],
            "uuid": data["uuid"],
            "rooms": data["rooms"],
            "trainingData": []
        })

        return mongo.db.maps.find_one({
            "mapName": data["mapName"],
            "projectID": request.auth["id"],
            "uuid": request.auth["uuid"]
        })


@app.route('/maps/<id>', methods=['GET'])
@require_auth(mongo)
def single_map(id):
    map = mongo.db.maps.find_one_or_404({"$or": [{"_id": ObjectId(id)}, {"uuid": id}]})
    map.pop("trainingData", None)
    map.pop("model", None)
    return dumps(map)


@app.route('/maps/<id>', methods=['PUT'])
@require_admin(mongo)
def update_training_data(id):
    map = mongo.db.maps.find_one_or_404({"_id": ObjectId(id)})
    trainingData = map["trainingData"]
    if request.json["room"] not in map["rooms"]:
        return "Unknown room", 404

    for data in request.json:
        roomIndex = map["rooms"].index(data["room"])
        this_entry = {"room": roomIndex}
        for item in data["readings"]:
            this_entry[ML.key_for_beacon(item["major"], item["minor"])] = item["strength"]
        trainingData.append(this_entry)
    map["trainingData"] = trainingData

    mongo.db.maps.update({'_id': map['_id']}, map, True)
    return "Done"


@app.route('/maps/<id>/train', methods=['POST'])
@require_admin(mongo=mongo)
def train(id):
    map = mongo.db.maps.find_one_or_404({"_id": ObjectId(id)})
    model = ML.train(map)
    string = ML.model_to_str(model)
    map["model"] = string
    mongo.db.maps.update({'_id': map['_id']}, map, True)
    return "Done"


@app.route('/maps/<id>', methods=['POST'])
@require_admin(mongo)
def predict(id):
    map = mongo.db.maps.find_one_or_404({"_id": ObjectId(id)})
    if "model" not in map:
        return "Model is not yet train", 300

    if type(request.json) is not list:
        return "Requires list of beacon readings", 422

    model = ML.load_model(map["model"])
    if model is None:
        return "Failed to load model", 302

    index = int(ML.predict(model, map, list(request.json)))
    return jsonify({
        "roomIndex": index,
        "room": map["rooms"][index]
    })


if __name__ == "__main__":
    app.run()
