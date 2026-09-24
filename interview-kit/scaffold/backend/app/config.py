# All runtime configuration, read once from the environment (12-factor).
# A bad value (e.g. CACHE_TTL=abc) fails at startup, not on the first request.

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_env: str
    git_sha: str
    build_time: str
    database_url: str
    redis_url: str
    log_level: str
    cache_ttl: int
    cors_origins: list[str]
    max_batch_size: int
    max_pending_batches: int
    worker_poll_seconds: float
    worker_max_attempts: int

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ.get
        return cls(
            app_env=env("APP_ENV", "dev"),
            # Baked into the image at build time (Dockerfile ARG) -> /version answers
            # "which commit is running?" with no access to CI or the cloud console.
            git_sha=env("GIT_SHA", "dev"),
            build_time=env("BUILD_TIME", ""),
            database_url=env("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/app"),
            redis_url=env("REDIS_URL", "redis://localhost:6379/0"),  # set to "" to run without a cache
            log_level=env("LOG_LEVEL", "INFO").upper(),
            cache_ttl=int(env("CACHE_TTL", "60")),
            cors_origins=env("CORS_ORIGINS", "*").split(","),
            max_batch_size=int(env("MAX_BATCH_SIZE", "1000")),
            max_pending_batches=int(env("MAX_PENDING_BATCHES", "500")),
            worker_poll_seconds=float(env("WORKER_POLL_SECONDS", "0.5")),
            worker_max_attempts=int(env("WORKER_MAX_ATTEMPTS", "3")),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
