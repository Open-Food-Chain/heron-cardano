import os
import re
from dotenv import load_dotenv
from sqlalchemy.engine import URL

load_dotenv()

SCHEMA_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _env(name, default=None):
    # An empty value counts as unset.
    return os.getenv(name) or default


class Settings:

    POSTGRES_USER = _env("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = _env("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST = _env("POSTGRES_HOST", "db")
    POSTGRES_PORT = int(_env("POSTGRES_PORT", "5432"))
    POSTGRES_DB = _env("POSTGRES_DB", "heron_db")
    POSTGRES_SCHEMA = _env("POSTGRES_SCHEMA")

    if POSTGRES_SCHEMA is not None and (
        len(POSTGRES_SCHEMA) > 63 or not SCHEMA_PATTERN.match(POSTGRES_SCHEMA)
    ):
        raise ValueError(
            "POSTGRES_SCHEMA is invalid: use letters, digits and underscore, "
            "not starting with a digit, at most 63 characters"
        )

    # URL object: user and password are escaped when it is rendered.
    DATABASE_URL = URL.create(
        drivername="postgresql",
        username=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
    )

    # Passed as SQLAlchemy connect_args; empty when no schema is set.
    DB_CONNECT_ARGS = (
        {"options": f"-c search_path={POSTGRES_SCHEMA}"} if POSTGRES_SCHEMA else {}
    )

settings = Settings()
