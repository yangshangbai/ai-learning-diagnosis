import multiprocessing

# Bind
bind = '127.0.0.1:8001'
backlog = 2048

# Worker settings
workers = min(multiprocessing.cpu_count() * 2 + 1, 4)
worker_class = 'uvicorn.workers.UvicornWorker'

# Timeouts
timeout = 300
graceful_timeout = 30
keepalive = 5

# Logging - use stdout/stderr for systemd journal
accesslog = '-'
errorlog = '-'
loglevel = 'info'
