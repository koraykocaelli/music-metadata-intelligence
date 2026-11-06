"""Fixtures for PostgreSQL-backed integration tests.

Safety model (fail closed):
1. TEST_DATABASE_URL is validated before any connection is opened
   (see tests/integration/db_safety.py). Missing -> tests are skipped;
   malformed or unsafe -> tests error out. No DDL runs in either case.
2. After connecting, current_database() is checked against the validated name.
3. Tables are created inside a uniquely named, disposable schema
   (pytest_<random>) created by this session. Teardown drops only that
   schema; existing tables in the test database are never dropped.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from tests.integration.db_safety import (
    MissingTestDatabaseError,
    UnsafeTestDatabaseError,
    generate_test_schema_name,
    validate_test_database_url,
    validate_test_schema_name,
    verify_connected_database,
)

INTEGRATION_DIR = Path(__file__).parent.resolve()


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    # Mark every test in tests/integration so it can be (de)selected with
    # `-m integration` / `-m "not integration"`. Runs before deselection.
    for item in items:
        if INTEGRATION_DIR in Path(str(item.path)).resolve().parents:
            item.add_marker(pytest.mark.integration)


def _load_database_urls() -> tuple[str | None, str | None]:
    try:
        from app.core.config import settings
    except Exception as error:  # fail closed on any configuration problem
        pytest.fail(
            "Could not load application settings, so the test database "
            f"target cannot be verified: {type(error).__name__}",
            pytrace=False,
        )

    return settings.test_database_url, settings.database_url


def _connected_database_name(connection) -> str | None:
    return connection.execute(text("SELECT current_database()")).scalar_one()


@pytest.fixture(scope="session", autouse=True)
def prepare_test_database():
    test_database_url, application_database_url = _load_database_urls()

    try:
        validated_url = validate_test_database_url(
            test_database_url,
            application_database_url,
        )
    except MissingTestDatabaseError as error:
        pytest.skip(str(error))
    except UnsafeTestDatabaseError as error:
        pytest.fail(str(error), pytrace=False)

    schema_name = validate_test_schema_name(generate_test_schema_name())

    admin_engine = create_engine(validated_url, poolclass=NullPool)
    schema_created = False
    test_engine: Engine | None = None

    try:
        try:
            with admin_engine.connect() as connection:
                verify_connected_database(
                    _connected_database_name(connection),
                    validated_url,
                )
                quoted_schema = connection.dialect.identifier_preparer.quote(
                    schema_name
                )
                # No IF NOT EXISTS: fails if the name is somehow already used.
                connection.execute(text(f"CREATE SCHEMA {quoted_schema}"))
                connection.commit()
                schema_created = True
        except UnsafeTestDatabaseError as error:
            pytest.fail(str(error), pytrace=False)
        except SQLAlchemyError as error:
            pytest.fail(
                "Could not prepare the test database (is PostgreSQL running "
                f"and TEST_DATABASE_URL correct?): {type(error).__name__}",
                pytrace=False,
            )

        test_engine = create_engine(
            validated_url,
            pool_pre_ping=True,
            # Keep "public" on the path so extensions such as pg_trgm resolve.
            connect_args={"options": f"-c search_path={schema_name},public"},
        )

        with test_engine.connect() as connection:
            verify_connected_database(
                _connected_database_name(connection),
                validated_url,
            )
            current_schema = connection.execute(
                text("SELECT current_schema()")
            ).scalar_one()
            if current_schema != schema_name:
                pytest.fail(
                    "Test engine is not bound to the disposable test schema; "
                    "refusing to run DDL.",
                    pytrace=False,
                )

            from app.db.base import Base
            from app.models.track import Track  # noqa: F401  (registers model)

            Base.metadata.create_all(bind=connection)
            connection.commit()

        yield test_engine
    finally:
        if test_engine is not None:
            test_engine.dispose()

        if schema_created:
            with admin_engine.connect() as connection:
                verify_connected_database(
                    _connected_database_name(connection),
                    validated_url,
                )
                quoted_schema = connection.dialect.identifier_preparer.quote(
                    validate_test_schema_name(schema_name)
                )
                # Drops only the schema created by this session.
                connection.execute(text(f"DROP SCHEMA {quoted_schema} CASCADE"))
                connection.commit()

        admin_engine.dispose()


@pytest.fixture
def db_session(prepare_test_database):
    connection = prepare_test_database.connect()
    transaction = connection.begin()

    # create_savepoint: application commit()/rollback() act on a SAVEPOINT,
    # so a rolled-back IntegrityError cannot end the per-test transaction.
    session = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
        join_transaction_mode="create_savepoint",
    )()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
