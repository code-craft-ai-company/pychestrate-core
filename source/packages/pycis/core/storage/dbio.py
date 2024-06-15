"""
.. module:: dbio
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Contains helper functions for working with specific databases

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2024, Myron W Walker"
__credits__ = []
__version__ = "1.0.0"


from typing import Dict


import contextlib
import logging
import traceback

from sqlalchemy.engine.base import Engine as SqlEngine

from mojo.errors.exceptions import ConfigurationError

from pycis.core.storage.orm import ModelBase

from pycis.core.storage.dbconnection import DatabaseConnectionFactory, create_database_connection_factory


logger = logging.getLogger()


def database_exists(conn_factory: DatabaseConnectionFactory, dbname: str) -> bool:
    """
        Checks to see if the specified database exists.
    """
    engine = conn_factory.create_engine(dbname="postgres", echo=True)
    result = engine.execute("SELECT 1 AS result FROM pg_database WHERE datname='%s'" % dbname)

    exists = result.rowcount > 0

    return exists


def database_create(conn_factory: DatabaseConnectionFactory, dbname):
    """
        Creates the specified database.
    """
    engine = conn_factory.create_engine(dbname="postgres", echo=True)

    conn = engine.connect()
    try:
        conn.connection.set_isolation_level(0)
        result = conn.execute("CREATE DATABASE %s" % dbname)
    except Exception as xcpt:
        xmsg = traceback.format_exc()
        logger.error(xmsg)
        raise
    finally:
        conn.close()

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
    ModelBase.metadata.create_all(engine, checkfirst=True)

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
                        for table in reversed(ModelBase.metadata.sorted_tables))))
            trans.commit()

    return