
from automojo.foundation.runtime.activation import activate_runtime, ActivationProfile

from automojo.foundation.configuration.configurationmaps import resolve_configuration_maps
from automojo.foundation.configuration.initialize import establish_configuration_settings
from automojo.foundation.configuration.configurationvariables import resolve_configuration_variables

from automojo.dataprofiles.wellknown import DataProfileManagerSingleton

from pycis.core.storage.dbconnection import create_database_connection_factory
from pycis.core.storage.dbio import database_exists, database_create
from pycis.core.storage.orm import ModelBase

def create_database_main():

    establish_configuration_settings()

    resolve_configuration_variables()

    activate_runtime(profile=ActivationProfile.Command)

    resolve_configuration_maps(use_credentials=True, use_landscape=True)

    profile_manager = DataProfileManagerSingleton()
    dbprofile = profile_manager.lookup_profile("software-pipeline-admin")

    dbfactory = create_database_connection_factory(dbprofile)

    dbname = "pipeline"

    if not database_exists(dbfactory, dbname):
        database_create(dbfactory, dbname=dbname, dbmetadata=ModelBase.metadata)

    return


if __name__ == "__main__":

    create_database_main()
