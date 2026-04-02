import re
from sqlalchemy import engine_from_config, pool
from alembic import context
from logging.config import fileConfig
from config.setting import env
import logging
from dotenv import load_dotenv
load_dotenv()

# Konfigurasi dasar
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

target_metadata = config.attributes.get('target_metadata')
db_names = config.get_main_option("databases")

def run_migrations_online() -> None:
    """Jalankan migrasi dalam mode 'online'."""
    engines = {}
    for name in re.split(r",\s*", db_names):
        engines[name] = {
            "engine": engine_from_config(
                config.get_section(name), prefix="sqlalchemy.", poolclass=pool.NullPool
            )
        }
    
    for name, rec in engines.items():
        engine = rec["engine"]
        current_metadata = target_metadata.get(name)
        with engine.connect() as connection:
            configure_args = {
                "connection": connection,
                "target_metadata": current_metadata,
                "compare_type": True,
                "upgrade_token": f"{name}_upgrades",
                "downgrade_token": f"{name}_downgrades",
            }
            if env.LIMIT_ALEMBIC_SCOPE == 1:
                configure_args["include_objects"] = current_metadata.tables.values()
            context.configure(**configure_args)
            with context.begin_transaction():
                context.run_migrations(engine_name=name)

if not context.is_offline_mode():
    run_migrations_online()
