import os
import time
import uuid


def uuid7() -> uuid.UUID:
    """Generate a time-ordered UUIDv7 (RFC 9562).

    UUIDv7 embeds a 48-bit Unix ms timestamp in the high bits, so rows sort
    chronologically by PK — cheaper B-tree inserts than random UUID4.
    """
    ms = int(time.time() * 1000)
    rand_bytes = os.urandom(10)
    rand_a = int.from_bytes(rand_bytes[:2], "big") & 0x0FFF   # 12 random bits
    rand_b = int.from_bytes(rand_bytes[2:], "big") & 0x3FFFFFFFFFFFFFFF  # 62 random bits
    val = (
        (ms & 0xFFFFFFFFFFFF) << 80   # 48-bit timestamp in top bits
        | (0x7 << 76)                  # version = 7
        | (rand_a << 64)               # rand_a occupies bits 64-75
        | (0b10 << 62)                 # RFC 9562 variant bits
        | rand_b
    )
    return uuid.UUID(int=val)
