from flask import Flask, render_template, jsonify, request
import os
from datetime import datetime
import RPi.GPIO as GPIO
import time

app = Flask(__name__)

# Variable to track the number of treats left
treats_left = 5

# File to store IP addresses of users who have fed Apollo today
IP_TRACKING_FILE = "fed_ip_addresses.txt"

# Set up GPIO
GPIO.setmode(GPIO.BCM)  # Use Broadcom pin numbering
GPIO.setup(17, GPIO.OUT)  # Set GPIO pin 17 as output

# Set up PWM on the GPIO pin for the servo
servo = GPIO.PWM(17, 50)  # GPIO 17 for PWM with 50Hz frequency
servo.start(0)  # Initialize PWM with 0% duty cycle

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


@app.route('/')
def home():
    bones = '🍩 ' * treats_left  # Display the remaining treats as doughnut emojis
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
        set_servo_angle(36)  # Rotate the servo
        time.sleep(1)
        set_servo_angle(0)
        time.sleep(1)
        bones = '🍩 ' * treats_left  # Display the remaining treats as dog bone emojis
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
        servo.stop()
        GPIO.cleanup()
