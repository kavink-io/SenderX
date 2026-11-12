
from flask_restx import Api
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from pymongo import MongoClient
import redis


api = Api(
    title="SenderX API",
    version="1.0",
    description="Multi-Channel Communication Platform"
)

cors = CORS()
jwt = JWTManager()

mongo_client = None
mongo_db = None

redis_client = None
