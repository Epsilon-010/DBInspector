from __future__ import annotations

import pytest

from app.adapters.sql.sqlglot_validator import SqlglotValidator
from app.domain.errors import UnsafeQueryError
from app.domain.models import SQLQuery


@pytest.fixture
def validator() -> SqlglotValidator:
    return SqlglotValidator()


class TestAccepts:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT 1",
            "SELECT id, name FROM products WHERE active = true LIMIT 10",
            "SELECT p.id, c.name FROM products p JOIN categories c ON c.id = p.category_id",
            "WITH top_sellers AS (SELECT id FROM products LIMIT 5) SELECT * FROM top_sellers",
            "SELECT '2024-01-01'::date AS d",
            "SELECT id FROM products UNION SELECT id FROM archived_products",
        ],
    )
    def test_accepts_safe_select_variants(self, validator: SqlglotValidator, sql: str) -> None:
        validator.validate(SQLQuery(sql=sql))


class TestRejects:
    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO products (id) VALUES (1)",
            "UPDATE products SET name = 'x'",
            "DELETE FROM products",
            "DROP TABLE products",
            "TRUNCATE products",
            "ALTER TABLE products ADD COLUMN x int",
            "CREATE TABLE foo (id int)",
            "GRANT ALL ON products TO public",
            "REVOKE ALL ON products FROM public",
        ],
    )
    def test_rejects_write_or_ddl(self, validator: SqlglotValidator, sql: str) -> None:
        with pytest.raises(UnsafeQueryError):
            validator.validate(SQLQuery(sql=sql))

    def test_rejects_multi_statement(self, validator: SqlglotValidator) -> None:
        with pytest.raises(UnsafeQueryError, match="una sentencia"):
            validator.validate(SQLQuery(sql="SELECT 1; SELECT 2;"))

    def test_rejects_unparseable(self, validator: SqlglotValidator) -> None:
        with pytest.raises(UnsafeQueryError, match="no parseable"):
            validator.validate(SQLQuery(sql="THIS IS NOT SQL @@@"))
