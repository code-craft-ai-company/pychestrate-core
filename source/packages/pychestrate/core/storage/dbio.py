"""
.. module:: dbio
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Contains helper functions for working with specific databases

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Automation Mojo LLC"
__credits__ = []
__version__ = "1.0.0"


from typing import Dict, Optional


import contextlib
import logging
import traceback

from sqlalchemy.engine.base import Engine as SqlEngine
from sqlalchemy.sql.schema import MetaData

from sqlalchemy_utils import database_exists as sqlutils_database_exists
from sqlalchemy_utils import create_database as sqlutils_create_database

from automojo.errors.exceptions import ConfigurationError

from pychestrate.core.storage.orm import PychestrateModelBase

from pychestrate.core.storage.dbconnection import DatabaseConnectionFactory, create_database_connection_factory


logger = logging.getLogger()


def database_exists(conn_factory: DatabaseConnectionFactory, dbname: Optional[str]=None) -> bool:
    """
        Checks to see if the specified database exists.
    """
    conn_str = conn_factory.format_connection_string(dbname=dbname)

    exists = sqlutils_database_exists(conn_str)

    return exists


def database_create(conn_factory: DatabaseConnectionFactory, dbname: Optional[str]=None, dbmetadata: Optional[MetaData]=None):
    """ 
        Creates the specified database.
    """

    conn_str = conn_factory.format_connection_string(dbname=dbname)

    sqlutils_create_database(conn_str)

    if dbmetadata is not None:
        engine = conn_factory.create_engine(dbname=dbname)
        dbmetadata.create_all(engine)

    return


def create_pycis_database(db_profile: Dict[str, str]):
    """
        Creates the 'pycis' database.
    """
    dbname = "pycis"
    conn_factory = create_database_connection_factory(db_profile)
    if conn_factory is None:
        db_profile_name = db_profile["name"]
        errmsg = "'create_pycis_database' could not get a connection factory for profile={}".format(
            db_profile_name
        )
        raise ConfigurationError(errmsg)

    if not database_exists(conn_factory, dbname):
        database_create(conn_factory, dbname)

    engine = conn_factory.create_engine(dbname=dbname, echo=True)

    # TODO: Solidify the data model and the metadata base used
    # to create the database
    PychestrateModelBase.metadata.create_all(engine, checkfirst=True)

    return


def open_pycis_database(db_profile: Dict[str, str]) -> SqlEngine:
    """
        Opens the 'pycis' postgresql database.
    """
    dbname = 'pycis'

    conn_factory = create_database_connection_factory(db_profile)
    if conn_factory is None:
        db_profile_name = db_profile["name"]
        errmsg = "'open_pycis_database' could not get a connection factory for profile={}".format(
            db_profile_name
        )
        raise ConfigurationError(errmsg)

    engine = conn_factory.create_engine(dbname=dbname, echo=True)

    return engine


def reset_pycis_database(db_profile: Dict[str, str]):
    """
        Reset the 'pycis' database.
    """
    dbname = "pycis"
    conn_factory = create_database_connection_factory(db_profile)
    if conn_factory is None:
        db_profile_name = db_profile["name"]
        errmsg = "'reset_pycis_database' could not get a connection factory for profile={}".format(
            db_profile_name
        )
        raise ConfigurationError(errmsg)

    if database_exists(conn_factory, dbname):
    
        engine = conn_factory.create_engine(dbname=dbname, echo=True)

        with contextlib.closing(engine.connect()) as con:
            trans = con.begin()
            con.execute('TRUNCATE {} RESTART IDENTITY;'.format(
                ','.join(table.name 
                        for table in reversed(PychestrateModelBase.metadata.sorted_tables))))
            trans.commit()

    return