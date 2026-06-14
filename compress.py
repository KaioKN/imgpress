import io
from PIL import Image

JPEG_QUALITY_MAX = 80
JPEG_QUALITY_MIN = 50
WEBP_QUALITY_MAX = 82
WEBP_QUALITY_MIN = 45
MIN_SAVINGS_BYTES = 1024


def _encode_jpeg(img: Image.Image, quality: int) -> bytes:
    with io.BytesIO() as buf:
        img.save(buf, format="JPEG", optimize=True, quality=quality, progressive=True, subsampling=2)
        return buf.getvalue()


def _encode_webp(img: Image.Image, quality: int) -> bytes:
    with io.BytesIO() as buf:
        img.save(buf, format="WEBP", quality=quality, method=6)
        return buf.getvalue()


def _encode_webp_lossless(img: Image.Image) -> bytes:
    with io.BytesIO() as buf:
        img.save(buf, format="WEBP", lossless=True, method=6)
        return buf.getvalue()


def _encode_png(img: Image.Image) -> bytes:
    with io.BytesIO() as buf:
        img.save(buf, format="PNG", optimize=True, compress_level=9)
        return buf.getvalue()


def _strip_alpha_if_opaque(img: Image.Image) -> Image.Image:
    if img.mode == "RGBA":
        alpha_min = img.getextrema()[3][0]
        if alpha_min == 255:
            return img.convert("RGB")
    return img


def _try_quantize_png(img: Image.Image) -> bytes | None:
    """Reduce to 256-color palette. Only for RGB (not RGBA — risks transparency breakage)."""
    if img.mode != "RGB":
        return None
    try:
        return _encode_png(img.quantize(colors=256))
    except Exception:
        return None


def _binary_search_quality(img, encode_fn, q_min, q_max, original_size):
    """Find highest quality whose output is still smaller than original_size."""
    best_data = None
    lo, hi = q_min, q_max

    while lo <= hi:
        mid = (lo + hi) // 2
        data = encode_fn(img, mid)
        if len(data) < original_size:
            best_data = data
            lo = mid + 1
        else:
            hi = mid - 1

    if best_data is None:
        best_data = encode_fn(img, q_min)
    return best_data


def _pick_best(candidates: list[tuple[bytes, str]], original_size: int) -> tuple[bytes, str] | None:
    valid = [(d, f) for d, f in candidates if len(d) < original_size]
    return min(valid, key=lambda x: len(x[0])) if valid else None


def compress(data: bytes) -> tuple[bytes, str, float]:
    """
    Compress image bytes. Returns (compressed_bytes, format_name, saved_pct).
    Tries multiple formats/strategies and returns the smallest result.
    If compression doesn't help, returns original data with 0.0 savings.
    """
    original_size = len(data)
    with Image.open(io.BytesIO(data)) as img:
        fmt = (img.format or "").upper()
        mode = img.mode

        if fmt == "JPEG":
            img2 = img.convert("RGB") if mode in ("RGBA", "P") else img.copy()
            img2.info = {}
            jpeg_data = _binary_search_quality(img2, _encode_jpeg, JPEG_QUALITY_MIN, JPEG_QUALITY_MAX, original_size)
            webp_data = _binary_search_quality(img2, _encode_webp, WEBP_QUALITY_MIN, WEBP_QUALITY_MAX, original_size)
            result = _pick_best([(jpeg_data, "JPEG"), (webp_data, "WEBP")], original_size)

        elif fmt == "WEBP":
            img2 = img.convert("RGBA") if mode in ("RGBA", "P") else img.copy()
            img2.info = {}
            webp_data = _binary_search_quality(img2, _encode_webp, WEBP_QUALITY_MIN, WEBP_QUALITY_MAX, original_size)
            result = _pick_best([(webp_data, "WEBP")], original_size)

        elif fmt == "PNG":
            img2 = img.copy()
            transparency = img.info.get("transparency")
            img2.info = {}
            if transparency is not None:
                img2.info["transparency"] = transparency
            if transparency is None:
                img2 = _strip_alpha_if_opaque(img2)

            candidates: list[tuple[bytes, str]] = []
            candidates.append((_encode_png(img2), "PNG"))
            candidates.append((_encode_webp_lossless(img2), "WEBP"))

            quantized = _try_quantize_png(img2)
            if quantized is not None:
                candidates.append((quantized, "PNG"))

            result = _pick_best(candidates, original_size)

        else:
            return data, fmt or "unknown", 0.0

    if result is None:
        return data, fmt, 0.0

    compressed, out_fmt = result
    saved = original_size - len(compressed)
    if saved < MIN_SAVINGS_BYTES:
        return data, fmt, 0.0

    saved_pct = saved / original_size * 100
    return compressed, out_fmt, saved_pct
