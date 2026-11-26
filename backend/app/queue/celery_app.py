from celery import Celery
from flask import Flask


def create_celery(app: Flask):

    celery = Celery(
        app.import_name,
        broker=app.config["RABBITMQ_URL"],
        backend=app.config["REDIS_URL"],
        include=["app.queue.tasks"]
    )

    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Kolkata",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        result_expires=86400
    )

    class FlaskTask(celery.Task):

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskTask

    # Import the existing task module during app construction so both the API
    # and worker share one finalized registry. Keep the explicit wire name used
    # by existing producers, and expose the module-qualified Celery name as an
    # alias to the same task instance.
    celery.loader.import_task_module("app.queue.tasks")
    celery.finalize()
    process_message_task = celery.tasks.get("senderx.process_message")
    if process_message_task is None:
        raise RuntimeError("Celery task senderx.process_message was not registered")
    celery.tasks["app.queue.tasks.process_message"] = process_message_task

    return celery


def __getattr__(name: str):
    if name in ("celery", "celery_app"):
        from app import create_app
        flask_app = create_app()
        return flask_app.celery
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
