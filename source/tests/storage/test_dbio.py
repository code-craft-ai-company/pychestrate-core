
import unittest

from pycis.core.storage.dbconnection import create_database_connection_factory

class DbIOTests(unittest.TestCase):

    def test_crate_database_connection_factory():

        profile = {
            "name": "blah",
            "conntype": "basic"
        }

        return