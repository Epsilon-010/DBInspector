from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.models import ColumnInfo, SchemaSnapshot, TableInfo

_INTROSPECTION_SQL = text(
    """
    SELECT
        table_schema,
        table_name,
        column_name,
        data_type,
        is_nullable
    FROM information_schema.columns
    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
    ORDER BY table_schema, table_name, ordinal_position
    """
)


class PostgresIntrospector:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def snapshot(self) -> SchemaSnapshot:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_INTROSPECTION_SQL)).all()

        grouped: dict[tuple[str, str], list[ColumnInfo]] = {}
        for schema_name, table_name, column_name, data_type, is_nullable in rows:
            grouped.setdefault((schema_name, table_name), []).append(
                ColumnInfo(
                    name=column_name,
                    data_type=data_type,
                    nullable=(is_nullable == "YES"),
                )
            )

        tables = tuple(
            TableInfo(
                schema_name=schema_name,
                name=table_name,
                columns=tuple(cols),
            )
            for (schema_name, table_name), cols in grouped.items()
        )
        return SchemaSnapshot(tables=tables)
