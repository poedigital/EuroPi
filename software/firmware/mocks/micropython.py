import time

def const(value):
    """Mock MicroPython's const() function (simply returns the value)."""
    return value

def ticks_ms():
    """Mock `ticks_ms()` to return current time in milliseconds."""
    return int(time.time() * 1000)

def ticks_us():
    """Mock `ticks_us()` to return current time in microseconds."""
    return int(time.time() * 1_000_000)

def ticks_add(ticks, delta):
    """Mock `ticks_add()` to add a delta to ticks."""
    return ticks + delta

def ticks_diff(ticks1, ticks2):
    """Mock `ticks_diff()` to calculate the difference between two ticks."""
    return ticks1 - ticks2

print("[INFO] Using MOCK micropython module")