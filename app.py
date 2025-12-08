import atexit
import os
import random
import threading
import time
import csv
import logging
from datetime import datetime

import RPi.GPIO as GPIO
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, jsonify, render_template, request
from rpi_ws281x import PixelStrip, Color

#####

DEFAULT_TREATS = 5
ENABLE_SERVO = False
ENABLE_LIGHTS = True

# LED strip configuration for Pi 3
LED_COUNT = 100  # Number of LED pixels
LED_PIN = 18  # GPIO pin connected to the pixels (18 uses PWM!)
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800kHz)
LED_DMA = 10  # DMA channel to use for generating signal
LED_BRIGHTNESS = 65  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal
LED_CHANNEL = 0  # Use channel 0

#####

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Variable to track the number of treats left
treats_left = DEFAULT_TREATS

# File to store IP addresses of users who have fed Apollo today
IP_TRACKING_FILE = "fed_ip_addresses.txt"

# Set up GPIO
GPIO.setmode(GPIO.BCM)  # Use Broadcom pin numbering
GPIO.setup(7, GPIO.OUT)  # Set GPIO pin 7 as output

# Set up PWM on the GPIO pin for the servo
servo = GPIO.PWM(7, 50)  # GPIO 7 for PWM with 50Hz frequency
servo.start(0)  # Initialize PWM with 0% duty cycle

# Initialize the LED strip
strip = PixelStrip(
    LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL
)
strip.begin()



def get_current_date():
    """Returns the current date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


def load_fan_art_metadata():
    """Loads fan art metadata from the CSV file and returns a random piece."""
    fan_art = []
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "static", "apollo-fan-art", "meta_data.csv")
    
    logger.info(f"Script directory: {script_dir}")
    logger.info(f"Looking for CSV at: {csv_path}")
    logger.info(f"File exists: {os.path.exists(csv_path)}")
    
    try:
        if os.path.exists(csv_path):
            logger.info(f"CSV file found! Reading contents...")
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Clean up the data (remove quotes and extra spaces)
                    art_piece = {
                        'filename': row['filename'].strip(),
                        'artist': row[' artist'].strip(),  # Note the leading space
                        'title': row[' title'].strip().strip('"')  # Note the leading space
                    }
                    fan_art.append(art_piece)
                    logger.info(f"Loaded art piece: {art_piece}")
            
            # Return a random piece of art instead of all pieces
            if fan_art:
                selected = random.choice(fan_art)
                logger.info(f"Selected random piece: {selected}")
                return [selected]
            else:
                logger.info("No fan art pieces found in CSV")
        else:
            logger.info(f"CSV file not found at {csv_path}")
    except Exception as e:
        logger.error(f"Error loading fan art metadata: {e}")
    
    return []


def load_ip_addresses():
    """Loads the list of IP addresses that have fed Apollo today."""
    if os.path.exists(IP_TRACKING_FILE):
        with open(IP_TRACKING_FILE, "r") as file:
            lines = file.readlines()
            date = lines[0].strip()  # The first line should be the date
            if date == get_current_date():
                return set(line.strip() for line in lines[1:])
    return set()


def save_ip_address(ip):
    """Saves a new IP address to the tracking file."""
    with open(IP_TRACKING_FILE, "a") as file:
        file.write(f"{ip}\n")


def reset_ip_tracking():
    """Resets the IP tracking file for a new day."""
    with open(IP_TRACKING_FILE, "w") as file:
        file.write(f"{get_current_date()}\n")


def set_servo_angle(angle):
    """Set the servo to a specific angle."""
    duty_cycle = 2.5 + (angle / 18.0)  # Convert angle to duty cycle
    servo.ChangeDutyCycle(duty_cycle)
    time.sleep(0.5)  # Give the servo time to reach the position
    servo.ChangeDutyCycle(0)  # Stop the PWM signal


def set_christmas_pattern():
    """Set alternating red and green pattern on all LEDs."""
    if not ENABLE_LIGHTS:
        return
    
    # NOTE: This LED strip uses GRB channel order (not RGB)
    # So Color(R, G, B) actually displays as (G, R, B)
    # Red: Color(0, 255, 0) = Green=0, Red=255, Blue=0
    # Green: Color(255, 0, 0) = Green=255, Red=0, Blue=0
    # White: Color(255, 255, 255) = Green=255, Red=255, Blue=255
    for i in range(strip.numPixels()):
        if i % 2 == 0:
            strip.setPixelColor(i, Color(0, 255, 0))  # Red
        else:
            strip.setPixelColor(i, Color(255, 0, 0))  # Green
    strip.show()


def twinkle_effect():
    """Twinkle effect with white, red, and green for Christmas."""
    if not ENABLE_LIGHTS:
        return
    
    logger.info("Starting twinkle effect")
    
    # Twinkle for about 3 seconds
    twinkle_duration = 3.0
    start_time = time.time()
    num_twinkles = 0
    
    while time.time() - start_time < twinkle_duration:
        # Randomly select some LEDs to twinkle
        num_to_twinkle = random.randint(5, 15)
        twinkled_indices = random.sample(range(strip.numPixels()), min(num_to_twinkle, strip.numPixels()))
        
        # Save current colors
        saved_colors = []
        for idx in twinkled_indices:
            saved_colors.append((idx, strip.getPixelColor(idx)))
        
        # Set twinkling colors (white, red, or green randomly)
        colors = [
            Color(255, 255, 255),  # White
            Color(0, 255, 0),      # Red
            Color(255, 0, 0)       # Green
        ]
        for idx in twinkled_indices:
            strip.setPixelColor(idx, random.choice(colors))
        strip.show()
        
        time.sleep(0.15)  # Twinkle duration
        
        # Restore original colors
        for idx, original_color in saved_colors:
            if idx % 2 == 0:
                strip.setPixelColor(idx, Color(0, 255, 0))  # Red
            else:
                strip.setPixelColor(idx, Color(255, 0, 0))  # Green
        strip.show()
        
        time.sleep(0.1)  # Pause between twinkles
        num_twinkles += 1
    
    logger.info(f"Twinkle effect complete ({num_twinkles} twinkles)")


def reset_treats():
    """Resets the treat count and IP tracking daily at 3 AM ET."""
    global treats_left
    treats_left = DEFAULT_TREATS
    reset_ip_tracking()
    print("Treats and IP tracking reset at 3 AM ET")


# Schedule the reset_treats function to run daily at 3 AM ET
scheduler = BackgroundScheduler()
scheduler.add_job(reset_treats, CronTrigger(hour=3, minute=0, timezone="US/Eastern"))
scheduler.start()


@app.route("/")
def home():
    logger.info("=== HOME ROUTE CALLED ===")
    bones = "🎃 " * treats_left  # Display the remaining treats as pumpkin emojis
    fan_art_metadata = load_fan_art_metadata()
    logger.info(f"Fan art metadata returned: {fan_art_metadata}")
    return render_template("index.html", treats=bones.strip(), fan_art=fan_art_metadata)


@app.route("/give_treat", methods=["POST"])
def give_treat():
    global treats_left

    # Get the user's IP address
    user_ip = request.remote_addr

    # Load the list of IP addresses that have fed Apollo today
    fed_ips = load_ip_addresses()

    # Ignore "127.0.0.1" (loopback address) if it's in the list
    fed_ips.discard("127.0.0.1")
    fed_ips.discard("192.168.86.1")

    # Check if this IP address has already fed Apollo today
    if user_ip in fed_ips:
        return jsonify({"error": "You have already fed Apollo today!"}), 403

    # Update the treats count and add the IP address to the tracking file
    if treats_left > 0:
        treats_left -= 1
        message = "Apollo got a treat!"
        save_ip_address(user_ip)

        # Start the treat dispensing and LED twinkle in a separate thread
        def treat_dispensing():
            # Servo dispensing logic FIRST
            if ENABLE_SERVO:
                set_servo_angle(36 + 18)  # Rotate the servo
                time.sleep(1)
                set_servo_angle(18)
                time.sleep(1)
            
            # Then twinkle effect
            twinkle_effect()
            
            # Restore Christmas pattern after twinkle
            set_christmas_pattern()

        # Run treat dispensing asynchronously
        threading.Thread(target=treat_dispensing).start()

        # Immediately respond with a success message
        bones = "🎃 " * treats_left  # Display the remaining treats as pumpkin emojis
        return jsonify({"treats_left": bones.strip(), "message": message})

    else:
        message = "No more treats left for today!"
        return jsonify({"error": message}), 403


@app.route("/thank_you")
def thank_you():
    return "Apollo has been fed! Thanks!"


def startup():
    # Set Christmas pattern on startup (alternating red and green)
    if ENABLE_LIGHTS:
        set_christmas_pattern()
    reset_ip_tracking()


def cleanup():
    # Cleanup GPIO on exit
    scheduler.shutdown()
    servo.stop()
    GPIO.cleanup()


# Reset IP tracking at the start of the application
startup()
atexit.register(cleanup)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
