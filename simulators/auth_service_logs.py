import time
import random
from kafka.producer import publish_log

SERVICE = "auth-service"

_NORMAL = [
    "User {user_id} logged in successfully",
    "JWT token issued for user {user_id}",
    "Password validation passed",
    "Session refreshed for user {user_id}",
]

_ERRORS = [
    "JWT validation failed: signature mismatch",
    "Redis session store connection refused",
    "Too many login attempts for user {user_id} — rate limited",
    "RSA key decode error: invalid PEM format",
    "Auth DB query timeout after 3000ms",
]


def _rand_id(prefix: str) -> str:
    return f"{prefix}-{random.randint(10000, 99999)}"


def run(error_rate: float = 0.04, interval: float = 0.4) -> None:
    print(f"[{SERVICE}] Starting simulator (error_rate={error_rate}) …")
    while True:
        if random.random() < error_rate:
            msg = random.choice(_ERRORS).format(user_id=_rand_id("usr"))
            publish_log(SERVICE, "ERROR", msg)
        else:
            msg = random.choice(_NORMAL).format(user_id=_rand_id("usr"))
            publish_log(SERVICE, "INFO", msg, extra={"latency_ms": random.randint(2, 80)})
        time.sleep(interval)


if __name__ == "__main__":
    run()
