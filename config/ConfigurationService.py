import os
import redis


class ConfigurationService:
    """
    Minimal Redis client for configuration reads/writes.
    Uses env vars:
      REDIS_HOST (default: 127.0.0.1)
      REDIS_PORT (default: 6379)
      REDIS_PASSWORD (required)
    """

    def __init__(self):
        host = os.getenv("REDIS_HOST", "127.0.0.1")
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD")

        if not password:
            raise RuntimeError("REDIS_PASSWORD is not set. Add it to your environment or .env file.")

        # decode_responses=True makes Redis return Python strings instead of bytes
        self.client = redis.Redis(
            host=host,
            port=port,
            password=password,
            decode_responses=True,
        )

    def ping(self) -> bool:
        return self.client.ping()

    def get(self, key: str):
        return self.client.get(key)

    def set(self, key: str, value):
        # For now, just store as a string for initial test
        self.client.set(key, value)
