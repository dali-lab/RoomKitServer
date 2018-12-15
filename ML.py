from sklearn.neural_network import MLPClassifier
import pickle


def train(trainingData, keys):
    clf = MLPClassifier(solver='lbfgs',
                        alpha=1e-5,
                        hidden_layer_sizes=(100, 10),
                        random_state=1)

    X = []
    Y = []
    for data in trainingData:
        entry = []
        for item in keys:
            if item in data and float(data[item]) != 0:
                entry.append(1/float(data[item]))
            else:
                entry.append(0)
        Y.append(int(data["room"]))
        X.append(entry)

    clf.fit(X, Y)
    return clf

def keys_for_data(trainingData):
    keys = set()
    for data in trainingData:
        for item in data:
            if item != "room":
                keys.add(item)
    keys = list(keys)
    keys.sort()
    return keys

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


def predict(model, keys, beaconsLists):
    X = []
    for beacons in beaconsLists:
        x = [0] * len(keys)
        for beacon in beacons:
            major = beacon['major']
            minor = beacon['minor']
            key = key_for_beacon(major, minor)
            if key not in keys or float(beacon["strength"]) == 0:
                continue
            x[keys.index(key)] = 1/float(beacon["strength"])
        X.append(x)
    print(X)

    return model.predict(X)
