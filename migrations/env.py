from alembic import context
from indexpilot.config import Settings
from indexpilot.metadata.models import Base
from indexpilot.metadata.session import metadata_engine

target_metadata = Base.metadata

if context.is_offline_mode():
    raise RuntimeError(
        "Offline migrations disabled: no credential-bearing URL is written to config."
    )

engine = metadata_engine(Settings())
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
