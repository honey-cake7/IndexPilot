from sqlalchemy import URL, Engine, create_engine

from indexpilot.config import Settings
from indexpilot.local import LocalConnectionError


def metadata_engine(settings: Settings) -> Engine:
    try:
        password = (settings.secret_dir / "meta_password").read_text(encoding="utf-8").strip()
    except OSError:
        raise LocalConnectionError("credential_file_unavailable") from None
    url = URL.create(
        "postgresql+psycopg",
        username="indexpilot_meta",
        password=password,
        host=settings.db_host,
        port=settings.db_port,
        database="indexpilot_meta",
    )
    return create_engine(
        url,
        hide_parameters=True,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        connect_args={
            "connect_timeout": settings.connect_timeout,
            "options": "-c statement_timeout=5000 -c lock_timeout=1000",
        },
    )
