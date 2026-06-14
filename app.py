import atexit
import os
import random
import threading
import time
import csv
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, jsonify, render_template, request

#####

DEFAULT_TREATS = 5
ENABLE_SERVO = True
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

# Raspberry Pi-only: set APOLLO_HEADLESS=1 on a VPS if you prefer to skip probing hardware.
GPIO = None
servo = None
strip = None
Color = None


def init_hardware():
    """Attach GPIO servo + WS281x strip on a Pi; no-op safely on VPS / missing libs."""
    global GPIO, servo, strip, Color
    force_headless = os.environ.get("APOLLO_HEADLESS", "").lower() in ("1", "true", "yes")
    if force_headless:
        logger.info("APOLLO_HEADLESS: GPIO and LED strip disabled.")
        return
    try:
        import RPi.GPIO as GPIO_mod
        from rpi_ws281x import Color as NeoColor
        from rpi_ws281x import PixelStrip

        Color = NeoColor
        GPIO_mod.setmode(GPIO_mod.BCM)
        GPIO_mod.setup(7, GPIO_mod.OUT)
        srv = GPIO_mod.PWM(7, 50)
        srv.start(0)
        st = PixelStrip(
            LED_COUNT,
            LED_PIN,
            LED_FREQ_HZ,
            LED_DMA,
            LED_INVERT,
            LED_BRIGHTNESS,
            LED_CHANNEL,
        )
        st.begin()
        GPIO = GPIO_mod
        servo = srv
        strip = st
        logger.info("GPIO and LED strip initialized.")
    except Exception as e:
        logger.warning("Raspberry Pi hardware not available (%s); running without GPIO/LEDs.", e)
        GPIO = None
        servo = None
        strip = None
        Color = None


init_hardware()


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
            if not lines:
                return set()
            date = lines[0].strip()
            if date == get_current_date():
                return set(line.strip() for line in lines[1:] if line.strip())
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
    if servo is None:
        return
    duty_cycle = 2.5 + (angle / 18.0)  # Convert angle to duty cycle
    servo.ChangeDutyCycle(duty_cycle)
    time.sleep(0.5)  # Give the servo time to reach the position
    servo.ChangeDutyCycle(0)  # Stop the PWM signal


def turn_leds_off():
    """Turn all LEDs off."""
    if not ENABLE_LIGHTS or strip is None or Color is None:
        return
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))  # Off
    strip.show()


def flicker_birthday():
    """Party twinkle: multicolor for birthday (strip is GRB order)."""
    if not ENABLE_LIGHTS or strip is None or Color is None:
        return
    
    logger.info("Starting birthday twinkle effect")
    
    # NOTE: This LED strip uses GRB channel order (not RGB)
    # Color(R, G, B) displays as (G, R, B) on the strip
    party_colors = [
        Color(0, 255, 0),       # red
        Color(255, 0, 0),       # green
        Color(0, 0, 255),       # blue
        Color(255, 255, 255),   # white
        Color(255, 255, 0),     # yellow
        Color(255, 0, 255),     # cyan
        Color(0, 255, 255),     # magenta / purple-ish
    ]
    
    twinkle_duration = 5.0
    start_time = time.time()
    
    while time.time() - start_time < twinkle_duration:
        num_to_twinkle = random.randint(8, 25)
        twinkled = random.sample(range(strip.numPixels()), min(num_to_twinkle, strip.numPixels()))
        
        for i in range(strip.numPixels()):
            if i in twinkled:
                strip.setPixelColor(i, random.choice(party_colors))
            else:
                strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        
        time.sleep(0.12)
    
    logger.info("Birthday twinkle effect complete")
    
    turn_leds_off()


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
    treat_icons = "🌸 " * treats_left
    fan_art_metadata = load_fan_art_metadata()
    logger.info(f"Fan art metadata returned: {fan_art_metadata}")
    return render_template("index.html", treats=treat_icons.strip(), fan_art=fan_art_metadata)


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
                set_servo_angle(23)  # Backtrack 5° further so the treat actually drops
                time.sleep(1)
            
            # Then birthday party twinkle (turns off automatically after)
            flicker_birthday()

        # Run treat dispensing asynchronously
        threading.Thread(target=treat_dispensing).start()

        # Immediately respond with a success message
        treat_icons = "🌸 " * treats_left
        return jsonify({"treats_left": treat_icons.strip(), "message": message})

    else:
        message = "No more treats left for today!"
        return jsonify({"error": message}), 403


@app.route("/thank_you")
def thank_you():
    return "Apollo has been fed! Thanks!"


def startup():
    # Turn all LEDs off on startup
    if ENABLE_LIGHTS:
        turn_leds_off()
    reset_ip_tracking()


def cleanup():
    scheduler.shutdown()
    if servo is not None:
        try:
            servo.stop()
        except Exception:
            logger.debug("servo.stop() skipped", exc_info=True)
    if GPIO is not None:
        try:
            GPIO.cleanup()
        except Exception:
            logger.debug("GPIO.cleanup() skipped", exc_info=True)


# Reset IP tracking at the start of the application
startup()
atexit.register(cleanup)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
