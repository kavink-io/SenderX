"""
SenderX Celery Worker Entrypoint
Usage:
    celery -A celery_worker.celery worker --loglevel=info -P solo
"""
from run import celery

if __name__ == "__main__":
    celery.start()
