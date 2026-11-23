"""
Gunicorn Production Configuration
Basista Oil Traders - Petrol Station Management System
"""

import multiprocessing
import os

# Server Socket
bind = os.getenv('GUNICORN_BIND', 'unix:/run/gunicorn/basista_oil.sock')
backlog = 2048
umask = 0o007

# Worker Processes & Concurrency
# Formula: 2 x CPU cores + 1
workers = int(os.getenv('GUNICORN_WORKERS', (multiprocessing.cpu_count() * 2) + 1))
worker_class = 'gthread'
threads = int(os.getenv('GUNICORN_THREADS', 2))
worker_connections = 1000
timeout = 90  # 90 seconds (allows WeasyPrint PDF and bulk report exports without premature timeout)
keepalive = 5

# Memory Leak Prevention
# Gracefully recycle workers after processing N requests
max_requests = 1000
max_requests_jitter = 100

# Security and Process Management
user = os.getenv('GUNICORN_USER', 'www-data')
group = os.getenv('GUNICORN_GROUP', 'www-data')
proc_name = 'basista_oil_gunicorn'
pidfile = '/run/gunicorn/basista_oil.pid'

# Logging
accesslog = os.getenv('GUNICORN_ACCESS_LOG', '/var/log/gunicorn/access.log')
errorlog = os.getenv('GUNICORN_ERROR_LOG', '/var/log/gunicorn/error.log')
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s µs'
capture_output = True

# Server Mechanics
preload_app = False
daemon = False

def on_starting(server):
    """Callback when Gunicorn starts."""
    server.log.info("Starting Basista Oil Traders Petrol Station Gunicorn master process.")

def on_reload(server):
    """Callback on reload."""
    server.log.info("Reloading Basista Oil Traders Gunicorn workers.")

def worker_int(worker):
    """Callback on worker SIGINT/SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal.")
