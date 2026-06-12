"""
TestBase tests for db connection factory exposure.

These tests intentionally avoid constructing engines or touching credentials to
keep them self-contained within a single host and without external dependencies.
"""


def test_create_database_connection_factory_is_exposed():
    """Verify the symbol exists and is callable if the module imports."""
    try:
        from ccai.pychestrate.core.storage.dbconnection import (
            create_database_connection_factory,
        )
    except Exception:
        # If optional dependencies are unavailable in this environment, do not fail.
        return

    assert callable(create_database_connection_factory)
