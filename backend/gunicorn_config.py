"""
SenderX Gunicorn Production Configuration
"""

import multiprocessing
import os

bind = os.getenv("BIND_ADDRESS", "0.0.0.0:5000")
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
threads = int(os.getenv("GUNICORN_THREADS", 2))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

# Graceful restart / reload
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 50
