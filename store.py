"""Disk-backed temporary store for compressed images with TTL auto-cleanup.

Files are written to a shared temp directory so the store survives a process
restart and is shared across gunicorn workers on the same host. A background
thread deletes entries older than TTL_SECONDS, so memory/disk usage stays
bounded instead of growing forever (the old in-memory dict never freed).
"""
import json
import pathlib
import tempfile
import threading
import time

TTL_SECONDS = 30 * 60          # entries live for 30 minutes
CLEANUP_INTERVAL = 5 * 60      # sweep every 5 minutes

STORE_DIR = pathlib.Path(tempfile.gettempdir()) / "imgpress_store"
STORE_DIR.mkdir(parents=True, exist_ok=True)


def _data_path(file_id: str) -> pathlib.Path:
    return STORE_DIR / f"{file_id}.bin"


def _meta_path(file_id: str) -> pathlib.Path:
    return STORE_DIR / f"{file_id}.json"


def put(file_id: str, data: bytes, download_name: str, mime: str) -> None:
    _data_path(file_id).write_bytes(data)
    _meta_path(file_id).write_text(
        json.dumps({"download_name": download_name, "mime": mime}),
        encoding="utf-8",
    )


def get(file_id: str) -> tuple[bytes, str, str] | None:
    """Return (data, download_name, mime) or None if missing/expired."""
    data_path = _data_path(file_id)
    meta_path = _meta_path(file_id)
    if not data_path.exists() or not meta_path.exists():
        return None
    if time.time() - data_path.stat().st_mtime > TTL_SECONDS:
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return data_path.read_bytes(), meta["download_name"], meta["mime"]
    except (OSError, ValueError, KeyError):
        return None


def _purge_expired() -> None:
    now = time.time()
    for path in STORE_DIR.glob("*"):
        try:
            if now - path.stat().st_mtime > TTL_SECONDS:
                path.unlink(missing_ok=True)
        except OSError:
            pass


def start_cleanup_thread() -> None:
    def loop() -> None:
        while True:
            _purge_expired()
            time.sleep(CLEANUP_INTERVAL)

    threading.Thread(target=loop, daemon=True, name="imgpress-cleanup").start()
