from  lcu_driver.connection import Connection
from lcu_driver import Connector

import sqlite3
import logging

# service basis 
class BaseService:
    def __init__(self) -> None:
        # logger initialization
        self.logger = logging.getLogger(f'{__name__}.{self.__class__.__name__}')

    async def start(self) -> None:
        self.logger.info(f'{self.__class__.__name__} is started!')


# fucking mess classification
class ConnectionRepository(BaseService):
    _connector: Connector

    _lastConnection: Connection
    _connection : Connection
    
    _lastEvent: object
    _event: object

    def __init__(self) -> None:
        self._connector = Connector()
        super().__init__()
    
    async def start(self) -> None:
        self._connector.start()
        return await super().start()

# props
    def get_connector(self) -> Connector:
        return self._connector
    connector : Connector = property(get_connector)


    # Q. is self._connection is equivalent to self._connector.connection?
    #    then this props doesn't required ;D
    def get_connection(self) -> Connection:    
        return self._connection
    def set_connection(self, conn : Connection):
        self._lastConnection = self._connection
        self._connection = conn
    connection : Connection = property(get_connection, set_connection)


    def get_event(self) -> object:
        return self._event
    def set_event(self, ev : object):
        self._lastEvent = self._event
        self._event = ev
    event : object = property(get_event, set_event)




# simple crud-based userdb manipulation service
class UserDBService(BaseService):
    db : sqlite3.Connection

    def __init__(self, db : sqlite3.Connection) -> None:
        self.db = db
        super().__init__()

    async def start(self) -> None:
        cur = self.db.cursor()
        cur.execute("CREATE TABLE IF NOT EXIST USERS(UserName TEXT, Level INTEGER, Point INTEGER);")
        return await super().start()

    async def addUser(self, username: str, level: int, point: int) -> None: # addUserDB
        assert username and level and point is not None
        
        cur = self.db.cursor()
        cur.execute("INSERT INTO USERS VALUES(?, ?, ?);", (username, level, point))

    async def editUser(self, username: str , key: str, value) -> None: # editUserDB
        assert username and key and value is not None

        cur = self.db.cursor()
        cur.execute("UPDATE USERS SET :key = :value WHERE UserName = :username;", {"username" : username, "key" : key, "value" : value })
    
    async def getAllUsers(self):  # getUserDB        
        cur = self.db.cursor()
        cur.execute("SELECT * FROM USERS;")
        return cur.fetchall()
    
    async def getUser(self, username: str): # findUser
        assert username is not None 

        cur = self.db.cursor()
        cur.execute("SELECT * FROM USERS WHERE UserName = :username;", {"username" : username})
        return cur.fetchone()



# wrapper service of /lol-chat/ path
class ChatService(BaseService):
    conn: ConnectionRepository
    roomID: str
    roomData: dict
    lastMessage: str
    def __init__(self, conn: ConnectionRepository) -> None:
        self.conn = conn
        super().__init__()
    
    async def start(self) -> None:
        await self.updateRoomInfo()
        return await super().start()

    async def updateRoomInfo(self) -> None:
        conversations = await (await self.conn.connection.request('get', '/lol-chat/v1/conversations')).json()

        # find first customGame, and set that instance as roomData, roomID
        for conversation in conversations:
            if conversation['type'] == 'customGame':
                self.roomData = conversation
                self.roomID = self.roomData['id']
                break

    async def sendMessage(self, roomID = None, text = "") -> None:
        if roomID is None: roomID = self.roomID

        body = { "body" : "/나 " + text }
        await self.conn.connection.request(
            'post',
            f'/lol-chat/v1/conversations/{roomID}/messages'
            ,data = body
        )


# wrapper service of /lol-lobby/ path
class LobbyService(BaseService):
    conn: ConnectionRepository
    memberList: list

    def __init__(self, conn: ConnectionRepository) -> None:
        self.conn = conn
        super().__init__()

    async def start(self) -> None:
        await self.updateMemberList()
        return await super().start()

    async def updateMemberList(self):
        members = await (await self.conn.connection.request('get', '/lol-lobby/v2/lobby/members/')).json()
        for member in members:
            if member["summonerId"] not in self.memberList:
                id, name = member["summonerId"], member["summonerName"]
                self.memberList[id] = name
    
    async def getMemberCount(self):
        members = await (await self.conn.connection.request('get', '/lol-lobby/v2/lobby/members/')).json()
        return len(members)


# wrapper service of /lol-summoner/ path
class SummonerService(BaseService):
    conn : ConnectionRepository
    summonerID : str

    def __init__(self, conn: ConnectionRepository) -> None:
        self.conn = conn
        super().__init__()

    async def start(self) -> None:
        await self.updateSummonerInfo()
        return await super().start()

    async def updateSummonerInfo(self):
        summoner = await (await self.conn.connection.request('get', '/lol-summoner/v1/current-summoner')).json()
        self.summonerID = summoner["summonerId"]
    
    async def canUseUserName(self, name):
        return (await (await self.conn.connection.request('get', '/lol-summoner/v1/check-name-availability/' + name)).json())
