from __future__ import annotations

from alembic import context

from sourceatlas.db.models import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Run migrations via sourceatlas.db.session.run_migrations")
context.configure(connection=connection, target_metadata=Base.metadata)
with context.begin_transaction():
    context.run_migrations()
