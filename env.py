import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# --- CRA PROTOCOL: ALEMBIC MIGRATION ENGINE ---
# [span_3](start_span)Purpose: Incremental migrations for audit-grade history[span_3](end_span)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# [span_4](start_span)Database connection logic for technical enforcement[span_4](end_span)
db_url = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/cra_protocol")
config.set_main_option("sqlalchemy.url", db_url)

def run_migrations_online():
    """Run migrations in 'online' mode for protocol law enforcement."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=None
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    # [span_5](start_span)Placeholder for offline 'Artifact Serialization' logic[span_5](end_span)
    pass
else:
    run_migrations_online()
