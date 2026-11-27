"""Read application settings from environment variables."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """Runtime settings; database credentials are hidden from repr output."""

    database_url: str = field(repr=False)

    @classmethod
    def from_env(cls) -> "Settings":
        """Read and validate the required DATABASE_URL setting."""
        database_url = os.environ.get("DATABASE_URL")
        if database_url is None or not database_url.strip():
            raise ValueError("DATABASE_URL must be set to a non-empty database URL")
        return cls(database_url=database_url.strip())
