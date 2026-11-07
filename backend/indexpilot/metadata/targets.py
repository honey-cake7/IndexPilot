import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from indexpilot.config import Settings
from indexpilot.errors import DomainError
from indexpilot.metadata.models import MonitoredDatabase


def ensure_demo_target(session: Session, settings: Settings) -> uuid.UUID:
    values = dict(
        target_key="demo",
        host=settings.db_host,
        port=settings.db_port,
        database_name="indexpilot_demo",
        role_name="indexpilot_analyzer",
        credential_reference="analyzer_password",
    )
    session.execute(
        insert(MonitoredDatabase)
        .values(id=uuid.uuid4(), **values)
        .on_conflict_do_nothing(index_elements=["target_key"])
    )
    target = session.scalar(select(MonitoredDatabase).where(MonitoredDatabase.target_key == "demo"))
    if any(getattr(target, key) != value for key, value in values.items()):
        raise DomainError(
            "target_changed", "Configured target differs from its saved identity.", 409
        )
    return target.id
