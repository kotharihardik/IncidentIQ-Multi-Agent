"""
Simulates a payment service that generates realistic structured logs.
Run this to populate Kafka with log data for testing.
"""
import time
import random
from kafka.producer import publish_log

SERVICE = "payment-service"

_NORMAL_MESSAGES = [
    "Payment processed successfully",
    "Transaction {txn_id} completed",
    "DB query executed in {ms}ms",
    "Redis cache hit for user {user_id}",
    "Webhook sent to {provider}",
]

_ERROR_MESSAGES = [
    "Database connection timeout after 5000ms",
    "Connection pool exhausted: max=5 active=5",
    "Payment gateway returned 503",
    "Transaction {txn_id} failed: insufficient funds",
    "DB connection refused on port 5432",
]


def _rand_id(prefix: str) -> str:
    return f"{prefix}-{random.randint(10000, 99999)}"


def run(error_rate: float = 0.05, interval: float = 0.5) -> None:
    """
    Publish logs continuously.

    Parameters
    ----------
    error_rate : float  probability of an ERROR log per tick
    interval   : float  seconds between log events
    """
    print(f"[{SERVICE}] Starting simulator (error_rate={error_rate}) …")
    while True:
        if random.random() < error_rate:
            msg = random.choice(_ERROR_MESSAGES).format(
                txn_id=_rand_id("txn"),
                user_id=_rand_id("usr"),
                provider=random.choice(["stripe", "paypal", "razorpay"]),
                ms=random.randint(1000, 6000),
            )
            publish_log(SERVICE, "ERROR", msg, extra={"trace_id": _rand_id("tr")})
        else:
            msg = random.choice(_NORMAL_MESSAGES).format(
                txn_id=_rand_id("txn"),
                user_id=_rand_id("usr"),
                provider=random.choice(["stripe", "paypal", "razorpay"]),
                ms=random.randint(5, 120),
            )
            publish_log(SERVICE, "INFO", msg, extra={"trace_id": _rand_id("tr"),
                                                      "latency_ms": random.randint(5, 120)})
        time.sleep(interval)


if __name__ == "__main__":
    run(error_rate=0.05)
