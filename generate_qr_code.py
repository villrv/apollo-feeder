import qrcode
from PIL import Image

# The URL you want to encode in the QR code
url = "http://127.0.0.1:5000/"

# Generate the QR code
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction to support image overlay
    box_size=10,
    border=4,
)
qr.add_data(url)
qr.make(fit=True)

# Create an image from the QR code
img_qr = qr.make_image(fill='black', back_color='white').convert('RGB')

# Open the poodle image and resize it
poodle = Image.open("poodle.png")  # Make sure this is the path to your poodle image
poodle = poodle.resize((50, 50))  # Adjust the size as needed

# Calculate the position to paste the poodle image
pos = ((img_qr.size[0] - poodle.size[0]) // 2, (img_qr.size[1] - poodle.size[1]) // 2)

# Paste the poodle image onto the QR code
img_qr.paste(poodle, pos)

# Save the final QR code image
img_qr.save("dog_feeder_qr_with_poodle.png")

print("QR code with poodle image generated and saved as 'dog_feeder_qr_with_poodle.png'")
