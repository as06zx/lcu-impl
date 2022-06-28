import re

from time import localtime, time
from dependency_injector.wiring import Provide, inject
from .containers import Container
from .services import ChatService, ConnectionRepository, LobbyService, SummonerService, UserDBService


USER_NAME = 0
LEVEL = 1
POINT = 2
@inject
def launch(
    conn: ConnectionRepository = Provide[Container.conn_repository],
    userdb_service: UserDBService = Provide[Container.userdb_service],
    chat_service: ChatService = Provide[Container.chat_service],
    lobby_service: LobbyService = Provide[Container.lobby_service],
    summoner_service: SummonerService = Provide[Container.summoner_service],
) -> None:

    async def cmdHelp(param):
        assert param is not None

        helpIndex = param[0]
        if helpIndex == "" or helpIndex == "1":
            await chat_service.sendMessage(text = "\n".join([
                '[help 1/2]',
                '/hi: ...',
                '/time: ...',
                '/membercount: ...'
            ]))
        elif helpIndex == "2":
            await chat_service.sendMessage(text = "\n".join([
                '[help 2/2]', 
                '/닉검색 닉네임: 닉네임이 사용중인지 검색합니다',
                '/생성: 닉네임을 등록합니다',
                '/정보 닉네임: 정보를 확인합니다',
                '/기부 닉네임 금액: 포인트를 기부합니다'
            ]))

    async def cmdHi(_):
        user = lobby_service.memberList[chat_service.lastMessage["fromSummonerId"]]
        await chat_service.sendMessage(text = "\n".join([
            f"{user} hi!"
        ]))
        
    async def cmdTime(_):
        tm = localtime(time())
        await chat_service.sendMessage(text = f"{tm.tm_year}--{tm.tm_mon}--{tm.tm_mday} | {tm.tm_hour}:{tm.tm_min}")

    async def cmdMemCount(_):
        membercount = await lobby_service.getMemberCount()
        await chat_service.sendMessage(text = f"{membercount} 명")
    async def cmdFindName(param):
        assert param is not None

        name = param[0]
        if not await summoner_service.canUseUserName(name):
            await chat_service.sendMessage(text = "해당 닉네임은 사용중입니다.")
        else:
            await chat_service.sendMessage(text = "해당 닉네임은 사용중이 아닙니다")

    async def cmdCreate(_):
        lastMessage = conn.event.data
        userid = chat_service.lastMessage["fromSummonerId"]
        username = lobby_service.memberList[userid]

        userDB = await userdb_service.getUser(username)
        
        if userDB:
            await chat_service.sendMessage(text = "이미 생성한 닉네임입니다")
            return 
        await userdb_service.addUser(username, 1, 1000)
        await chat_service.sendMessage(text = "생성 완료")

    async def cmdInfo(param):
        lastMessage = conn.event.data
        userid = lastMessage["fromSummonerId"]
        username = lobby_service.memberList[userid]
        targetName = param[0]
        outMsg = ""

        targetDB = await userdb_service.getUser(targetName)
        if not targetDB:
            await chat_service.sendMessage(text = "등록된 닉네임이 아닙니다")
            return

        level = targetDB[LEVEL]
        point = targetDB[POINT]

        outMsg = "\n".join([
            f"{targetName}'s Info",
            f"Level -> {level}",
            f"Point -> {point}"
        ])
        await chat_service.sendMessage(text = outMsg)

    async def cmdGive(param):
        assert len(param) == 2

        lastMessage = conn.event.data
        userid = lastMessage["fromSummonerId"]
        username = lobby_service.memberList[userid]
        targetName = param[0]
        amount = int(param[1])

        targetDB = await userdb_service.getUser(targetName)
        userDB = await userdb_service.getUser(username)

        if username == targetName:
            await chat_service.sendMessage(text = "자신에게 보낼수 없습니다")
            return 
        
        if amount > userDB[POINT]:
            await chat_service.sendMessage(text = "보유중인 포인트보다 많습니다")
            return

        await userdb_service.editUser(username, "Point", userDB[POINT] - amount)
        await userdb_service.editUser(targetName, "Point", targetDB[POINT] + amount)
        await chat_service.sendMessage(text = f"{username} 포인트 기부 ({amount}) -> {targetName}")


    commands : dict = dict()
    def register_comamnd():
        commands["help"] = cmdHelp
        commands["hi"] = cmdHi
        commands["time"] = cmdTime
        commands["membercount"] = cmdMemCount
        commands["닉검색"] = cmdFindName
        commands["생성"] = cmdCreate
        commands["정보"] = cmdInfo
        commands["기부"] = cmdGive

    @conn.connector.ready
    async def connect(connection):
        print("connected!")
        conn.connection = connection
        await summoner_service.start()
        await chat_service.start()
        await lobby_service.start()
        await userdb_service.start()
        register_comamnd()
        await chat_service.sendMessage(text = "type /help for a list of commands")


    @conn.connector.ws.register('/lol-chat/v1/conversations/', event_types=('CREATE',))
    async def onChatChanged(connection, event):
        conn.connection = connection
        conn.event = event
        chat_service.lastMessage = event.data
        if "body" not in chat_service.lastMessage: return
        
        body, type = chat_service.lastMessage["body"], chat_service.lastMessage["type"]
        print(f'>> {body}')

        if type != "groupchat":
            print('type is not groupchat')
            return


        userid = chat_service.lastMessage["fromSummonerId"]
        username =  lobby_service.memberList[userid]
        userDB = await userdb_service.getUser(username)
        if userDB:
            await userdb_service.editUser(username, "Point", userDB[POINT] + 1)
        
        if body[0] == "/":
            command = (body[1:]).split(" ", 1)[0]
            parameters = body[len(command) + 1 : len(body)].split()
            if len(parameters) == 0: parameters = [""]
            if command in commands:
                await commands[command](parameters)

    @conn.connector.close
    async def disconnect(connection):
        await conn.connector.stop()

    conn.connector.start()


if __name__ == '__main__':
    container = Container()
    container.init_resources()
    container.wire(modules=[__name__])
    launch()