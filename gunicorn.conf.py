"""Small Free-plan pool: finite sync-worker deadline, one heavy operation."""
import os

bind = '0.0.0.0:' + os.environ.get('PORT', '10000')
workers = 2
worker_class = 'sync'
threads = 1
# Keep above the unchanged browser deadline; sync workers are killed/replaced
# if a provider/DNS operation exceeds this window. Never set timeout=0.
timeout = 150
graceful_timeout = 150
backlog = 32
max_requests = 200
max_requests_jitter = 20
accesslog = None  # Never log location queries or request bodies.
errorlog = '-'
loglevel = 'info'
capture_output = False

# No admin control socket or writable home directory is needed in the image.
control_socket_disable = True
