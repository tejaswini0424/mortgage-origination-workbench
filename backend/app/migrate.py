"""Apply workbench migrations, including recognized pre-Alembic SQLite databases."""

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .storage import Base, engine

def migrate():
    config = Config("alembic.ini")
    with engine.connect() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        if "alembic_version" not in tables and "cases" in tables:
            columns = {column["name"] for column in inspector.get_columns("cases")}
            if set(Base.metadata.tables) <= tables and {"organization", "owner"} <= columns:
                command.stamp(config, "head")
            elif {"documents", "cases"} <= tables and {"id", "title", "borrower", "status", "events", "calculation", "packet"} <= columns and "organization" not in columns:
                command.stamp(config, "0002_exports" if "case_exports" in tables else "0001_workbench")
            else:
                raise RuntimeError("Unrecognized pre-migration database. Back it up before continuing.")
    command.upgrade(config, "head")

if __name__ == "__main__":
    migrate()
