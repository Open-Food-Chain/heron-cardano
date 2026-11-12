from logging.config import fileConfig
from sqlalchemy import create_engine, pool, text # type: ignore
from alembic import context # type: ignore

from heron_app.core.config import settings
from heron_app.db.database import Base
from heron_app.db.models import wallet, transaction, transaction_output, transaction_output_asset, minting_policies

config = context.config

fileConfig(config.config_file_name)

target_metadata = Base.metadata

SCHEMA = settings.POSTGRES_SCHEMA


def run_migrations_offline():
    # The URL goes straight to context.configure: config.set_main_option
    # would treat the % of an escaped password as configparser interpolation.
    url = settings.DATABASE_URL.render_as_string(hide_password=False)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=SCHEMA,
    )

    with context.begin_transaction():
        if SCHEMA:
            context.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
            context.execute(f"SET search_path TO {SCHEMA}")
        context.run_migrations()

def run_migrations_online():
    connectable = create_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
        connect_args=settings.DB_CONNECT_ARGS,
    )

    with connectable.connect() as connection:
        if SCHEMA:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
            connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=SCHEMA,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    print("TABLES SEEN BY ALEMBIC:", Base.metadata.tables.keys())

    run_migrations_online()