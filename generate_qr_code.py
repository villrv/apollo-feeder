import qrcode
from PIL import Image
from dotenv import load_dotenv
import os

# Load environment variables from the .env file
load_dotenv()

# Determine whether to use the local IP or public IP
use_local_ip = os.getenv('USE_LOCAL_IP', 'True') == 'True'
use_local_ip = False #hard coding b/c lazy

# Select the appropriate IP address
if use_local_ip:
    ip_address = os.getenv('LOCAL_IP')
else:
    ip_address = os.getenv('PUBLIC_IP')

def generate_qr_code():
    """Generate a QR code with the IP address and overlay a poodle image."""
    # Create the URL with the IP address
    url = f"http://{ip_address}:8080/"

    # Generate the QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=15,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img_qr = qr.make_image(fill='black', back_color='white').convert('RGB')

    # Open the poodle image and resize it
    poodle = Image.open("poodle.png")
    poodle = poodle.resize((50, 50))

    pos = ((img_qr.size[0] - poodle.size[0]) // 2, (img_qr.size[1] - poodle.size[1]) // 2)
    img_qr.paste(poodle, pos, mask=poodle)

    # Save the final QR code image
    filename = "qr_code.png"
    img_qr.save(filename)
    
    print(f"QR code generated and saved as {filename} with URL: {url}")

if __name__ == "__main__":
    generate_qr_code()
