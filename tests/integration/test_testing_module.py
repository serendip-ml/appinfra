"""
Integration tests for the appinfra.db.pg.testing module.

Verifies that the pytest fixtures work correctly for schema isolation.
"""

import pytest
from sqlalchemy import Column, Integer, String, text
from sqlalchemy.orm import declarative_base


# Override the default fixtures to use our test config
@pytest.fixture(scope="session")
def pg_test_config(pg_config):
    """Use the existing pg_config from pg_integration fixtures."""
    return pg_config


@pytest.fixture(scope="session")
def pg_test_logger(pg_logger):
    """Use the existing pg_logger from pg_integration fixtures."""
    return pg_logger


# Now import the testing fixtures
pytest_plugins = ["appinfra.db.pg.testing"]


@pytest.mark.integration
class TestPgIsolatedFixture:
    """Test the pg_isolated fixture."""

    def test_pg_isolated_has_schema(self, pg_isolated):
        """Test that pg_isolated has a schema configured."""
        assert pg_isolated.schema is not None
        assert pg_isolated.schema.startswith("test_")

    def test_pg_isolated_can_execute_queries(self, pg_isolated):
        """Test that pg_isolated can execute queries."""
        with pg_isolated.session() as session:
            result = session.execute(text("SELECT 1 as value"))
            row = result.fetchone()
            assert row[0] == 1


@pytest.mark.integration
class TestPgSessionIsolatedFixture:
    """Test the pg_session_isolated fixture."""

    def test_session_executes_in_schema(self, pg_isolated, pg_session_isolated):
        """Test session executes queries in the correct schema."""
        # Create a test table
        pg_session_isolated.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_session_fixture (
                    id INT PRIMARY KEY,
                    value TEXT
                )
                """
            )
        )
        pg_session_isolated.commit()

        # Verify table is in the correct schema
        result = pg_session_isolated.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = :schema
                AND table_name = 'test_session_fixture'
                """
            ),
            {"schema": pg_isolated.schema},
        )
        assert result.scalar() == 1


@pytest.mark.integration
class TestMakeMigrateFixture:
    """Test the make_migrate_fixture factory."""

    def test_creates_tables_from_base(
        self, pg_test_config, pg_test_logger, pg_test_schema
    ):
        """Test that make_migrate_fixture creates tables in the schema."""
        from appinfra.db.pg import PG

        Base = declarative_base()

        class MigrateTestModel(Base):
            __tablename__ = "migrate_fixture_test"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        # Manually invoke what the fixture would do
        pg = PG(pg_test_logger, pg_test_config, schema=pg_test_schema)

        try:
            if pg._schema_mgr:
                pg._schema_mgr.reset_schema()
            pg.migrate(Base)

            # Verify table exists in correct schema
            with pg.engine.connect() as conn:
                result = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.tables
                        WHERE table_schema = :schema
                        AND table_name = 'migrate_fixture_test'
                        """
                    ),
                    {"schema": pg_test_schema},
                )
                assert result.scalar() == 1
        finally:
            if pg._schema_mgr:
                pg._schema_mgr.drop_schema(cascade=True)


@pytest.mark.integration
class TestPgCleanSchemaFixture:
    """Test the pg_clean_schema fixture."""

    def test_clean_schema_starts_fresh(self, pg_clean_schema, pg_isolated):
        """Test that pg_clean_schema provides a fresh schema."""
        # The schema should be empty (reset just happened)
        with pg_isolated.engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = :schema
                    """
                ),
                {"schema": pg_isolated.schema},
            )
            # Should have no tables in a freshly reset schema
            assert result.scalar() == 0
