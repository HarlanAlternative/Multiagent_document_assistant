from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def run_runtime_migrations(engine: Engine) -> None:
    inspector = inspect(engine)

    _ensure_column(engine, inspector, table_name="documents", column_name="project_id", column_type="VARCHAR(36)")
    _ensure_column(engine, inspector, table_name="conversations", column_name="project_id", column_type="VARCHAR(36)")
    _ensure_column(engine, inspector, table_name="conversations", column_name="summary", column_type="TEXT")


def _ensure_column(engine: Engine, inspector, *, table_name: str, column_name: str, column_type: str) -> None:
    if table_name not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return

    statement = text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
    with engine.begin() as connection:
        connection.execute(statement)
