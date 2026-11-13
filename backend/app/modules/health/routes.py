
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


@health_bp.route("/rabbitmq", methods=["GET"])
def rabbitmq_health():

    try:
        import kombu

        broker_url = current_app.config.get("RABBITMQ_URL")
        with kombu.Connection(broker_url, connect_timeout=3) as conn:
            conn.connect()
            connected = conn.connected

        if connected:
            return jsonify({
                "success": True,
                "message": "RabbitMQ is connected",
                "data": {
                    "rabbitmq": "connected"
                }
            }), 200

        raise ConnectionError("RabbitMQ not connected")

    except Exception as error:
        current_app.logger.error(
            "RabbitMQ health check failed (%s)", type(error).__name__
        )

        return jsonify({
            "success": False,
            "message": "RabbitMQ connection failed",
            "data": {
                "rabbitmq": "disconnected"
            }
        }), 503


@health_bp.route("/celery", methods=["GET"])
def celery_health():

    try:
        inspect = current_app.celery.control.ping(timeout=1.0)
        workers_online = len(inspect) if inspect else 0

        return jsonify({
            "success": True,
            "message": (
                f"{workers_online} Celery worker(s) online"
                if workers_online > 0
                else "No active Celery workers detected"
            ),
            "data": {
                "celery_workers": workers_online,
                "workers": inspect or []
            }
        }), 200 if workers_online > 0 else 503

    except Exception as error:
        current_app.logger.error(
            "Celery health check failed (%s)", type(error).__name__
        )

        return jsonify({
            "success": False,
            "message": "Celery worker ping failed",
            "data": {
                "celery_workers": 0
            }
        }), 503


@health_bp.route("/detailed", methods=["GET"])
def detailed_health():

    results = {}

    # Flask
    results["flask"] = "operational"

    # MongoDB
    try:
        current_app.mongo_client.admin.command("ping")
        results["mongodb"] = "connected"
    except Exception:
        results["mongodb"] = "disconnected"

    # Redis
    try:
        current_app.redis_client.ping()
        results["redis"] = "connected"
    except Exception:
        results["redis"] = "disconnected"

    # RabbitMQ
    try:
        import kombu
        with kombu.Connection(current_app.config.get("RABBITMQ_URL"), connect_timeout=3) as conn:
            conn.connect()
            results["rabbitmq"] = "connected" if conn.connected else "disconnected"
    except Exception:
        results["rabbitmq"] = "disconnected"

    # Celery
    try:
        inspect = current_app.celery.control.ping(timeout=1.0)
        results["celery_workers"] = len(inspect) if inspect else 0
    except Exception:
        results["celery_workers"] = 0

    all_connected = (
        results["mongodb"] == "connected"
        and results["redis"] == "connected"
        and results["rabbitmq"] == "connected"
    )

    return jsonify({
        "success": all_connected,
        "message": (
            "All core dependencies operational"
            if all_connected
            else "One or more core dependencies unavailable"
        ),
        "data": results,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200 if all_connected else 503
