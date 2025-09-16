import automojo.testbase as testbase

from automojo.errors.exceptions import SkipError

try:
    from automojo.pychestrate.core.storage.dbconnection import create_database_connection_factory
except Exception:  # pragma: no cover
    create_database_connection_factory = None


def test_create_database_connection_factory():
    if create_database_connection_factory is None:
        reason = "create_database_connection_factory not available"
        skip_exc = SkipError(reason)
        skip_exc.reason = reason
        skip_exc.bug = None
        raise skip_exc

    profile = {
        "name": "blah",
        "conntype": "basic",
    }

    factory = create_database_connection_factory(profile)
    testbase.assert_not_equal(factory, None)

    return


if __name__ == "__main__":
    from automojo.testbase.entrypoints import generic_test_entrypoint

    generic_test_entrypoint()
