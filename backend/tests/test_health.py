"""
SenderX Health Endpoints Test Suite
Validates:
- GET /api/v1/health/
- GET /api/v1/health/mongodb
- GET /api/v1/health/redis
- GET /api/v1/health/rabbitmq
- GET /api/v1/health/celery
- GET /api/v1/health/database
- GET /api/v1/health/detailed
"""

from unittest.mock import MagicMock, patch
import pytest

from app import create_app


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_basic_health_check(client):
    """Verify basic application health check returns 200 and operational status."""
    res = client.get("/api/v1/health/")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["application"] == "SenderX"
    assert data["data"]["status"] == "running"
    assert "timestamp" in data["data"]


def test_mongodb_health_check_connected(client):
    """Verify MongoDB health returns 200 when connection is active."""
    res = client.get("/api/v1/health/mongodb")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["mongodb"] == "connected"


def test_mongodb_health_check_disconnected(app, client):
    """Verify MongoDB health returns 503 when ping fails."""
    with patch("pymongo.synchronous.database.Database.command", side_effect=Exception("Connection refused")):
        res = client.get("/api/v1/health/mongodb")
        assert res.status_code == 503
        data = res.get_json()
        assert data["success"] is False
        assert data["data"]["mongodb"] == "disconnected"


def test_redis_health_check_mocked(app, client):
    """Verify Redis health returns 200 when ping succeeds and 503 on failure."""
    # Success
    with patch.object(app.redis_client, "ping", return_value=True):
        res = client.get("/api/v1/health/redis")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["redis"] == "connected"

    # Failure
    with patch.object(app.redis_client, "ping", side_effect=Exception("Redis down")):
        res = client.get("/api/v1/health/redis")
        assert res.status_code == 503
        data = res.get_json()
        assert data["success"] is False
        assert data["data"]["redis"] == "disconnected"


def test_rabbitmq_health_check_mocked(client):
    """Verify RabbitMQ health check returns appropriate status and handles connection failure."""
    with patch("kombu.Connection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn.connected = True
        mock_conn_cls.return_value.__enter__.return_value = mock_conn

        res = client.get("/api/v1/health/rabbitmq")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["rabbitmq"] == "connected"


def test_celery_health_check_mocked(app, client):
    """Verify Celery health check reports worker count and responds 200 when workers active, 503 when none."""
    # Workers active
    with patch.object(app.celery.control, "ping", return_value=[{"worker1": {"ok": "pong"}}]):
        res = client.get("/api/v1/health/celery")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["celery_workers"] == 1

    # No workers
    with patch.object(app.celery.control, "ping", return_value=[]):
        res = client.get("/api/v1/health/celery")
        assert res.status_code == 503
        data = res.get_json()
        assert data["data"]["celery_workers"] == 0


def test_database_health_aggregate(app, client):
    """Verify /database endpoint checks both MongoDB and Redis."""
    with patch.object(app.mongo_client.admin, "command", return_value={"ok": 1}):
        with patch.object(app.redis_client, "ping", return_value=True):
            res = client.get("/api/v1/health/database")
            assert res.status_code == 200
            data = res.get_json()
            assert data["success"] is True
            assert data["data"]["mongodb"] == "connected"
            assert data["data"]["redis"] == "connected"


def test_detailed_health_check(app, client):
    """Verify /detailed returns a complete dictionary with all components."""
    with patch.object(app.redis_client, "ping", return_value=True):
        with patch("kombu.Connection") as mock_conn_cls:
            # Don't let Celery's broadcast initialize its producer pool while
            # kombu.Connection is mocked; the pool limit is process-global.
            with patch.object(app.celery.control, "ping", return_value=[]):
                mock_conn = MagicMock()
                mock_conn.connected = True
                mock_conn_cls.return_value.__enter__.return_value = mock_conn

                res = client.get("/api/v1/health/detailed")
                data = res.get_json()
                assert "flask" in data["data"]
                assert "mongodb" in data["data"]
                assert "redis" in data["data"]
                assert "rabbitmq" in data["data"]
                assert "celery_workers" in data["data"]
                assert "timestamp" in data
