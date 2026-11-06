"""Safety checks for the integration test database target.

Everything here is pure (no network, no application imports) so it can be
unit tested without PostgreSQL. The integration fixtures call these checks
before any connection is used for DDL, and fail closed on any doubt.
"""

import re
import uuid

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

# The test database name must be an explicit, dedicated name ending in "_test".
# A plain substring check ("contains test") is deliberately not accepted.
TEST_DATABASE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*_test$")

# Only connection options that cannot redirect the connection to another
# database/host are allowed in the URL query string. Options such as
# "dbname", "host", "port", "service" or "options" are rejected because they
# could silently override the target encoded in the URL.
ALLOWED_QUERY_PARAMETERS = frozenset(
    {
        "sslmode",
        "sslrootcert",
        "sslcert",
        "sslkey",
        "connect_timeout",
        "application_name",
    }
)

TEST_SCHEMA_PATTERN = re.compile(r"^pytest_[0-9a-f]{12}$")


class UnsafeTestDatabaseError(RuntimeError):
    """The configured test database target cannot be proven safe."""


class MissingTestDatabaseError(UnsafeTestDatabaseError):
    """TEST_DATABASE_URL is not configured."""


def _parse_url(raw_url: str, variable_name: str) -> URL:
    try:
        return make_url(raw_url)
    except (ArgumentError, ValueError) as error:
        raise UnsafeTestDatabaseError(
            f"{variable_name} is malformed and cannot be parsed."
        ) from error


def validate_test_database_url(
    test_database_url: str | None,
    application_database_url: str | None,
) -> URL:
    """Return the parsed test URL, or raise if it is not provably safe."""

    if test_database_url is None or not test_database_url.strip():
        raise MissingTestDatabaseError(
            "TEST_DATABASE_URL is not configured; integration tests require "
            "an explicitly configured, dedicated test database."
        )

    if application_database_url is None or not application_database_url.strip():
        raise UnsafeTestDatabaseError(
            "DATABASE_URL is not configured, so the test database cannot be "
            "verified to differ from the application database."
        )

    test_url = _parse_url(test_database_url.strip(), "TEST_DATABASE_URL")
    application_url = _parse_url(
        application_database_url.strip(),
        "DATABASE_URL",
    )

    if test_url.get_backend_name() != "postgresql":
        raise UnsafeTestDatabaseError(
            "TEST_DATABASE_URL must point to a PostgreSQL database."
        )

    if not test_url.host:
        raise UnsafeTestDatabaseError(
            "TEST_DATABASE_URL must specify an explicit host."
        )

    unexpected_parameters = set(test_url.query) - ALLOWED_QUERY_PARAMETERS
    if unexpected_parameters:
        raise UnsafeTestDatabaseError(
            "TEST_DATABASE_URL contains connection parameters that are not "
            f"allowed: {', '.join(sorted(unexpected_parameters))}."
        )

    test_database_name = test_url.database
    if not test_database_name:
        raise UnsafeTestDatabaseError(
            "TEST_DATABASE_URL must specify an explicit database name."
        )

    if not TEST_DATABASE_NAME_PATTERN.fullmatch(test_database_name):
        raise UnsafeTestDatabaseError(
            "TEST_DATABASE_URL database name must be a dedicated test "
            "database name in lowercase ending with '_test' "
            "(for example 'music_metadata_test')."
        )

    application_database_name = application_url.database
    if not application_database_name:
        raise UnsafeTestDatabaseError(
            "DATABASE_URL has no explicit database name, so the test "
            "database cannot be verified to differ from it."
        )

    # Compare names regardless of host/port: host aliases (localhost,
    # 127.0.0.1, container names, port forwards) can reach the same server,
    # so an identical database name is always rejected.
    if test_database_name.lower() == application_database_name.lower():
        raise UnsafeTestDatabaseError(
            "TEST_DATABASE_URL must not point to the application database "
            "configured in DATABASE_URL."
        )

    return test_url


def verify_connected_database(
    connected_database_name: str | None,
    expected_test_url: URL,
) -> None:
    """Confirm the live connection is really the validated test database."""

    if connected_database_name != expected_test_url.database:
        raise UnsafeTestDatabaseError(
            "Connected database does not match the validated "
            "TEST_DATABASE_URL database name; refusing to run DDL."
        )

    if not TEST_DATABASE_NAME_PATTERN.fullmatch(connected_database_name or ""):
        raise UnsafeTestDatabaseError(
            "Connected database is not a dedicated test database; "
            "refusing to run DDL."
        )


def generate_test_schema_name() -> str:
    """Return a unique, disposable schema name for one test session."""

    return f"pytest_{uuid.uuid4().hex[:12]}"


def validate_test_schema_name(schema_name: str) -> str:
    if not TEST_SCHEMA_PATTERN.fullmatch(schema_name):
        raise UnsafeTestDatabaseError(
            f"Refusing to use unexpected test schema name: {schema_name!r}."
        )

    return schema_name
