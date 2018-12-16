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

# MARK: - Interface

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

# MARK: - API

# Get all the maps (for the signed in project)
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
            "uuid": i["uuid"]
        })
    
    return jsonify(array)


@app.route('/maps', methods=['POST'])
@require_admin(mongo=mongo)
def map_post():
    data = request.json
    if "name" not in data or "uuid" not in data:
        return "name and uuid fields are required", 422

    if mongo.db.maps.find_one({"name": data["name"], "projectID": request.auth["id"]}):
        return "name already taken in this project", 422

    mongo.db.maps.insert({
        "name": data["name"],
        "projectID": request.auth["id"],
        "uuid": data["uuid"]
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

    return jsonify({
        "id": str(map["_id"]),
        "name": map["name"],
        "projectID": map["projectID"],
        "uuid": map["uuid"]
    })

@app.route('/maps/<id>/rooms', methods=['GET'])
@require_auth(mongo)
def rooms(id):
    if "os" not in request.headers:
        return "os required", 422
    
    rooms = mongo.db.rooms.find({ "map": id })
    rooms = list(rooms)
    array = []
    client_os = request.headers["os"]

    for room in rooms:
        percentTrained = 0
        if ("num_samples" + client_os) in room:
            num_samples = room["num_samples-" + client_os]
            percentTrained = float(num_samples) / 500
        
        array.append({
            "name": room["name"],
            "percent_trained": percentTrained
        })
    return jsonify(array)


@app.route('/maps/<id>/rooms', methods=['POST'])
@require_admin(mongo)
def newRoom(id):
    data = request.json
    if data is None:
        return "No data!", 422
    if "name" not in data:
        return "Room needs a name", 422

    if mongo.db.rooms.find_one({ "map": id, "name": data["name"] }):
        return "Room name already taken", 422
    rooms = mongo.db.rooms.find({ "map": id })

    mongo.db.rooms.insert({
        "name": data["name"],
        "map": id,
        "label": rooms.count(),
        "num_samples": 0
    })
    return jsonify({
        "name": data["name"],
        "percent_trained": 0.0
    })


@app.route('/maps/<id>', methods=['PUT'])
@require_admin(mongo)
def update_training_data(id):
    if "os" not in request.headers:
        return "os required", 422
    
    client_os = request.headers["os"]
    roomsPercentTrained = {}

    for data in request.json:
        room = mongo.db.rooms.find_one_or_404({"name": data["room"], "map": id})

        sample = {}
        for reading in data["readings"]:
            sample[ML.key_for_beacon(reading["major"], reading["minor"])] = reading["strength"]

        mongo.db.samples.insert({
            "room": room["_id"],
            "map": id,
            "data": sample,
            "os": client_os
        })

        num_samples = mongo.db.samples.find({
            "map": id,
            "room": room["_id"],
            "os": client_os
        }).count()

        room["num_samples-" + client_os] = num_samples
        roomsPercentTrained[room["name"]] = float(num_samples) / 500
        mongo.db.rooms.update({"_id": room["_id"]}, room, True)

    return jsonify(roomsPercentTrained)


@app.route('/maps/<id>/train', methods=['POST'])
@require_admin(mongo=mongo)
def train(id):
    if "os" not in request.headers:
        return "os required", 422

    map = mongo.db.maps.find_one_or_404({"_id": ObjectId(id)})
    samples = list(mongo.db.samples.find({ "map": id, "os": request.headers["os"] }))
    if len(samples) == 0:
        return "No samples found!", 422

    roomIDs = set()
    for sample in samples:
        roomIDs.add(sample["room"])
    
    roomToLabel = {}
    for roomID in list(roomIDs):
        room = mongo.db.rooms.find_one({"_id": ObjectId(roomID)})
        if room != None:
            roomToLabel[roomID] = room["label"]
    
    trainingData = []
    for sample in samples:
        entry = sample["data"]
        entry["room"] = roomToLabel[sample["room"]]
        trainingData.append(entry)

    keys = ML.keys_for_data(trainingData)
    model = ML.train(trainingData, keys)
    modelString = ML.model_to_str(model)
    map["model-" + request.headers["os"]] = modelString
    map["keys-" + request.headers["os"]] = keys
    mongo.db.maps.update({'_id': map['_id']}, map, True)
    return "Done"


@app.route('/maps/<id>', methods=['POST'])
@require_auth(mongo)
def predict(id):
    if "os" not in request.headers:
        return "os required", 422

    client_os = request.headers["os"]

    map = mongo.db.maps.find_one_or_404({"_id": ObjectId(id)})
    if ("model-" + client_os) not in map:
        return "Model is not yet trained", 300

    if type(request.json) is not list:
        return "Requires list of beacon readings", 422

    model = ML.load_model(map["model-" + client_os])
    if model is None:
        return "Failed to load model", 302

    label = int(ML.predict(model, map["keys-" + client_os], [list(request.json)])[0])
    roomName = mongo.db.rooms.find_one({"label": label})["name"]
    return jsonify({
        "roomLabel": label,
        "room": roomName
    })

# @app.route('/maps/<id>/savebackup', methods=['POST'])
# def save_backup(id):
#
#     map = mongo.db.maps.find_one_or_404({"_id": ObjectId(id)})
#     map[request.headers["client_os"]]["trainingData"] = request.json
#
#     mongo.db.maps.update({'_id': map['_id']}, map, True)
#     return "Done"


@app.route('/maps/<id>/multiclassify', methods=['POST'])
@require_auth(mongo)
def multi_classify(id):
    if "os" not in request.headers:
        return "os required", 422

    client_os = request.headers["os"]

    map = mongo.db.maps.find_one_or_404({"_id": ObjectId(id)})
    if client_os not in map or "model" not in map[client_os]:
        return "Model is not yet trained", 300

    if type(request.json) is not list or type(list(request.json)[0]) is not list:
        return "Requires list of lists of beacon readings", 422

    model = ML.load_model(map[client_os]["model"])
    if model is None:
        return "Failed to load model", 302

    labels = ML.predict(model, map["keys-" + client_os], list(request.json))
    return jsonify([{
        "roomLabel": int(label),
        "room": mongo.db.rooms.find_one({"label": int(label)})["name"]
    } for label in labels])


if __name__ == "__main__":
    app.run()
