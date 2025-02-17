from europi import *
import math
import time

# OLED dimensions
OLED_WIDTH = 128
OLED_HEIGHT = 32

# Radii for sun/moon
SUN_RADIUS = 6
MOON_RADIUS = 3

# Approx length of lunar cycle (New Moon -> Full Moon -> New Moon)
MOON_CYCLE_DAYS = 29.53

# -------------------------------------------------------
# 1) Moon Phase Calculation
# -------------------------------------------------------
def get_moon_phase(day):
    """
    Returns the moon phase fraction between 0.0 and 1.0
    0.0 = New Moon, 0.5 = Full Moon
    """
    return (day % MOON_CYCLE_DAYS) / MOON_CYCLE_DAYS

# -------------------------------------------------------
# 2) Drawing a Filled Circle
# -------------------------------------------------------
def draw_circle(oled, x_center, y_center, radius, fill=True):
    """
    Manually draw a circle on the OLED by setting pixels.
    If fill=False, it draws just the outline.
    """
    for x in range(-radius, radius + 1):
        for y in range(-radius, radius + 1):
            if (x**2 + y**2) <= (radius**2):
                # If fill=True or if near the edge, draw pixel
                if fill or (x**2 + y**2) >= (radius - 1)**2:
                    px = x_center + x
                    py = y_center + y
                    if 0 <= px < OLED_WIDTH and 0 <= py < OLED_HEIGHT:
                        oled.pixel(px, py, 1)

# -------------------------------------------------------
# 3) Sun Rendering
# -------------------------------------------------------
def render_sun(oled, time_of_day):
    """
    We linearly move the sun across the screen left -> right from x=0 at t=0
    until x=OLED_WIDTH at t=24.
    Y is a fixed position so it doesn't appear mirrored with the moon.
    """
    # Fraction of day from 0.0 to 1.0
    day_frac = time_of_day / 24.0

    # Sun X position
    sun_x = int(day_frac * OLED_WIDTH)
    # Sun Y position (fixed near top)
    sun_y = 8

    # Draw bigger sun
    draw_circle(oled, sun_x, sun_y, SUN_RADIUS, fill=True)

# -------------------------------------------------------
# 4) Moon Rendering
# -------------------------------------------------------
def render_moon(oled, time_of_day, phase):
    """
    Similar horizontal movement, but offset by 12 hours (half a day)
    so it doesn't mirror the sun. Also placed lower (y=24).
    """
    # Offset time_of_day by 12 hours so the moon leads/lags the sun
    moon_time = (time_of_day + 12) % 24  # shift by half a day
    day_frac = moon_time / 24.0

    # Moon X position
    moon_x = int(day_frac * OLED_WIDTH)
    # Moon Y position (fixed near bottom)
    moon_y = 24

    # 1) Draw full moon
    draw_circle(oled, moon_x, moon_y, MOON_RADIUS, fill=True)

    # 2) Mask for moon phase
    # phase goes from 0.0 (new) -> 0.5 (full) -> 1.0 (new)
    # We interpret 0.0 or 1.0 as New Moon, 0.5 as Full Moon.

    # We'll do a simple "slice" from left to right to represent the shadow:
    #   - at new moon (phase=0.0 or near 1.0), the entire circle is masked
    #   - at full moon (phase=0.5), none is masked
    # We'll shift the shadow from left to right as the phase moves from 0->0.5->1.0

    # This simple approach: shadow portion = phase * moon diameter
    # but we shift center if phase > 0.5 so it "waxes" and "wanes" properly.
    diameter = MOON_RADIUS * 2
    # Convert phase [0..1] into [0..diameter] for the "shadow" width
    shadow_width = int(phase * diameter)

    # We'll center the shadow around 0.5
    # If phase < 0.5 -> shadow on right side, if phase > 0.5 -> shadow on left side
    # A quick trick: offset = shadow_width/2 if phase>0.5
    # Or simpler: we can just do a naive approach:
    #   - for waxing from 0.0->0.5, shadow goes from entire left to none
    #   - from 0.5->1.0, shadow goes from none to entire right
    # So let's do it in two halves:

    if phase <= 0.5:
        # Shadow is on the right part. (Waxing from new -> full)
        mask_start_x = moon_x + (diameter // 2 - shadow_width)
        mask_end_x   = moon_x + (diameter // 2)
    else:
        # Shadow is on the left part. (Waning from full -> new)
        # Phase in [0.5..1], so let's find "subphase" from 0..0.5
        subphase = (phase - 0.5) * 2  # ranges 0..1
        shadow_width = int(subphase * diameter)
        mask_start_x = moon_x - (diameter // 2)
        mask_end_x   = moon_x - (diameter // 2) + shadow_width

    # Now "erase" (pixel=0) the shadow area
    for x in range(mask_start_x, mask_end_x):
        if 0 <= x < OLED_WIDTH:
            for y in range(-MOON_RADIUS, MOON_RADIUS + 1):
                py = moon_y + y
                if 0 <= py < OLED_HEIGHT:
                    # Only erase if within the moon circle
                    if x - moon_x != 0 or y != 0:
                        dist_sq = (x - moon_x)**2 + (y)**2
                        if dist_sq <= MOON_RADIUS**2:
                            oled.pixel(x, py, 0)

# -------------------------------------------------------
# 5) Main Render Function
# -------------------------------------------------------
def render_oled(oled, time_of_day, day):
    """
    Clears the screen, draws the sun and the moon, then shows the result.
    """
    oled.fill(0)  # Clear screen
    # Draw sun
    render_sun(oled, time_of_day)
    # Draw moon with correct lunar phase
    moon_phase = get_moon_phase(day)
    render_moon(oled, time_of_day, moon_phase)
    oled.show()

# -------------------------------------------------------
# 6) Main Loop with "Global Time"
# -------------------------------------------------------
global_time = 0.0  # This will accumulate hours
while True:
    # Extract fractional "hour" for the day 0..24
    time_of_day = global_time % 24
    # Extract day number
    day = int(global_time // 24)

    # Render
    render_oled(oled, time_of_day, day)

    # Advance time. Each loop = 0.25 hours so 6 loops = 1.5 hours, ~6 loops for a day in 6s
    global_time += 0.25

    time.sleep(0.1)  # real-time delay
