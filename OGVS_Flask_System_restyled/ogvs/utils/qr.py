import base64
import io

import qrcode


def qr_data_uri(value):
    qr = qrcode.QRCode(
        box_size=8,
        border=4,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
    )
    qr.add_data(value)
    qr.make(fit=True)
    image_data = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(image_data, format="PNG")
    encoded = base64.b64encode(image_data.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"