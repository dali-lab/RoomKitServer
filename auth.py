from flask import request
from functools import wraps
import random


class require_auth:
    def __init__(self, mongo):
        self.mongo = mongo

    def __call__(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "authorization" in request.headers:
                registration = self.mongo.db.authKeys.find_one({
                    "$or": [
                        {
                            "admin_key": request.headers["authorization"]
                        },
                        {
                            "user_key": request.headers["authorization"]
                        }
                    ]
                })
                if registration is not None:
                    registration.pop("admin_key", None)
                    registration.pop("user_key", None)
                    request.auth = registration
                    request.auth["id"] = str(registration["_id"])
                    return f(*args, **kwargs)
            return "Unauthorized", 401
        return decorated


class require_admin:
    def __init__(self, mongo):
        self.mongo = mongo

    def __call__(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "authorization" in request.headers:
                registration = self.mongo.db.authKeys.find_one({
                    "admin_key": request.headers["authorization"]
                })
                if registration is not None:
                    registration.pop("admin_key", None)
                    registration.pop("user_key", None)
                    request.auth = registration
                    request.auth["id"] = str(registration["_id"])
                    return f(*args, **kwargs)
            return "Unauthorized", 401
        return decorated


def register_auth(project_name, email, mongo):
    assert project_name is not None and mongo is not None
    if mongo.db.authKeys.find_one({"name": project_name}) is not None:
        return False, None, None

    existing = None
    admin_key = None
    while existing is not None or admin_key is None:
        admin_key = hex(random.getrandbits(200)).replace("0x", "")
        existing = mongo.db.authKeys.find_one({"admin_key": admin_key})

    existing = None
    user_key = None
    while existing is not None or user_key is None:
        user_key = hex(random.getrandbits(200)).replace("0x", "")
        existing = mongo.db.authKeys.find_one({"user_key": user_key})

    mongo.db.authKeys.insert({
        "name": project_name,
        "email": email,
        "admin_key": admin_key,
        "user_key": user_key
    })
    return True, admin_key, user_key
