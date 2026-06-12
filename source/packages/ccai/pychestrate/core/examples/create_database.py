
__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []
__version__ = "1.0.0"

from ccai.foundation.runtime.activation import activate_runtime, ActivationProfile

from ccai.foundation.configuration.configurationmaps import resolve_configuration_maps
from ccai.foundation.configuration.initialize import establish_configuration_settings
from ccai.foundation.configuration.configurationvariables import resolve_configuration_variables


from ccai.credentials.wellknown import CredentialManagerSingleton

from ccai.dataprofiles.wellknown import DataProfileManagerSingleton


from ccai.pychestrate.core.storage.dbconnection import create_database_connection_factory
from ccai.pychestrate.core.storage.dbio import database_exists, database_create
from ccai.pychestrate.core.storage.orm import PychestrateModelBase


def create_database_main():

    establish_configuration_settings(name="pychestrate", home_dir="~/pychestrate")

    resolve_configuration_variables()

    activate_runtime(profile=ActivationProfile.Command)

    resolve_configuration_maps(use_credentials=True, use_landscape=True)

    profile_manager = DataProfileManagerSingleton()
    dbprofile = profile_manager.lookup_profile("software-pipeline-admin")

    cred_manager = CredentialManagerSingleton()

    dbfactory = create_database_connection_factory(dbprofile=dbprofile, cred_manager=cred_manager)

    dbname = "pipeline"

    if not database_exists(dbfactory, dbname):
        database_create(dbfactory, dbname=dbname, dbmetadata=PychestrateModelBase.metadata)

    return


if __name__ == "__main__":

    create_database_main()

