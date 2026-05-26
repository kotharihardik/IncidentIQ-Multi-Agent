import time
import random
from kafka.producer import publish_log

SERVICE = "inventory-service"

_NORMAL = [
    "Stock level checked for product {prod_id}",
    "Inventory reserved for order {order_id}",
    "Stock replenishment triggered for {prod_id}",
    "Cache updated for category {cat}",
]

_ERRORS = [
    "Stock reservation failed: negative inventory for {prod_id}",
    "DB write failed: deadlock detected",
    "Kafka publish error: broker not available",
    "Out of disk space: cannot write audit log",
]


def _rand_id(prefix: str) -> str:
    return f"{prefix}-{random.randint(1000, 9999)}"


def run(error_rate: float = 0.03, interval: float = 0.6) -> None:
    print(f"[{SERVICE}] Starting simulator (error_rate={error_rate}) …")
    while True:
        if random.random() < error_rate:
            msg = random.choice(_ERRORS).format(
                prod_id=_rand_id("prod"),
                order_id=_rand_id("ord"),
            )
            publish_log(SERVICE, "ERROR", msg)
        else:
            msg = random.choice(_NORMAL).format(
                prod_id=_rand_id("prod"),
                order_id=_rand_id("ord"),
                cat=random.choice(["electronics", "apparel", "grocery"]),
            )
            publish_log(SERVICE, "INFO", msg)
        time.sleep(interval)


if __name__ == "__main__":
    run()
