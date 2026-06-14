"""Gunicorn production config. Used automatically by `gunicorn app:app`
(gunicorn reads gunicorn.conf.py from the working directory), or explicitly
via `gunicorn -c gunicorn.conf.py app:app`.

Env overrides: WEB_BIND, WEB_WORKERS, WEB_TIMEOUT.
"""
import multiprocessing
import os

# On PaaS (Render/Railway/Heroku) the platform injects $PORT and routes
# external HTTPS to it, so bind to all interfaces on that port. Otherwise
# bind to localhost (the VPS+Nginx setup, where Nginx proxies in).
_port = os.environ.get("PORT")
if _port:
    bind = f"0.0.0.0:{_port}"
else:
    bind = os.environ.get("WEB_BIND", "127.0.0.1:8080")

# The disk-backed store (store.py) is shared across workers on the same host,
# so multiple workers are safe. Default to a CPU-aware count; override for
# small RAM boxes since Pillow decodes each image fully into memory.
workers = int(os.environ.get("WEB_WORKERS", min(multiprocessing.cpu_count() * 2 + 1, 4)))

# Compressing large images (esp. WebP method=6) can take a few seconds.
timeout = int(os.environ.get("WEB_TIMEOUT", "60"))

# Recycle workers periodically to bound any slow memory growth from Pillow.
max_requests = 200
max_requests_jitter = 50

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("WEB_LOGLEVEL", "info")
