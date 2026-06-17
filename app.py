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

# "normal" = treat dispenser; "standby" = hardware down, kisses only
APP_MODE = os.environ.get("APOLLO_MODE", "standby")
KISSES_COUNT_FILE = "kisses_count.txt"
KISS_COOLDOWN_SECONDS = 4

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
kisses_sent = 0
last_kiss_at = 0.0
_kiss_light_lock = threading.Lock()

# File to store IP addresses of users who have fed Apollo today
IP_TRACKING_FILE = "fed_ip_addresses.txt"

# Raspberry Pi-only: set APOLLO_HEADLESS=1 on a VPS if you prefer to skip probing hardware.
GPIO = None
servo = None
strip = None
Color = None


def is_standby_mode():
    return APP_MODE.lower() == "standby"


def servo_enabled():
    return ENABLE_SERVO and not is_standby_mode()


def init_hardware():
    """Attach WS281x strip on a Pi; servo only when not in standby. No-op on VPS / missing libs."""
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
        if is_standby_mode():
            logger.info("Standby mode: servo disabled, LED strip enabled.")
            srv = None
        else:
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
        logger.info("LED strip initialized%s.", "" if srv else " (servo skipped)")
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


def load_kisses_count():
    """Load total kisses sent (persists across restarts during standby)."""
    if os.path.exists(KISSES_COUNT_FILE):
        try:
            with open(KISSES_COUNT_FILE, "r") as file:
                return int(file.read().strip() or 0)
        except (ValueError, OSError):
            logger.warning("Could not read kisses count file; starting at 0.")
    return 0


def save_kisses_count(count):
    """Persist total kisses sent."""
    with open(KISSES_COUNT_FILE, "w") as file:
        file.write(str(count))


def set_servo_angle(angle):
    """Set the servo to a specific angle."""
    if not servo_enabled() or servo is None:
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


def flicker_kiss():
    """Soft pink twinkle when Apollo gets a kiss (strip is GRB order)."""
    if not ENABLE_LIGHTS or strip is None or Color is None:
        return
    if not _kiss_light_lock.acquire(blocking=False):
        return

    try:
        logger.info("Starting kiss twinkle effect")

        kiss_colors = [
            Color(180, 80, 255),    # pink
            Color(220, 120, 255),   # light pink
            Color(255, 150, 255),   # rose
            Color(255, 200, 255),   # pale blush
            Color(255, 100, 255),   # hot pink
        ]

        twinkle_duration = 3.0
        start_time = time.time()

        while time.time() - start_time < twinkle_duration:
            num_to_twinkle = random.randint(10, 30)
            twinkled = random.sample(range(strip.numPixels()), min(num_to_twinkle, strip.numPixels()))

            for i in range(strip.numPixels()):
                if i in twinkled:
                    strip.setPixelColor(i, random.choice(kiss_colors))
                else:
                    strip.setPixelColor(i, Color(0, 0, 0))
            strip.show()

            time.sleep(0.1)

        logger.info("Kiss twinkle effect complete")
        turn_leds_off()
    finally:
        _kiss_light_lock.release()


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
    return render_template(
        "index.html",
        mode=APP_MODE,
        treats=treat_icons.strip(),
        kisses_sent=kisses_sent,
        fan_art=fan_art_metadata,
    )


@app.route("/give_kiss", methods=["POST"])
def give_kiss():
    global kisses_sent, last_kiss_at
    if not is_standby_mode():
        return jsonify({"error": "Kisses are only available in standby mode."}), 403

    now = time.time()
    elapsed = now - last_kiss_at
    if elapsed < KISS_COOLDOWN_SECONDS:
        retry_after = int(KISS_COOLDOWN_SECONDS - elapsed + 0.99)
        return jsonify(
            {
                "error": f"Give Apollo a moment! Try again in {retry_after}s 💋",
                "retry_after": retry_after,
            }
        ), 429

    last_kiss_at = now
    kisses_sent += 1
    save_kisses_count(kisses_sent)
    threading.Thread(target=flicker_kiss).start()
    return jsonify(
        {
            "kisses_sent": kisses_sent,
            "message": "Apollo got a kiss! 💋",
            "cooldown_seconds": KISS_COOLDOWN_SECONDS,
        }
    )


@app.route("/give_treat", methods=["POST"])
def give_treat():
    global treats_left

    if is_standby_mode():
        return jsonify(
            {"error": "Hardware is down for upgrades — send Apollo a kiss instead! 💋"}
        ), 403

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
            if servo_enabled():
                set_servo_angle(55)  # Rotate forward to dispense
                time.sleep(1)
                set_servo_angle(0)  # Return to rest
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
    global kisses_sent
    # Turn all LEDs off on startup
    if ENABLE_LIGHTS:
        turn_leds_off()
    reset_ip_tracking()
    kisses_sent = load_kisses_count()
    if is_standby_mode():
        logger.info("Standby mode active — servo off, lights on, kisses enabled.")


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
