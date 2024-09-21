"""
.. module:: dbconnection
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Contains helper functions for working with specific databases

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2024, Myron W Walker"
__credits__ = []
__version__ = "1.0.0"

from typing import Dict


import logging
import os


from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine as SqlEngine


from mojo.errors.exceptions import ConfigurationError, NotOverloadedError

from mojo.credentials.basecredential import BaseCredential
from mojo.credentials.basiccredential import BasicCredential

from mojo.config.wellknown import CredentialManager


logger = logging.getLogger()


class DatabaseConnectionFactory:

    def __init__(self, profile_name: str, *, conntype: str, dbtype: str, credential: BaseCredential, dbname: str=None, **other):
        self._profile_name = profile_name
        self._conntype = conntype
        self._dbtype = dbtype
        self._credential = credential
        self._dbname = dbname
        return

    @property
    def conntype(self) -> str:
        return self._conntype
    
    @property
    def credential(self) -> BaseCredential:
        return self._credential
    
    @property
    def dbname(self) -> str:
        return self._dbname
    
    @property
    def dbtype(self) -> str:
        return self._dbtype
    
    @property
    def profile_name(self) -> str:
        return self._profile_name

    def create_engine(self, *, dbname=None, echo=True) -> SqlEngine:
        errmsg = "The 'create_engine' method must be overloaded by 'DatabaseConnectionFactory' derived types."
        raise NotOverloadedError(errmsg)


class BasicDatabaseConnectionFactory(DatabaseConnectionFactory):

    def __init__(self, profile_name: str, *, conntype: str, dbtype:str, credential: str, dbname: str=None):
        super().__init__(profile_name, conntype=conntype, dbtype=dbtype, credential=credential, dbname=dbname)
        return

    def create_engine(self, *, dbname=None, echo=True) -> SqlEngine:
        # TODO: Implement pipe based DB connection engine creation
        return


class BasicTcpDatabaseConnectionFactory(DatabaseConnectionFactory):

    def __init__(self, profile_name: str, *, conntype: str, dbtype:str, host: str, port: int, credential: BaseCredential, dbname: str=None):
        self.profile_name = profile_name
        self.conntype = conntype
        self.dbtype = dbtype
        self.host = host
        self.port = port
        self.credential = credential
        self.dbname = dbname
        return

    def create_engine(self, *, dbname=None, echo=True) -> SqlEngine:

        # If the database type we are creating an engine for is postgresql, make sure
        # we can import all of the postgresql dependencies.
        if self.dbtype == 'postgresql':
            try:
                import psycopg2
            except ImportError:
                errmsg_lines = [
                    "In order to create a postgresql database engine, you must install the following dependencies.",
                    "DEPENDENCIES",
                    "    psycopg2"
                ]
                errmsg = os.linesep.join(errmsg_lines)
                raise ConfigurationError(errmsg)

        if dbname is None and self.dbname is not None:
            dbname = self.dbname

        if dbname is None:
            warnmsg = "BasicTcpDatabaseConnectionFactory.create_engine: dbname was None."
            logger.warn(warnmsg)

        credmgr = CredentialManager()

        cred = credmgr.credentials[self.credential]
        if isinstance(cred, BasicCredential):
            connstr = '%s+psycopg2://%s:%s@%s:%d/%s' % (
                self.dbtype, cred.username, cred.password, self.host, self.port, dbname)
            dbengine = create_engine(connstr, echo=echo)

        return dbengine



DATABASE_CONNECTION_FACTORIES = {}


def create_database_connection_factory(conn_profile: Dict[str, str]) -> DatabaseConnectionFactory:

    global DATABASE_CONNECTION_FACTORIES

    conn_factory = None

    profile_name = conn_profile["name"]

    if profile_name in DATABASE_CONNECTION_FACTORIES:
        conn_factory = DATABASE_CONNECTION_FACTORIES[conn_profile]
    
    else:

        if "conntype" in conn_profile:
            conntype = conn_profile["conntype"].lower()
            if conntype == "basic":
                conn_factory = BasicDatabaseConnectionFactory(profile_name, **conn_profile)
            elif conntype == "basic-tcp":
                conn_factory = BasicTcpDatabaseConnectionFactory(profile_name, **conn_profile)
            else:
                errmsg = "Unknown database connection type. connection={} conntype={}".format(
                    conn_profile, conntype)
                raise ConfigurationError(errmsg)

            DATABASE_CONNECTION_FACTORIES[conn_profile] = conn_factory
        else:
            errmsg = "Database connection entries must have a 'conntype' entry. connection={}".format(
                conn_profile
            )
            raise ConfigurationError(errmsg)
    

    return conn_factory
