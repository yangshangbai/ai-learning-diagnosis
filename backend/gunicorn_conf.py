import multiprocessing
import os

# Bind
bind = '127.0.0.1:8001'
backlog = 2048

# Worker settings
workers = min(multiprocessing.cpu_count() * 2 + 1, 9)
worker_class = 'uvicorn.workers.UvicornWorker'

# Timeouts
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logging - use stdout/stderr for systemd journal
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Process naming
proc_name = 'ai_learning_backend'

# Preload app for shared memory
preload_app = True
