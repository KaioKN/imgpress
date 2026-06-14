import io
import os
import uuid

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

import store
from compress import compress

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

SUPPORTED_MIMES = {'image/jpeg', 'image/png', 'image/webp'}

# Background sweep of expired entries so disk usage stays bounded.
store.start_cleanup_thread()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/compress', methods=['POST'])
def compress_image():
    file = request.files.get('image')
    if not file:
        return jsonify({'error': 'No file uploaded'}), 400

    # mimetype comes from the client header and is easy to spoof; it's only a
    # cheap pre-filter. The real validation is compress()/Pillow opening the
    # bytes below, which rejects anything that isn't a decodable image.
    mime = file.mimetype
    if mime not in SUPPORTED_MIMES:
        return jsonify({'error': 'Unsupported format. Use JPEG, PNG, or WebP.'}), 400

    data = file.read()
    original_size = len(data)

    try:
        compressed, fmt, saved_pct = compress(data)
    except Exception:
        return jsonify({'error': 'Failed to process image. Make sure it is a valid file.'}), 500

    ext = fmt.lower()
    if ext == 'jpeg':
        ext = 'jpg'

    base = secure_filename(os.path.splitext(file.filename or 'image')[0]) or 'image'
    out_name = f"{base}_compressed.{ext}"

    file_id = str(uuid.uuid4())
    store.put(file_id, compressed, out_name, f'image/{ext}')

    return jsonify({
        'id': file_id,
        'original_name': file.filename,
        'compressed_name': out_name,
        'original_size': original_size,
        'compressed_size': len(compressed),
        'saved_pct': round(saved_pct, 1),
        'format': fmt,
        'already_optimal': saved_pct <= 0.0,
    })


@app.route('/download/<file_id>')
def download(file_id):
    entry = store.get(file_id)
    if not entry:
        return 'Not found', 404
    data, filename, mime = entry
    return send_file(
        io.BytesIO(data),
        mimetype=mime,
        as_attachment=True,
        download_name=filename,
    )


@app.errorhandler(413)
def too_large(_):
    # Keep the response JSON so the frontend's res.json() handling works
    # instead of choking on Flask's default HTML error page.
    return jsonify({'error': 'File too large. Max 20 MB.'}), 413


if __name__ == '__main__':
    # Local dev only. In production the app is served by gunicorn
    # (gunicorn app:app), which never executes this block, so the debugger
    # is never exposed. Debug stays off unless explicitly opted in.
    debug = os.environ.get('FLASK_DEBUG') == '1'
    app.run(debug=debug, port=8080)
