import pytest
from sqlalchemy.engine import make_url

from tests.integration.db_safety import (
    MissingTestDatabaseError,
    UnsafeTestDatabaseError,
    generate_test_schema_name,
    validate_test_database_url,
    validate_test_schema_name,
    verify_connected_database,
)

APP_URL = "postgresql+psycopg://user:secret@localhost:5432/music_metadata"
TEST_URL = "postgresql+psycopg://user:secret@localhost:5432/music_metadata_test"


def test_valid_test_database_url_is_accepted() -> None:
    url = validate_test_database_url(TEST_URL, APP_URL)

    assert url.database == "music_metadata_test"
    assert url.host == "localhost"


def test_allowed_query_parameters_are_accepted() -> None:
    url = validate_test_database_url(f"{TEST_URL}?sslmode=disable", APP_URL)

    assert url.database == "music_metadata_test"


@pytest.mark.parametrize("missing", [None, "", "   "])
def test_missing_test_database_url_is_rejected(missing) -> None:
    with pytest.raises(MissingTestDatabaseError):
        validate_test_database_url(missing, APP_URL)


@pytest.mark.parametrize("missing", [None, "", "   "])
def test_missing_application_database_url_is_rejected(missing) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        validate_test_database_url(TEST_URL, missing)


@pytest.mark.parametrize(
    "malformed",
    ["not a url", "://missing-driver", "postgresql+psycopg://user@host:notaport/x_test"],
)
def test_malformed_test_database_url_is_rejected(malformed) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        validate_test_database_url(malformed, APP_URL)


def test_malformed_application_database_url_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        validate_test_database_url(TEST_URL, "not a url")


def test_non_postgresql_backend_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="PostgreSQL"):
        validate_test_database_url("sqlite:///music_metadata_test", APP_URL)


def test_missing_host_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="host"):
        validate_test_database_url(
            "postgresql+psycopg://user:secret@/music_metadata_test",
            APP_URL,
        )


def test_missing_database_name_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="database name"):
        validate_test_database_url(
            "postgresql+psycopg://user:secret@localhost:5432",
            APP_URL,
        )


def test_same_database_as_application_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        validate_test_database_url(APP_URL, APP_URL)


@pytest.mark.parametrize(
    "database_name",
    [
        "music_metadata",  # the application database
        "postgres",
        "template1",
        "test_music_metadata",  # contains "test" but is not a *_test name
        "music_metadata_testing",
        "music_test_metadata",
        "testdb",
        "Music_Metadata_Test",  # uppercase / quoted identifiers not accepted
        "music-metadata_test",
    ],
)
def test_non_dedicated_test_database_names_are_rejected(database_name) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        validate_test_database_url(
            f"postgresql+psycopg://user:secret@localhost:5432/{database_name}",
            APP_URL,
        )


def test_application_database_with_same_name_on_other_host_is_rejected() -> None:
    # Host aliases can reach the same server, so equal names are never allowed.
    app_url = "postgresql+psycopg://user:secret@db.internal:5432/music_metadata_test"

    with pytest.raises(UnsafeTestDatabaseError, match="application database"):
        validate_test_database_url(TEST_URL, app_url)


def test_application_database_name_comparison_is_case_insensitive() -> None:
    app_url = "postgresql+psycopg://user:secret@localhost:5432/MUSIC_METADATA_TEST"

    with pytest.raises(UnsafeTestDatabaseError, match="application database"):
        validate_test_database_url(TEST_URL, app_url)


def test_application_database_without_name_is_rejected() -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="DATABASE_URL"):
        validate_test_database_url(
            TEST_URL,
            "postgresql+psycopg://user:secret@localhost:5432",
        )


@pytest.mark.parametrize(
    "query",
    [
        "dbname=music_metadata",
        "host=prod.example.com",
        "port=6543",
        "service=production",
        "options=-csearch_path%3Dpublic",
    ],
)
def test_target_overriding_query_parameters_are_rejected(query) -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="not allowed"):
        validate_test_database_url(f"{TEST_URL}?{query}", APP_URL)


def test_verify_connected_database_accepts_expected_database() -> None:
    verify_connected_database("music_metadata_test", make_url(TEST_URL))


@pytest.mark.parametrize("connected", ["music_metadata", "postgres", None, ""])
def test_verify_connected_database_rejects_unexpected_database(connected) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        verify_connected_database(connected, make_url(TEST_URL))


def test_generated_schema_names_are_unique_and_valid() -> None:
    first = generate_test_schema_name()
    second = generate_test_schema_name()

    assert first != second
    assert validate_test_schema_name(first) == first
    assert validate_test_schema_name(second) == second


@pytest.mark.parametrize(
    "schema_name",
    ["public", "pytest_", "pytest_XYZ", 'pytest_abc"; DROP SCHEMA public; --'],
)
def test_unexpected_schema_names_are_rejected(schema_name) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        validate_test_schema_name(schema_name)
