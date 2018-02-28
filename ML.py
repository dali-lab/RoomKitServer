from sklearn.neural_network import MLPClassifier
import pickle


def train(map):
    clf = MLPClassifier(solver='lbfgs',
                        alpha=1e-5,
                        hidden_layer_sizes=(5, 2),
                        random_state=1)
    keys = set()
    for data in map["trainingData"]:
        for item in data:
            if item != "room":
                keys.add(item)
    keys = list(keys)
    keys.sort()

    X = []
    Y = []
    for data in map["trainingData"]:
        entry = []
        all_neg1 = True
        for item in keys:
            if item in data and float(data[item]) != -1 and float(data[item]) != 0:
                all_neg1 = False
                entry.append(1/float(data[item]))
            else:
                entry.append(0)
        if not all_neg1:
            Y.append(int(data["room"]))
            X.append(entry)

    clf.fit(X, Y)
    return clf


def key_for_beacon(major, minor):
    return str(major) + ":" + str(minor)


def model_to_str(model):
    return pickle.dumps(model)


def load_model(string):
    """
    Loads the model from a string
    :param string: The string
    :return: MLPClassifier
    """
    return pickle.loads(string)


def predict(model, map, beacons):
    keys = set()
    for data in map["trainingData"]:
        for item in data:
            if item != "room":
                keys.add(item)
    keys = list(keys)
    keys.sort()

    X = [None] * len(keys)
    for beacon in beacons:
        major = beacon['major']
        minor = beacon['minor']
        key = key_for_beacon(major, minor)
        if key not in keys or float(beacon["strength"]) == -1:
            X[keys.index(key)] = 0
            continue
        X[keys.index(key)] = float(beacon["strength"])

    return model.predict([X])[0]

