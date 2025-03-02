#!/usr/bin/env python3
# NeoPixel library strandtest example
# Author: Tony DiCola (tony@tonydicola.com)
#
# Direct port of the Arduino NeoPixel library strandtest example.  Showcases
# various animations on a strip of NeoPixels.

import time
from rpi_ws281x import *
import argparse
import random
# LED strip configuration:
LED_COUNT      = 100     # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
#LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10      # DMA channel to use for generating a signal (try 10)
LED_BRIGHTNESS = 65      # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53



# Define functions which animate LEDs in various ways.
def colorWipe(strip, color, wait_ms=50):
    """Wipe color across display a pixel at a time."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)

def theaterChase(strip, color, wait_ms=50, iterations=10):
    """Movie theater light style chaser animation."""
    for j in range(iterations):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, color)
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)

def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)

def rainbow(strip, wait_ms=20, iterations=1):
    """Draw rainbow that fades across all pixels at once."""
    for j in range(256*iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((i+j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)

def rainbowCycle(strip, wait_ms=20, iterations=5):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    for j in range(256*iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)

def theaterChaseRainbow(strip, wait_ms=50):
    """Rainbow movie theater light style chaser animation."""
    for j in range(256):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, wheel((i+j) % 255))
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)

# HARD CODE ROW LENGTHS
row_lengths = [20, 16, 15, 14, 16, 19]

def rowChangeAndSparkle(strip, wait_ms=50, sparkle_time=2):
    """Light up rows top to bottom in alternating colors, then randomly sparkle with white."""
    # Define alternating colors: red and green
    colors = [Color(255, 0, 0), Color(0, 255, 0)]  # Red, Green
    
    # Top to bottom lighting
    for i in reversed(range(len(row_lengths))):  # Reverse the row index order
        row_start = int(sum(row_lengths[:i]))  # Starting index of the current row
        row_end = row_start + row_lengths[i]      # Ending index of the current row
        
        # Get the current color (alternate between red and green)
        color = colors[i % 2]
        
        for j in range(row_start, row_end):       # Iterate through LEDs in the current row
            strip.setPixelColor(j, color)
            strip.show()
            time.sleep(wait_ms / 1000.0)
    
    # Sparkle effect
    sparkle_end_time = time.time() + sparkle_time
    while time.time() < sparkle_end_time:
        # Choose a random LED to sparkle white
        random_led = random.randint(0, strip.numPixels() - 1)
        original_color = strip.getPixelColor(random_led)  # Save the original color
        
        # Set to white temporarily
        strip.setPixelColor(random_led, Color(255, 255, 255))
        strip.show()
        time.sleep(0.1)  # Short sparkle duration
        
        # Restore the original color
        strip.setPixelColor(random_led, original_color)
        strip.show()

    for i,row in enumerate(row_lengths):
        current_ind = int(sum(row_lengths[0:i]))
        for j in range(row):
            strip.setPixelColor(int(j+current_ind), color)
            strip.show()
        time.sleep(wait_ms/1000.0)


def explosion(strip, row_lengths, setup_delay=10, explosion_speed=1000):
    """Light rows in red/green quickly, then explode white radially both horizontally and vertically."""
    # Define alternating colors: red and green
    colors = [Color(255, 0, 0), Color(0, 255, 0)]  # Red, Green

    # 1. Light rows in alternating red and green (quickly)
    for i in range(len(row_lengths)):  # Top-to-bottom row order
        row_start = int(sum(row_lengths[:i]))  # Start index of the current row
        row_end = row_start + int(row_lengths[i])  # End index of the current row
        
        color = colors[i % 2]  # Alternate between red and green
        for j in range(row_start, row_end):       # Light up the row quickly
            strip.setPixelColor(int(j), color)
        strip.show()
        time.sleep(setup_delay / 1000.0)  # Short delay between rows

    # 2. Calculate the middle row for vertical explosion
    total_rows = len(row_lengths)
    middle_row = total_rows // 2  # Middle row index
    total_leds = int(sum(row_lengths))  # Total number of LEDs

    # Create an explosion that propagates both vertically and horizontally
    max_radius = max(row_lengths)  # Determine the maximum radius for explosion
    for radius in range(int(max_radius)):
        for row_offset in range(total_rows):
            # Vertical propagation: Move outward from the middle row
            for direction in [-1, 1]:  # Upward (-1) and downward (+1)
                current_row = middle_row + direction * row_offset
                if 0 <= current_row < total_rows:
                    row_start = int(sum(row_lengths[:current_row]))
                    row_middle = row_start + (int(row_lengths[current_row]) // 2)
                    row_end = row_start + int(row_lengths[current_row])
                    
                    # Horizontal propagation: Light LEDs outward from the row middle
                    left_led = int(row_middle - radius) if row_middle - radius >= row_start else None
                    right_led = int(row_middle + radius) if row_middle + radius < row_end else None
                    
                    if left_led is not None:
                        strip.setPixelColor(int(left_led), Color(255, 255, 255))  # White
                    if right_led is not None:
                        strip.setPixelColor(int(right_led), Color(255, 255, 255))  # White
            
        # Show the changes for this radius
        strip.show()
        time.sleep(explosion_speed / 1000.0)  # Delay between radial expansions

    # Optionally: Turn off all LEDs after explosion
    for i in range(total_leds):
        strip.setPixelColor(int(i), Color(0, 0, 0))  # Turn off
    strip.show()

def reset_lights(strip, row_lengths):
    """
    Reset the LEDs to alternating red/green rows.
    :param strip: The LED strip object.
    :param row_lengths: Array of row lengths.
    """
    base_colors = [Color(255, 0, 0), Color(0, 255, 0)]  # Red and Green
    for i in range(sum(row_lengths)):
        strip.setPixelColor(i, base_colors[i % len(base_colors)])
    strip.show()


def generate_vibrant_color():
    """
    Generate a vibrant random color with a preference for one dominant channel.
    Occasionally allows two dominant channels, but avoids whites/pastels.
    """
    channels = [0, 0, 0]  # Initialize RGB channels

    # Decide how many channels will dominate (prefer 1, occasionally 2)
    dominant_count = 1 if random.random() < 0.7 else 2  # 70% single, 30% double

    # Randomly pick which channels will dominate
    dominant_indices = random.sample(range(3), k=dominant_count)

    for i in range(3):
        if i in dominant_indices:
            channels[i] = random.randint(128, 255)  # High intensity for dominant channels
        else:
            channels[i] = random.randint(0, 64)    # Low intensity for non-dominant channel

    return Color(channels[0], channels[1], channels[2])



def fireworks(strip, row_lengths, num_fireworks=3, burst_delay=500, fade_time=2):
    """
    Simulate a fireworks celebration with bursts, radial expansion, and twinkles.
    :param strip: The LED strip object.
    :param row_lengths: Array of row lengths.
    :param num_fireworks: Number of fireworks to simulate.
    :param burst_delay: Delay (ms) between fireworks.
    :param fade_time: Time (seconds) for the final fade-out.
    """
    total_leds = int(sum(row_lengths))  # Total number of LEDs

    for _ in range(num_fireworks):
        # 1. Select a random burst point
        burst_row = random.randint(0, len(row_lengths) - 1)  # Random row
        row_start = int(sum(row_lengths[:burst_row]))  # Start index of the burst row
        row_middle = row_start + (int(row_lengths[burst_row]) // 2)  # Middle of the row

        # 2. Generate a vibrant random color across the full spectrum
        firework_color = generate_vibrant_color()
        
        # Initial bright burst
        strip.setPixelColor(int(row_middle), firework_color)  # Bright colored burst
        strip.show()
        time.sleep(0.1)  # Small pause for burst visibility

        # 3. Radial expansion
        max_radius = max(row_lengths)  # Determine maximum possible radius
        for radius in range(1, max_radius):
            for row_offset in range(-radius, radius + 1):
                current_row = burst_row + row_offset
                if 0 <= current_row < len(row_lengths):
                    # Get the row boundaries
                    row_start = int(sum(row_lengths[:current_row]))
                    row_end = row_start + int(row_lengths[current_row])
                    row_middle = row_start + (int(row_lengths[current_row]) // 2)

                    # Expand outward from the middle
                    left_led = int(row_middle - radius) if row_middle - radius >= row_start else None
                    right_led = int(row_middle + radius) if row_middle + radius < row_end else None

                    if left_led is not None:
                        strip.setPixelColor(int(left_led), firework_color)
                    if right_led is not None:
                        strip.setPixelColor(int(right_led), firework_color)
            strip.show()
            time.sleep(0.05)  # Speed of radial expansion

        # 4. Fade-out twinkles
        twinkle_time = time.time() + fade_time
        while time.time() < twinkle_time:
            random_led = int(random.randint(0, total_leds - 1))
            original_color = strip.getPixelColor(int(random_led))
            strip.setPixelColor(int(random_led), Color(255, 255, 255))  # Twinkle to white
            strip.show()
            time.sleep(0.05)
            strip.setPixelColor(int(random_led), original_color)  # Restore original color
            strip.show()

        # Clear the strip for the next firework
        for i in range(total_leds):
            strip.setPixelColor(int(i), Color(0, 0, 0))
        strip.show()
        time.sleep(burst_delay / 1000.0)  # Delay before the next firework



def ripple_wave(strip, row_lengths, feeder_index=9, ripple_color=Color(255, 255, 128), speed=100):
    """
    Create a ripple-down animation starting from the top (last row) and ending at the treat feeder.
    :param strip: The LED strip object.
    :param row_lengths: Array of row lengths (bottom row is first in the list).
    :param feeder_index: The index where the ripple ends (the treat feeder).
    :param ripple_color: The ripple wave color (yellowish white).
    :param speed: Speed of the ripple (ms between updates).
    """
    total_leds = sum(row_lengths)

    # Step 1: Initialize all LEDs in alternating red and green
    base_colors = [Color(255, 0, 0), Color(0, 255, 0)]  # Red and Green
    for i in range(total_leds):
        strip.setPixelColor(i, base_colors[i % len(base_colors)])
    strip.show()

    # Step 2: Create the ripple-down wave (from top to bottom)
    for i in range(len(row_lengths) - 1, -1, -1):  # Iterate from last row (top) to first row (bottom)
        row_start = int(sum(row_lengths[:i]))  # Start index of the current row
        row_end = row_start + row_lengths[i]  # End index of the current row

        # Ripple across the row
        for j in range(row_start, row_end):
            strip.setPixelColor(j, ripple_color)  # Set the ripple color
        strip.show()
        time.sleep(speed / 1000.0)  # Pause before moving to the next row

        # Restore the row back to its base colors after the ripple passes
        for j in range(row_start, row_end):
            strip.setPixelColor(j, base_colors[j % len(base_colors)])
        strip.show()

    # Step 3: Conclude the ripple at the feeder
    for i in range(feeder_index + 1):  # Ripple specifically to the feeder index
        strip.setPixelColor(i, ripple_color)  # Keep the ripple color at the feeder index
        if i > 0:
            strip.setPixelColor(i - 1, base_colors[(i - 1) % len(base_colors)])  # Restore previous
        strip.show()
        time.sleep(speed / 1000.0)

    # Step 4: Final highlight at the feeder
    for _ in range(3):  # Flash 3 times
        strip.setPixelColor(feeder_index, Color(255, 255, 255))  # Bright white flash
        strip.show()
        time.sleep(0.1)
        strip.setPixelColor(feeder_index, ripple_color)  # Restore ripple color
        strip.show()
        time.sleep(0.1)
def drawHeart(strip, heart_color=Color(255, 105, 180), wait_ms=50):
    """
    Lights up the LEDs in a heart shape pattern using a soft pink color.
    Assumes a rough center alignment of rows.
    
    :param strip: LED strip object
    :param heart_color: Color object for the heart (default: pink)
    :param wait_ms: Delay for smooth animation (milliseconds)
    """
    
    # Proper heart pattern (0 = off, 1 = lit)
    heart_matrix = [
        "00110011001100000000",  # Row 1 (20 LEDs)
        "01111111111111000000",  # Row 2 (16 LEDs)
        "01111111111111000000",  # Row 3 (15 LEDs)
        "00111111111100000000",  # Row 4 (14 LEDs)
        "00011111111000000000",  # Row 5 (16 LEDs)
        "00001111110000000000",  # Row 6 (19 LEDs)
    ]
    
    # Convert heart matrix to LED positions
    for row_idx, row_pattern in enumerate(heart_matrix):
        row_start = int(sum(row_lengths[:row_idx]))  # Start index of the row
        row_leds = row_lengths[row_idx]  # Number of LEDs in this row
        
        # Trim to match actual row length
        row_pattern = row_pattern[:row_leds]
        
        for char_idx, char in enumerate(row_pattern):
            if char == '1':  # Light up only heart shape positions
                strip.setPixelColor(row_start + char_idx, heart_color)
                strip.show()
                time.sleep(wait_ms / 1000.0)  # Smooth animation delay

    # Hold the heart for a moment
    time.sleep(2)

    # Fade out effect
    for brightness in range(255, 0, -15):
        dim_color = Color(
            (heart_color >> 16 & 0xFF) * brightness // 255,  # Red channel
            (heart_color >> 8 & 0xFF) * brightness // 255,   # Green channel
            (heart_color & 0xFF) * brightness // 255         # Blue channel
        )
        
        for row_idx, row_pattern in enumerate(heart_matrix):
            row_start = int(sum(row_lengths[:row_idx]))
            row_leds = row_lengths[row_idx]
            
            row_pattern = row_pattern[:row_leds]
            
            for char_idx, char in enumerate(row_pattern):
                if char == '1':
                    strip.setPixelColor(row_start + char_idx, dim_color)
        
        strip.show()
        time.sleep(0.1)  # Smooth dimming

    # Clear the heart
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))  # Turn off all LEDs
    strip.show()


'''
# Main program logic follows:
if __name__ == '__main__':
    # Process arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
    args = parser.parse_args()

    # Create NeoPixel object with appropriate configuration.
    strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    # Intialize the library (must be called once before other functions).
    strip.begin()

    print ('Press Ctrl-C to quit.')
    if not args.clear:
        print('Use "-c" argument to clear LEDs on exit')

    try:

        while True:
            print('custom tests')
            #rowChangeAndSparkle(strip, wait_ms=50, sparkle_time=5)
            #explosion(strip, row_lengths, setup_delay=10, explosion_speed=150)
            #fireworks(strip, row_lengths, num_fireworks=5, burst_delay=500, fade_time=3)
            ripple_wave(strip, row_lengths, feeder_index=9, ripple_color=Color(255, 255, 128), speed=150)


            
            print ('Color wipe animations.')
            colorWipe(strip, Color(255, 0, 0))  # Red wipe
            colorWipe(strip, Color(0, 255, 0))  # Blue wipe
            colorWipe(strip, Color(0, 0, 255))  # Green wipe
            print ('Theater chase animations.')
            theaterChase(strip, Color(127, 127, 127))  # White theater chase
            theaterChase(strip, Color(127,   0,   0))  # Red theater chase
            theaterChase(strip, Color(  0,   0, 127))  # Blue theater chase
            print ('Rainbow animations.')
            rainbow(strip)
            rainbowCycle(strip)
            theaterChaseRainbow(strip)
            

    except KeyboardInterrupt:
        if args.clear:
            colorWipe(strip, Color(0,0,0), 10)
'''
