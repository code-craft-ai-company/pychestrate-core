import unittest

try:
    from automojo.pychestrate.core.storage.dbconnection import create_database_connection_factory
except Exception:  # pragma: no cover
    create_database_connection_factory = None


class DbIOTests(unittest.TestCase):

    def test_create_database_connection_factory(self):
        if create_database_connection_factory is None:
            self.skipTest("create_database_connection_factory not available")

        profile = {
            "name": "blah",
            "conntype": "basic",
        }

        factory = create_database_connection_factory(profile)
        self.assertIsNotNone(factory)


if __name__ == "__main__":
    unittest.main()
