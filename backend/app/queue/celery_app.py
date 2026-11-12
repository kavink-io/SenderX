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

    return celery