import ccai.testbase as testbase

from ccai.errors.exceptions import SkipError

try:
    from ccai.credentials.credentialmanager import CredentialManager
    from ccai.dataprofiles.databasebasicsocketprofile import DatabaseBasicSocketProfile
    from ccai.pychestrate.core.storage.dbconnection import create_database_connection_factory
except Exception:  # pragma: no cover
    CredentialManager = None
    DatabaseBasicSocketProfile = None
    create_database_connection_factory = None


def test_create_database_connection_factory():
    if create_database_connection_factory is None:
        reason = "create_database_connection_factory not available"
        skip_exc = SkipError(reason)
        skip_exc.reason = reason
        skip_exc.bug = None
        raise skip_exc

    credential_identifier = "test-basic-credential"

    credential_info = {
        "credentials": [
            {
                "identifier": credential_identifier,
                "category": "basic",
                "username": "testuser",
                "password": "testpassword",
            }
        ]
    }

    cred_manager = CredentialManager()
    cred_manager.load_credentials(credential_info=credential_info)

    dbprofile = DatabaseBasicSocketProfile(
        "test-basic-socket-profile",
        category="basic-socket",
        dbtype="postgresql",
        dbname="testdb",
        socket="/tmp/test-db.socket",
        credential=credential_identifier,
    )

    factory = create_database_connection_factory(dbprofile=dbprofile, cred_manager=cred_manager)

    testbase.assert_not_equal(factory, None)

    return


if __name__ == "__main__":
    from ccai.testbase.entrypoints import generic_test_entrypoint

    generic_test_entrypoint()
