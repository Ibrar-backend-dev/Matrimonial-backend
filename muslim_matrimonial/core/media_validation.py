import io

from PIL import Image

# Guards against a decompression bomb (a tiny file that decodes to an
# enormous pixel grid) -- Pillow raises Image.DecompressionBombError once the
# decoded size would exceed this.
MAX_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class MediaValidationError(Exception):
    pass


def validate_and_normalize(data, max_bytes):
    """Verify `data` is a genuine, safe image and return (webp_bytes, width, height).

    Never trust a client-declared content-type: this decodes the actual
    bytes. Re-encoding via Pillow's save() (without passing an `exif` kwarg)
    strips EXIF/GPS and any other embedded metadata, since Pillow does not
    carry it forward unless explicitly asked to.
    """
    if len(data) > max_bytes:
        raise MediaValidationError("File exceeds the maximum allowed size.")

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        # verify() leaves the file object unusable for load() -- reopen.
        image = Image.open(io.BytesIO(data))
        image.load()
    except Image.DecompressionBombError as exc:
        raise MediaValidationError("Image dimensions are too large for its file size.") from exc
    except Exception as exc:
        raise MediaValidationError("The uploaded file is not a valid image.") from exc

    if image.format not in ALLOWED_FORMATS:
        raise MediaValidationError("Supported image types are JPEG, PNG, and WEBP.")

    width, height = image.size
    output = io.BytesIO()
    image.convert("RGB").save(output, format="WEBP", quality=85)
    return output.getvalue(), width, height
