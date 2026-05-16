"""
agents/utils/rate_limiter.py
Simple rate limiter for API calls
"""
import time

class RateLimiter:
    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = calls_per_minute
        self.interval = 60.0 / calls_per_minute
        self.last_call = 0.0

    def wait(self):
        now = time.time()
        time_since_last = now - self.last_call
        if time_since_last < self.interval:
            time.sleep(self.interval - time_since_last)
        self.last_call = time.time()
