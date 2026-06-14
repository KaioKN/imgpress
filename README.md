# IMGPRESS

Lossless-first image compressor (JPEG / PNG / WebP). Flask app, no database.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py            # dev server on http://127.0.0.1:8080
```

Set `FLASK_DEBUG=1` to enable the debugger locally. **Never** set it in production.

## Production

Served by gunicorn (config in `gunicorn.conf.py`):

```bash
pip install -r requirements.txt
gunicorn -c gunicorn.conf.py app:app
```

Tunables via env: `WEB_BIND` (default `127.0.0.1:8080`), `WEB_WORKERS`,
`WEB_TIMEOUT` (default `60`s).

### Behind Nginx

The app binds to localhost; put Nginx in front for TLS and proxying. Keep
`client_max_body_size` slightly above the app's 20 MB upload limit:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    client_max_body_size 25M;
}
```

### Notes

- **Memory:** Pillow decodes each image fully into RAM. Use **≥ 2 GB** and cap
  `WEB_WORKERS` on small boxes to avoid OOM under concurrent large uploads.
- **Storage:** compressed results are written to a temp dir (`store.py`), shared
  across workers, and auto-deleted after 30 minutes. No DB required.

## Endpoints

- `GET /` — UI
- `POST /compress` — multipart field `image`; returns JSON with a download `id`
- `GET /download/<id>` — fetch the compressed file
