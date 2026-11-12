
from flask import Blueprint, current_app, jsonify
from datetime import datetime, timezone


health_bp = Blueprint("health", __name__)



@health_bp.route("/", methods=["GET"])
def health_check():

    return jsonify({
        "success": True,
        "message": "SenderX API is operational",
        "data": {
            "application": "SenderX",
            "status": "running",
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat()
        }
    }), 200




@health_bp.route("/database", methods=["GET"])
def database_health():

    results = {}

    try:
        current_app.mongo_client.admin.command("ping")

        results["mongodb"] = "connected"

    except Exception as error:

        results["mongodb"] = "disconnected"

        current_app.logger.error(
            "MongoDB connection failed (%s)", type(error).__name__
        )

    try:
        current_app.redis_client.ping()

        results["redis"] = "connected"

    except Exception as error:

        results["redis"] = "disconnected"

        current_app.logger.error(
            "Redis connection failed (%s)", type(error).__name__
        )

   
    all_connected = all(
        status == "connected"
        for status in results.values()
    )

   
    response = {
        "success": all_connected,
        "message": (
            "All services operational"
            if all_connected
            else "One or more services unavailable"
        ),
        "data": results
    }

    return jsonify(response), (
        200 if all_connected else 503
    )



@health_bp.route("/mongodb", methods=["GET"])
def mongodb_health():

    try:

        current_app.mongo_client.admin.command("ping")

        return jsonify({
            "success": True,
            "message": "MongoDB is connected",
            "data": {
                "mongodb": "connected"
            }
        }), 200

    except Exception as error:

        current_app.logger.error(
            "MongoDB health check failed (%s)", type(error).__name__
        )

        return jsonify({
            "success": False,
            "message": "MongoDB connection failed",
            "data": {
                "mongodb": "disconnected"
            }
        }), 503



@health_bp.route("/redis", methods=["GET"])
def redis_health():

    try:

        current_app.redis_client.ping()

        return jsonify({
            "success": True,
            "message": "Redis is connected",
            "data": {
                "redis": "connected"
            }
        }), 200

    except Exception as error:

        current_app.logger.error(
            "Redis health check failed (%s)", type(error).__name__
        )

        return jsonify({
            "success": False,
            "message": "Redis connection failed",
            "data": {
                "redis": "disconnected"
            }
        }), 503
