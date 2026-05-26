"""
Fault injector: floods a service with ERROR logs to test the full pipeline.

Usage:
    python -m simulators.fault_injector --service payment-service --count 80 --rate 0.9
"""
import argparse
import time
import random
from kafka.producer import publish_log

_FAULT_MESSAGES = {
    "payment-service": [
        "Database connection timeout after 5000ms",
        "Connection pool exhausted: max=5 active=5",
        "Payment gateway returned 503",
        "DB connection refused on port 5432",
    ],
    "auth-service": [
        "JWT validation failed: signature mismatch",
        "Redis session store connection refused",
        "Auth DB query timeout after 3000ms",
    ],
    "inventory-service": [
        "DB write failed: deadlock detected",
        "Kafka publish error: broker not available",
        "Out of disk space: cannot write audit log",
    ],
}

_DEFAULT_FAULTS = [
    "Internal server error",
    "Connection refused",
    "Request timeout",
]


def inject(service: str, count: int = 60, error_rate: float = 0.85, interval: float = 0.1) -> None:
    messages = _FAULT_MESSAGES.get(service, _DEFAULT_FAULTS)
    print(f"[fault_injector] Injecting {count} logs into '{service}' (error_rate={error_rate}) …")

    for i in range(count):
        if random.random() < error_rate:
            msg = random.choice(messages)
            publish_log(service, "ERROR", msg)
        else:
            publish_log(service, "INFO", "Service running normally")
        time.sleep(interval)

    print(f"[fault_injector] Done — {count} log events published.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--service",  default="payment-service")
    parser.add_argument("--count",    type=int,   default=60)
    parser.add_argument("--rate",     type=float, default=0.85)
    parser.add_argument("--interval", type=float, default=0.1)
    args = parser.parse_args()
    inject(args.service, args.count, args.rate, args.interval)
