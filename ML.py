from sklearn.neural_network import MLPClassifier
import pickle


def train(map, client_os):
    clf = MLPClassifier(solver='lbfgs',
                        alpha=1e-5,
                        hidden_layer_sizes=(5, 2),
                        random_state=1)
    keys = set()
    maxes = {}
    for data in map[client_os]["trainingData"]:
        for item in data:
            if item != "room":
                keys.add(item)
                if item not in maxes or maxes[item] < data[item]:
                    maxes[item] = data[item]
    keys = list(keys)
    keys.sort()

    X = []
    Y = []
    for data in map[client_os]["trainingData"]:
        entry = []
        for item in keys:
            if item in data and float(data[item]) != 0:
                entry.append(float(data[item]))
            else:
                entry.append(maxes[item])
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


def predict(model, map, beacons, client_os):
    keys = set()
    maxes = {}
    for data in map[client_os]["trainingData"]:
        for item in data:
            if item != "room":
                keys.add(item)
                if item not in maxes or maxes[item] < data[item]:
                    maxes[item] = data[item]
    keys = list(keys)
    keys.sort()

    X = [maxes[key] for key in keys]
    for beacon in beacons:
        major = beacon['major']
        minor = beacon['minor']
        key = key_for_beacon(major, minor)
        if key not in keys or float(beacon["strength"]) == 0:
            continue
        X[keys.index(key)] = float(beacon["strength"])
    print(X)

    return model.predict([X])[0]

