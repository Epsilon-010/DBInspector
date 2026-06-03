"""Canned offline adapters used when DEMO_MODE=true (no Anthropic, no Postgres)."""
from __future__ import annotations

import asyncio
import re
from typing import Any

from app.domain.models import (
    ColumnInfo,
    QueryResult,
    SchemaSnapshot,
    SQLQuery,
    TableInfo,
)

# Simulate API/DB roundtrips so the live-progress UI has time to render each step.
_GUARDRAIL_DELAY = 0.4
_SQL_GEN_DELAY = 1.0
_DB_DELAY = 0.4
_ANALYZER_DELAY = 0.8


_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "genre": ("género", "genero", "genre", "estilo"),
    "country": ("país", "pais", "country", "región", "region", "ciudad"),
    "timeline": ("mes", "año", "ano", "fecha", "tiempo", "evoluc", "trend", "mensual"),
    "tracks": ("canción", "cancion", "track", "tema"),
}


# Prompts in `app/application/prompts/*.py` wrap the user question in triple double-quotes.
# Extract that to avoid matching keywords that appear in the schema/SQL also included
# in the LLM prompt (e.g. table name `genre` would otherwise force the "genre" intent
# for every question).
_QUESTION_RE = re.compile(r'"""(.*?)"""', re.DOTALL)


def _detect_intent(prompt_text: str) -> str:
    match = _QUESTION_RE.search(prompt_text)
    target = match.group(1) if match else prompt_text
    lowered = target.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return intent
    return "artists"


_RESPONSES: dict[str, dict[str, Any]] = {
    "artists": {
        "sql": (
            "SELECT artist.name AS artist, COUNT(album.album_id) AS album_count\n"
            "FROM artist\n"
            "JOIN album ON album.artist_id = artist.artist_id\n"
            "GROUP BY artist.name\n"
            "ORDER BY album_count DESC\n"
            "LIMIT 5"
        ),
        "columns": ("artist", "album_count"),
        "rows": (
            ("Iron Maiden", 21),
            ("Led Zeppelin", 14),
            ("Deep Purple", 11),
            ("Metallica", 10),
            ("U2", 10),
        ),
        "analysis": {
            "summary": (
                "Iron Maiden lidera el catálogo con 21 álbumes, seguido por Led Zeppelin "
                "(14) y Deep Purple (11). Los cinco primeros artistas concentran el 35% "
                "del catálogo total. El género metal/rock domina la parte alta del ranking."
            ),
            "chart": {
                "type": "bar",
                "x": "artist",
                "y": "album_count",
                "series": None,
                "title": "Top 5 artistas por cantidad de álbumes",
            },
        },
    },
    "tracks": {
        "sql": (
            "SELECT track.name AS track,\n"
            "       ROUND(SUM(invoice_line.unit_price * invoice_line.quantity), 2) AS revenue\n"
            "FROM track\n"
            "JOIN invoice_line ON invoice_line.track_id = track.track_id\n"
            "GROUP BY track.name\n"
            "ORDER BY revenue DESC\n"
            "LIMIT 5"
        ),
        "columns": ("track", "revenue"),
        "rows": (
            ("The Trooper", 12.87),
            ("Stairway to Heaven", 11.88),
            ("Smoke on the Water", 10.89),
            ("One", 10.89),
            ("Hallowed Be Thy Name", 9.90),
        ),
        "analysis": {
            "summary": (
                "The Trooper de Iron Maiden encabeza la facturación con $12.87, seguida "
                "por Stairway to Heaven ($11.88). Los cinco temas más vendidos generan "
                "$56.43 — concentración alta en hits clásicos del rock."
            ),
            "chart": {
                "type": "bar",
                "x": "track",
                "y": "revenue",
                "series": None,
                "title": "Top 5 canciones por facturación",
            },
        },
    },
    "country": {
        "sql": (
            "SELECT billing_country AS country, ROUND(SUM(total), 2) AS sales\n"
            "FROM invoice\n"
            "GROUP BY billing_country\n"
            "ORDER BY sales DESC\n"
            "LIMIT 5"
        ),
        "columns": ("country", "sales"),
        "rows": (
            ("USA", 523.06),
            ("Canada", 303.96),
            ("France", 195.10),
            ("Brazil", 190.10),
            ("Germany", 156.48),
        ),
        "analysis": {
            "summary": (
                "Estados Unidos lidera las ventas con $523.06, casi el doble que Canadá "
                "($303.96). Los cinco primeros países concentran el 70% de la facturación "
                "total. Norteamérica + Europa Occidental son los mercados dominantes."
            ),
            "chart": {
                "type": "pie",
                "x": "country",
                "y": "sales",
                "series": None,
                "title": "Distribución de ventas por país",
            },
        },
    },
    "timeline": {
        "sql": (
            "SELECT TO_CHAR(invoice_date, 'YYYY-MM') AS month, ROUND(SUM(total), 2) AS sales\n"
            "FROM invoice\n"
            "WHERE invoice_date >= DATE '2024-01-01'\n"
            "GROUP BY month\n"
            "ORDER BY month"
        ),
        "columns": ("month", "sales"),
        "rows": (
            ("2024-01", 38.62),
            ("2024-02", 47.62),
            ("2024-03", 39.62),
            ("2024-04", 51.86),
            ("2024-05", 44.62),
            ("2024-06", 56.81),
            ("2024-07", 48.39),
            ("2024-08", 60.55),
            ("2024-09", 49.62),
            ("2024-10", 55.91),
            ("2024-11", 63.04),
            ("2024-12", 71.86),
        ),
        "analysis": {
            "summary": (
                "Las ventas mensuales muestran una tendencia ascendente clara: de $38.62 "
                "en enero a $71.86 en diciembre (+86%). El cuarto trimestre concentra la "
                "facturación más alta, sugiriendo estacionalidad navideña."
            ),
            "chart": {
                "type": "line",
                "x": "month",
                "y": "sales",
                "series": None,
                "title": "Evolución mensual de ventas 2024",
            },
        },
    },
    "genre": {
        "sql": (
            "SELECT genre.name AS genre, COUNT(track.track_id) AS track_count\n"
            "FROM genre\n"
            "JOIN track ON track.genre_id = genre.genre_id\n"
            "GROUP BY genre.name\n"
            "ORDER BY track_count DESC\n"
            "LIMIT 6"
        ),
        "columns": ("genre", "track_count"),
        "rows": (
            ("Rock", 1297),
            ("Latin", 579),
            ("Metal", 374),
            ("Alternative & Punk", 332),
            ("Jazz", 130),
            ("TV Shows", 93),
        ),
        "analysis": {
            "summary": (
                "Rock domina el catálogo con 1,297 tracks (44% del total mostrado). Latin "
                "ocupa el segundo lugar con 579, seguido por Metal (374). Los géneros "
                "tradicionales superan ampliamente a los nichos como TV Shows o Jazz."
            ),
            "chart": {
                "type": "pie",
                "x": "genre",
                "y": "track_count",
                "series": None,
                "title": "Distribución de tracks por género",
            },
        },
    },
}


class DemoLLMClient:
    """Detects intent from the question (or the SQL, for the analyzer call) and returns
    the matching canned response. Independent of any external service.
    """

    async def complete(
        self,
        *,
        system: str,  # noqa: ARG002
        user: str,
        max_tokens: int = 1024,  # noqa: ARG002
        temperature: float = 0.0,  # noqa: ARG002
    ) -> str:
        await asyncio.sleep(_SQL_GEN_DELAY)
        intent = _detect_intent(user)
        return _RESPONSES[intent]["sql"]

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 1024,  # noqa: ARG002
        temperature: float = 0.0,  # noqa: ARG002
    ) -> dict:
        if "guardrail" in system.lower():
            await asyncio.sleep(_GUARDRAIL_DELAY)
            return {"is_safe": True, "reason": "Pregunta de análisis de datos legítima (demo)."}
        await asyncio.sleep(_ANALYZER_DELAY)
        intent = _detect_intent(user)
        return _RESPONSES[intent]["analysis"]


class DemoIntrospector:
    """Returns a Chinook-shaped schema snapshot."""

    _SCHEMA = SchemaSnapshot(
        tables=(
            TableInfo(
                name="artist",
                schema_name="public",
                columns=(
                    ColumnInfo(name="artist_id", data_type="integer", nullable=False),
                    ColumnInfo(name="name", data_type="varchar(120)", nullable=True),
                ),
            ),
            TableInfo(
                name="album",
                schema_name="public",
                columns=(
                    ColumnInfo(name="album_id", data_type="integer", nullable=False),
                    ColumnInfo(name="title", data_type="varchar(160)", nullable=False),
                    ColumnInfo(name="artist_id", data_type="integer", nullable=False),
                ),
            ),
            TableInfo(
                name="track",
                schema_name="public",
                columns=(
                    ColumnInfo(name="track_id", data_type="integer", nullable=False),
                    ColumnInfo(name="name", data_type="varchar(200)", nullable=False),
                    ColumnInfo(name="album_id", data_type="integer", nullable=True),
                    ColumnInfo(name="genre_id", data_type="integer", nullable=True),
                    ColumnInfo(name="milliseconds", data_type="integer", nullable=False),
                    ColumnInfo(name="unit_price", data_type="numeric(10,2)", nullable=False),
                ),
            ),
            TableInfo(
                name="genre",
                schema_name="public",
                columns=(
                    ColumnInfo(name="genre_id", data_type="integer", nullable=False),
                    ColumnInfo(name="name", data_type="varchar(120)", nullable=True),
                ),
            ),
            TableInfo(
                name="invoice",
                schema_name="public",
                columns=(
                    ColumnInfo(name="invoice_id", data_type="integer", nullable=False),
                    ColumnInfo(name="customer_id", data_type="integer", nullable=False),
                    ColumnInfo(name="invoice_date", data_type="timestamp", nullable=False),
                    ColumnInfo(name="billing_country", data_type="varchar(40)", nullable=True),
                    ColumnInfo(name="total", data_type="numeric(10,2)", nullable=False),
                ),
            ),
            TableInfo(
                name="invoice_line",
                schema_name="public",
                columns=(
                    ColumnInfo(name="invoice_line_id", data_type="integer", nullable=False),
                    ColumnInfo(name="invoice_id", data_type="integer", nullable=False),
                    ColumnInfo(name="track_id", data_type="integer", nullable=False),
                    ColumnInfo(name="unit_price", data_type="numeric(10,2)", nullable=False),
                    ColumnInfo(name="quantity", data_type="integer", nullable=False),
                ),
            ),
        )
    )

    async def snapshot(self) -> SchemaSnapshot:
        return self._SCHEMA


class DemoDatabase:
    """Inspects the (canned) SQL to figure out which intent it serves, returns matching rows."""

    async def execute(
        self,
        query: SQLQuery,
        *,
        timeout_seconds: int,  # noqa: ARG002
        max_rows: int,  # noqa: ARG002
    ) -> QueryResult:
        await asyncio.sleep(_DB_DELAY)
        intent = _detect_intent_from_sql(query.sql)
        canned = _RESPONSES[intent]
        return QueryResult(
            columns=canned["columns"],
            rows=canned["rows"],
            row_count=len(canned["rows"]),
            truncated=False,
        )


def _detect_intent_from_sql(sql: str) -> str:
    """SQL-side intent detection. Cheap keyword match on table names produced by DemoLLM."""
    lowered = sql.lower()
    if "from genre" in lowered or "join genre" in lowered:
        return "genre"
    if "billing_country" in lowered:
        return "country"
    if "to_char(invoice_date" in lowered or "invoice_date" in lowered and "month" in lowered:
        return "timeline"
    if "from track" in lowered and "invoice_line" in lowered:
        return "tracks"
    return "artists"


class DemoSQLValidator:
    """Always accepts the demo SQL — the validator is exercised in tests against real SQL."""

    def validate(self, query: SQLQuery) -> None:  # noqa: ARG002
        return None
