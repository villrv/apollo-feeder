from flask import Flask, render_template, jsonify, request
import os
from datetime import datetime
import RPi.GPIO as GPIO
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from rpi_ws281x import PixelStrip, Color  # For LEDs
import threading
from strandtest import *

# PICK ONE RANDOMLY FROM THESE in strandtest:
rowChangeAndSparkle, explosion, fireworks, ripple_wave


app = Flask(__name__)

# **Debugging:** Replace servo call with an easy toggle
enable_servo = True  # Toggle to enable/disable servo

# Variable to track the number of treats left
treats_left = 9

# File to store IP addresses of users who have fed Apollo today
IP_TRACKING_FILE = "fed_ip_addresses.txt"

# Set up GPIO
GPIO.setmode(GPIO.BCM)  # Use Broadcom pin numbering
GPIO.setup(17, GPIO.OUT)  # Set GPIO pin 17 as output

# Set up PWM on the GPIO pin for the servo
servo = GPIO.PWM(17, 50)  # GPIO 17 for PWM with 50Hz frequency
servo.start(0)  # Initialize PWM with 0% duty cycle

# LED strip configuration:
LED_COUNT = 100      # Number of LED pixels.
LED_PIN = 18         # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ = 800000 # LED signal frequency in hertz (usually 800kHz)
LED_DMA = 10         # DMA channel to use for generating a signal (try 10)
LED_BRIGHTNESS = 65  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False   # True to invert the signal
LED_CHANNEL = 0      # Use channel 0

# Initialize the NeoPixel strip
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()


def get_current_date():
    """Returns the current date in YYYY-MM-DD format."""
    return datetime.now().strftime('%Y-%m-%d')

def load_ip_addresses():
    """Loads the list of IP addresses that have fed Apollo today."""
    if os.path.exists(IP_TRACKING_FILE):
        with open(IP_TRACKING_FILE, 'r') as file:
            lines = file.readlines()
            date = lines[0].strip()  # The first line should be the date
            if date == get_current_date():
                return set(line.strip() for line in lines[1:])
    return set()

def save_ip_address(ip):
    """Saves a new IP address to the tracking file."""
    with open(IP_TRACKING_FILE, 'a') as file:
        file.write(f"{ip}\n")

def reset_ip_tracking():
    """Resets the IP tracking file for a new day."""
    with open(IP_TRACKING_FILE, 'w') as file:
        file.write(f"{get_current_date()}\n")

def set_servo_angle(angle):
    """Set the servo to a specific angle."""
    duty_cycle = 2.5 + (angle / 18.0)  # Convert angle to duty cycle
    servo.ChangeDutyCycle(duty_cycle)
    time.sleep(0.5)  # Give the servo time to reach the position
    servo.ChangeDutyCycle(0)  # Stop the PWM signal

def reset_treats():
    """Resets the treat count and IP tracking daily at 3 AM ET."""
    global treats_left
    treats_left = 5
    reset_ip_tracking()
    print("Treats and IP tracking reset at 3 AM ET")

# Schedule the reset_treats function to run daily at 3 AM ET
scheduler = BackgroundScheduler()
scheduler.add_job(reset_treats, CronTrigger(hour=3, minute=0, timezone='US/Eastern'))
scheduler.start()

@app.route('/')
def home():
    bones = '🌟 ' * treats_left  # Display the remaining treats as emojis
    return render_template('index.html', treats=bones.strip())

@app.route('/give_treat', methods=['POST'])
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
        return jsonify({'error': 'You have already fed Apollo today!'}), 403

    # Update the treats count and add the IP address to the tracking file
    if treats_left > 0:
        treats_left -= 1
        message = "Apollo got a treat!"
        save_ip_address(user_ip)

        # Start the treat dispensing and LED animation in a separate thread
        def treat_and_lights():
            # Servo dispensing logic
            if enable_servo:
                set_servo_angle(36)  # Rotate the servo
                time.sleep(1)
                set_servo_angle(0)
                time.sleep(1)

            # Pick a random animation and run it
            animations = [
                lambda: rowChangeAndSparkle(strip, wait_ms=50, sparkle_time=5),
                lambda: explosion(strip, row_lengths, setup_delay=10, explosion_speed=150),
                lambda: fireworks(strip, row_lengths, num_fireworks=5, burst_delay=500, fade_time=3),
                lambda: ripple_wave(strip, row_lengths, feeder_index=9, ripple_color=Color(255, 255, 128), speed=150)
            ]
            random.choice(animations)()  # Pick and run one animation randomly

            # Reset the lights to red/green rows after the animation
            reset_lights(strip, row_lengths)


        # Run treat dispensing and lights asynchronously
        threading.Thread(target=treat_and_lights).start()

        # Immediately respond with a success message
        bones = '🌟 ' * treats_left  # Display the remaining treats as emojis
        return jsonify({'treats_left': bones.strip(), 'message': message})

    else:
        message = "No more treats left for today!"
        return jsonify({'error': message}), 403


@app.route('/thank_you')
def thank_you():
    return "Apollo has been fed! Thanks!"

if __name__ == '__main__':
    # Reset IP tracking at the start of the application
    reset_ip_tracking()
    try:
        app.run(host='0.0.0.0', port=8080)
    finally:
        # Cleanup GPIO on exit
        scheduler.shutdown()
        servo.stop()
        GPIO.cleanup()
