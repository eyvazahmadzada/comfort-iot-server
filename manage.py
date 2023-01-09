from flask import Flask, request, jsonify
from flask_restful import Resource, Api, reqparse
from bson.json_util import dumps
from bson.objectid import ObjectId
from bson.errors import InvalidId
import json
from pymongo import MongoClient
from datetime import datetime, timedelta
from itertools import combinations
import ahpy
import jwt
from flask_bcrypt import Bcrypt
from functools import wraps
from flask_cors import CORS


app = Flask(__name__)
api = Api(app)
CORS(app, resources={r"/*": {"origins": "*"}})
client = MongoClient(
    'mongodb+srv://iot:iotproject@cluster0.wow2pnq.mongodb.net/?retryWrites=true&w=majority')
db = client.flask_db
rooms = db.rooms

parser = reqparse.RequestParser()


bcrypt = Bcrypt(app)
# @TODO: global env
secret_key = "a252503e7f7748beacd4a22e37842224"


# Decorater for protected routes

def tokenReq(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "Authorization" in request.headers:
            # return jsonify('hsda')
            token = request.headers["Authorization"]
            token = token.split()[1]
            try:
                jwt.decode(token, secret_key, algorithms=['HS256'])
            except:
                return jsonify({"status": "fail", "message": "unauthorized"}), 401
            return f(*args, **kwargs)
        else:
            return jsonify({"status": "fail", "message": "unauthorized"}), 401
    return decorated


class ROOMS(Resource):
    def get(self):

        # @TODO: we need to add AHP importance filtering based on user preference
        # So, just another parameter AHPObj would be enough:
        # AHPObj: {
        # 'temperature, humidity': 0.2,
        # 'temperature', pressure': 3,
        # ...
        # }

        # This

        ROOMS_OBJECT = {}

        where_clause = {}

        search_room = request.args.get("search_room")

        min_temperature = request.args.get("min_temperature")
        max_temperature = request.args.get("max_temperature")

        min_humidity = request.args.get("min_humidity")
        max_humidity = request.args.get("max_humidity")

        min_light = request.args.get("min_light")
        max_light = request.args.get("max_light")

        min_pressure = request.args.get("min_pressure")
        max_pressure = request.args.get("max_pressure")
        if search_room != None:
            where_clause['room.room_name'] = search_room

        # filter based on the given min and max temperature
        if min_temperature != None and max_temperature != None:
            where_clause['room.temperature'] = {
                '$gte': int(min_temperature), '$lte': int(max_temperature)}
        # filter based on the given min and max humidity

        if min_humidity != None and max_humidity != None:
            where_clause['room.humidity'] = {
                '$gte': int(min_humidity), '$lte': int(max_humidity)}
        # filter based on the given min and max light
        if min_light != None and max_light != None:
            where_clause['room.light'] = {
                '$gte': int(min_light), '$lte': int(max_light)}
        # filter based on the given min and max pressure
        if min_pressure != None and max_pressure != None:
            where_clause['room.pressure'] = {
                '$gte': int(min_pressure), '$lte': int(max_pressure)}

        all_rooms = rooms.aggregate(
            [
                {"$sort": {"room.time": -1}
                 }, {"$match": where_clause},
                {"$group": {"_id": "$room.room_name", "doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$doc"}},
            ])
        ROOMS_OBJECT = json.loads(dumps(all_rooms, default=str))
        return ROOMS_OBJECT


class ROOM(Resource):
    def get(self, room_name):
        current_time = datetime.datetime.utcnow()
        past_time = current_time - datetime.timedelta(hours=24)
        past_time = past_time.strftime('%Y-%m-%d %H:%M:%S')
        current_time = current_time.strftime('%Y-%m-%d %H:%M:%S')

        try:
            room = rooms.find({"room.room_name": room_name, 'room.time': {
                              '$gte': past_time, '$lte': current_time}})
            room = json.loads(dumps(room, default=str))
            if not room:
                return "Not found", 404

            # Group the documents by 3 hour intervals
            data = {}
            for doc in room:
                time = datetime.datetime.strptime(
                    doc['room']['time'], '%Y-%m-%d %H:%M:%S')
                interval = (time.hour // 3) * 3
                if interval not in data:
                    data[interval] = []
                data[interval].append(doc)
            averages = {}
            for interval, documents in data.items():
                temperature_sum = 0
                humidity_sum = 0
                light_sum = 0
                pressure_sum = 0
                count = len(documents)
                for doc in documents:
                    temperature_sum += doc['room']['temperature']
                    humidity_sum += doc['room']['humidity']
                    light_sum += doc['room']['light']
                    pressure_sum += doc['room']['pressure']
                averages[f"{interval}-{interval+3}"] = {
                    'temperature': temperature_sum / count,
                    'humidity': humidity_sum / count,
                    'light': light_sum / count,
                    'pressure': pressure_sum / count
                }
            return averages
        except InvalidId:
            return "Not found", 404


@ app.route('/rooms/average_values')
def averageValues():

    current_time = datetime.datetime.utcnow()
    past_time = current_time - datetime.timedelta(hours=24)
    past_time = past_time.strftime('%Y-%m-%d %H:%M:%S')
    current_time = current_time.strftime('%Y-%m-%d %H:%M:%S')

    query = {'room.time': {'$gte': past_time, '$lte': current_time}}
    documents = rooms.find(query)
    if not documents:
        return jsonify('No data in the last 24 hours.')

    # Group the documents by 3 hour intervals
    data = {}
    for doc in documents:
        time = datetime.datetime.strptime(
            doc['room']['time'], '%Y-%m-%d %H:%M:%S')
        interval = (time.hour // 3) * 3
        if interval not in data:
            data[interval] = []
        data[interval].append(doc)

    averages = {}
    for interval, documents in data.items():
        temperature_sum = 0
        humidity_sum = 0
        light_sum = 0
        pressure_sum = 0
        count = len(documents)
        for doc in documents:
            temperature_sum += doc['room']['temperature']
            humidity_sum += doc['room']['humidity']
            light_sum += doc['room']['light']
            pressure_sum += doc['room']['pressure']
        averages[f"{interval}-{interval+3}"] = {
            'temperature': temperature_sum / count,
            'humidity': humidity_sum / count,
            'light': light_sum / count,
            'pressure': pressure_sum / count
        }
    return averages


class AHPImportance(Resource):
    def get(self):
        print('some code')
        # @TODO Need to create a table for AHP importance in DB
        # It should basically store this object:
        # AHPObj: {
        # 'temperature, humidity': 0.2,
        # 'temperature', pressure': 3,
        # }

    def put(self, updatedAHPObj):
        print('some code')
        # @TODO updatedImportance is also an object - same type as AHPObj


@app.route('/test')
@tokenReq
def test():
    return jsonify('jwt works.')


@app.route('/login', methods=['POST'])
def login():
    message = ""
    res_data = {}
    code = 500
    status = "fail"

    try:
        data = {}
        data['email'] = request.form.get('email')
        data['password'] = request.form.get('password')
        # return jsonify('ge')
        user = db['users'].find_one({"email": f'{data["email"]}'})

        if user:
            user['_id'] = str(user['_id'])
            if user and bcrypt.check_password_hash(user['password'], data['password']):
                time = datetime.utcnow() + timedelta(hours=24)
                token = jwt.encode({
                    "user": {
                        "email": f"{user['email']}",
                        "id": f"{user['_id']}",
                    },
                    "exp": time
                }, secret_key)

                del user['password']

                message = f"User authenticated"
                code = 200
                status = "successful"
                res_data['token'] = token
                res_data['user'] = user

            else:
                message = "Wrong password"
                code = 401
                status = "fail"
        else:
            message = "Invalid login details"
            code = 401
            status = "Fail"

    except Exception as ex:
        message = f"{ex}"
        code = 500
        status = "fail"
    return jsonify({"data": res_data, 'status': status, "message": message})


def calculateAHPOrder(AHPObj):
    # AHPObj format same as above
    # @TODO: AHPObj needs to be converted to the following format (object key: tuples, value: float):
    # {
    #   ('Temperature', 'Humidity'): 0.2,
    # ('Temperature', 'Pressure'): 3,
    # ('Temperature', 'Light'): 7,
    # ('Humidity', 'Pressure'): 4,
    # ('Humidity', 'Light'): 0.3333333333333333,
    # ('Pressure', 'Light'): 2
    # }

    rooms = ['room_106', 'room_108', 'room_215', 'room_104']
    room_pairs = list(combinations(rooms, 2))
    # room_pairs returns:
    # [('room_106', 'room_108'),
    # ('room_106', 'room_215'),
    # ('room_106', 'room_104'),
    # ('room_108', 'room_215'),
    # ('room_108', 'room_104'),
    # ('room_215', 'room_104')]

    # These are dummy data, and they represent importance for each pair:
    # ('room_106', 'room_108'): 1/5
    # ('room_106', 'room_215'): 3
    # ...
    temperature_values = [1/5, 3, 7, 4, 1/3, 2]
    humidity_values = [1/3, 4, 8, 1, 1/2, 3]
    pressure_values = [1/5, 7, 7, 2, 1/3, 2]
    light_values = [1/5, 3, 6, 4, 1/3, 5]

    # So how do we calculate them?
    # 1. Get average parameter value (temp, humidity, pressure...) for each room in the last 24h
    # 2. Divide values for pairs by each other.
    # So if temp is 5 for room_106 and 25 for room_108, ('room_106', 'room_108') will be 1/5 (5/25) - 0.2

    temperature_comparisons = dict(zip(room_pairs, temperature_values))
    humidity_comparisons = dict(zip(room_pairs, humidity_values))
    pressure_comparisons = dict(zip(room_pairs, pressure_values))
    light_comparisons = dict(zip(room_pairs, light_values))

    temperature = ahpy.Compare(
        'Temperature', temperature_comparisons, precision=3, random_index='saaty')
    humidity = ahpy.Compare('Humidity', humidity_comparisons,
                            precision=3, random_index='saaty')
    pressure = ahpy.Compare('Pressure', pressure_comparisons,
                            precision=3, random_index='saaty')
    light = ahpy.Compare('Light', light_comparisons,
                         precision=3, random_index='saaty')
    criteria = ahpy.Compare('Criteria', criteria_comparisons,
                            precision=3, random_index='saaty')

    criteria.add_children([temperature, humidity, pressure, light])

    print(criteria.target_weights)
    # {'room_106': 0.344, 'room_108': 0.335, 'room_104': 0.178, 'room_215': 0.144}

    # After getting the value of criteria.target_weights, we just need to sort rooms by value (descending):
    # room_108, room_106, room_104, room_215 - this is the end result of the calculation


api.add_resource(ROOMS, '/rooms')
api.add_resource(ROOM, '/rooms/<room_name>/')


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8087)
