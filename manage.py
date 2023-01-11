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
    def post(self):

        ahp_object = request.form.get('ahp_object')

        # example:
        # ahpObj = {
        #     'temperature, humidity': 0.2,
        #     'temperature, pressure': 3,
        #     'temperature, light': 7,
        #     'humidity, pressure': 4,
        #     'humidity, light': 0.3333333333333333,
        #     'pressure, light': 2,
        # }

        if ahp_object != None and ahp_object != '':
            ahpObj = json.loads(ahp_object)
        else:
            ahpDoc = db['ahp'].find_one()
            ahpObj = ahpDoc['ahp']

        ahp_criteria = calculateAHPOrder(ahpObj)
        # print(criteria_comparisons)

        ROOMS_OBJECT = {}

        where_clause = {}

        search_room = request.form.get("search_room")

        min_temperature = request.form.get("min_temperature")
        max_temperature = request.form.get("max_temperature")

        min_humidity = request.form.get("min_humidity")
        max_humidity = request.form.get("max_humidity")

        min_light = request.form.get("min_light")
        max_light = request.form.get("max_light")

        min_pressure = request.form.get("min_pressure")
        max_pressure = request.form.get("max_pressure")
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
        all_rooms = sort_rooms(all_rooms, ahp_criteria)

        ROOMS_OBJECT = json.loads(dumps(all_rooms, default=str))
        return ROOMS_OBJECT


class ROOM(Resource):
    def get(self, room_name):
        current_time = datetime.utcnow()
        past_time = current_time - timedelta(hours=24)
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
                time = datetime.strptime(
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

    current_time = datetime.utcnow()
    past_time = current_time - timedelta(hours=24)
    past_time = past_time.strftime('%Y-%m-%d %H:%M:%S')
    current_time = current_time.strftime('%Y-%m-%d %H:%M:%S')

    query = {'room.time': {'$gte': past_time, '$lte': current_time}}
    documents = rooms.find(query)
    if not documents:
        return jsonify('No data in the last 24 hours.')

    # Group the documents by 3 hour intervals
    data = {}
    for doc in documents:
        time = datetime.strptime(
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

        ahpDoc = db['ahp'].find_one()
        return ahpDoc['ahp']

    def put(self):
        ahp_object = request.form.get('data')

        # example:
        # ahpObj = {
        #     'temperature, humidity': 0.2,
        #     'temperature, pressure': 3,
        #     'temperature, light': 7,
        #     'humidity, pressure': 4,
        #     'humidity, light': 0.3333333333333333,
        #     'pressure, light': 2,
        # }

        try:
            if ahp_object != None and ahp_object != '':
                ahpObj = json.loads(ahp_object)
                db['ahp'].update_one({}, {"$set": ahpObj})
                message = f"Successfuly updated ahp object"
                code = 200
                status = "successful"
            else:
                message = f"{ex}"
                code = 401
                status = "Invalid parameters"

        except Exception as ex:
            message = f"{ex}"
            code = 500
            status = "fail"

        return jsonify({'status': status, "message": message})


@app.route('/verify_token')
@tokenReq
def verify_token():
    return jsonify('jwt works.')


@app.route('/login', methods=['POST'])
def login():
    message = ""
    res_data = {}
    code = 500
    status = "fail"

    try:
        data = {}
        data['email'] = request.get_json()['email']
        data['password'] = request.get_json()['password']
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

    # AHPObj: {
    # 'temperature, humidity': 0.2,
    # 'temperature', pressure': 3,
    # }


def sort_rooms(data, values):
    sorted_data = sorted(data, key=lambda x: values.get(
        x['room']['room_name']), reverse=True)
    return sorted_data


def calculateAHPTempImportance(val1, val2, min, max, best):
    # If both are outside the comfort temperature values, prefer both equally
    if ((val1 <= min or val1 >= max) and (val2 <= min or val2 >= max)) or val1 == val2:
        return 1
    else:
        # If one of them is outside, extremely prefer the other one
        if val1 <= min or val1 >= max:
            return 1/9
        elif val2 <= min or val2 >= max:
            return 9
        else:  # Both of them are inside comfort values
            val1Dis = abs(20 - val1)
            val2Dis = abs(20 - val2)

            # Calculate different between how close they are to the perfect value
            diff = val1Dis - val2Dis

            if diff < 0:  # val1 is closer to 20
                return abs(diff)+1
            else:  # val2 is closer to 20
                return 1/(diff+1)


def calculateAHPOrder(AHPObj):

    # serialize the ahp object to the required format by ahp library
    criteria_comparisons = {
        tuple(key.title().split(', ')): value for key, value in AHPObj.items()}
    # new format:
    #  {
    #        ('Temperature', 'Humidity'): 0.2,
    #        ('Temperature', 'Pressure'): 3,
    # }

    room_names = ['room_106', 'room_108', 'room_215', 'room_111']
    room_pairs = list(combinations(room_names, 2))
    # room_pairs returns:
    # [('room_106', 'room_108'),
    # ('room_106', 'room_215'),
    # ('room_106', 'room_111'),
    # ('room_108', 'room_215'),
    # ('room_108', 'room_111'),
    # ('room_215', 'room_111')]

    # Get average parameter value (temp, humidity, pressure...) for each room in the last 24h
    past_24_hours = datetime.utcnow() - timedelta(hours=24)
    past_24_hours = past_24_hours.strftime('%Y-%m-%d %H:%M:%S')
    pipeline = [
        {"$match": {"room.time": {"$gte": past_24_hours}}},
        {"$group": {"_id": "$room.room_name",
                    "temperature": {"$avg": "$room.temperature"},
                    "humidity": {"$avg": "$room.humidity"},
                    "light": {"$avg": "$room.light"},
                    "pressure": {"$avg": "$room.pressure"}
                    }
         }
    ]

    averages = {}
    for doc in rooms.aggregate(pipeline):
        averages[doc['_id']] = {
            "temperature": float(doc["temperature"]),
            "humidity": float(doc["humidity"]),
            "light": float(doc["light"]),
            "pressure": float(doc["pressure"])
        }
    # averages returns (example):
    # {
    #   "room_205": {
    #              "temperature": 24.3,
    #              "humidity" : 12,
    #              "light": 3,
    #              "pressure": 4
    #     },
    # }

    print(criteria_comparisons)

    # 1. Get average parameter value (temp, humidity, pressure...) for each room in the last 24h
    # 2. Divide values for pairs by each other.
    # So if temp is 5 for room_106 and 25 for room_108, ('room_106', 'room_108') will be 1/5 (5/25) - 0.2
    temperature_values = [
        calculateAHPTempImportance(
            averages['room_106']['temperature'], averages['room_108']['temperature'], 16, 24, 20),

        averages['room_106']['temperature'] /
        averages['room_215']['temperature'],

        averages['room_106']['temperature'] /
        averages['room_111']['temperature'],

        averages['room_108']['temperature'] /
        averages['room_215']['temperature'],

        averages['room_108']['temperature'] /
        averages['room_111']['temperature'],

        averages['room_215']['temperature'] /
        averages['room_111']['temperature'],
    ]
    humidity_values = [
        calculateAHPTempImportance(
            averages['room_106']['humidity'], averages['room_108']['humidity'], 26, 34, 30),
        averages['room_106']['humidity'] /
        averages['room_108']['humidity'],

        averages['room_106']['humidity'] /
        averages['room_215']['humidity'],

        averages['room_106']['humidity'] /
        averages['room_111']['humidity'],

        averages['room_108']['humidity'] /
        averages['room_215']['humidity'],

        averages['room_108']['humidity'] /
        averages['room_111']['humidity'],

        averages['room_215']['humidity'] /
        averages['room_111']['humidity'],
    ]
    pressure_values = [
        calculateAHPTempImportance(
            averages['room_106']['light'], averages['room_108']['light'], 66, 74, 70),

        averages['room_106']['light'] /
        averages['room_215']['light'],

        averages['room_106']['light'] /
        averages['room_111']['light'],

        averages['room_108']['light'] /
        averages['room_215']['light'],

        averages['room_108']['light'] /
        averages['room_111']['light'],

        averages['room_215']['light'] /
        averages['room_111']['light'],
    ]
    light_values = [
        calculateAHPTempImportance(
            averages['room_106']['pressure'] / 1000, averages['room_108']['pressure'] / 1000, 90, 98, 94),
        averages['room_106']['pressure'] /
        averages['room_108']['pressure'],

        averages['room_106']['pressure'] /
        averages['room_215']['pressure'],

        averages['room_106']['pressure'] /
        averages['room_111']['pressure'],

        averages['room_108']['pressure'] /
        averages['room_215']['pressure'],

        averages['room_108']['pressure'] /
        averages['room_111']['pressure'],

        averages['room_215']['pressure'] /
        averages['room_111']['pressure'],
    ]

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
    return criteria.target_weights
    # {'room_106': 0.344, 'room_108': 0.335, 'room_111': 0.178, 'room_215': 0.144}

    # After getting the value of criteria.target_weights, we just need to sort rooms by value (descending):
    # room_108, room_106, room_111, room_215 - this is the end result of the calculation


api.add_resource(ROOMS, '/rooms')
api.add_resource(AHPImportance, '/ahpImportances')
api.add_resource(ROOM, '/rooms/<room_name>/')


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8087)
