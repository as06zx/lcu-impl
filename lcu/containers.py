import logging.config
import sqlite3
from lcu_driver import Connector
from dependency_injector import containers, providers
from . import services

class Container(containers.DeclarativeContainer):
    
    config = providers.Configuration(ini_files=["config.ini"])
    logging = providers.Resource(logging.config.fileConfig, fname="logging.ini")
    connector = Connector()

    db_repository = providers.Singleton(
        sqlite3.connect,
        config.database.db
    )

    conn_repository = providers.Singleton(
        services.ConnectionRepository,
    )
    userdb_service = providers.Factory(
        services.UserDBService,
        db = db_repository,
    )
    chat_service = providers.Factory(
        services.ChatService,
        conn = conn_repository
    )
    lobby_service = providers.Factory(
        services.LobbyService,
        conn = conn_repository
    )
    summoner_service = providers.Factory(
        services.SummonerService,
        conn = conn_repository
    )

