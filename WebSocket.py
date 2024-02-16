import asyncio
import json
import websockets
import gettext
from gptapi import GPTAPIConversation
# 语言设置
LANG = "zh_CN"
lang = gettext.translation("mcgpt","locale",languages=[LANG])
lang.install()
# 请修改此处"API_URL"和"API_KEY"
api_url = "API_URL" # API地址 #例：https://chat.openai.com/v1/chat/completions
api_key = "API_KEY"  # 硬编码api用于本地测试
model = "gpt-4" # gpt模型
system_prompt = _("Please maintain a positive and professional attitude at all times. Try to keep your answers to one paragraph and not too long, adding line breaks as appropriate") # 系统提示词


# 上下文（临时）
enable_history = False # 默认关闭

#WebSocket
ip = "localhost" # 如需配置服务器请修改ip
port = "8080" # 端口
wlo = "Connect to the WebSocket Server successfully\nServer IP: {ip}\nPort: {port}\nGPT Context: {enable_history}"
welcome_message = _(wlo).format(ip=ip,port=port,enable_history=enable_history)
#初始化conversation变量
conversation = None

async def gpt_main(player_prompt):
    global conversation, enable_history
    # 创建实例
    if conversation is None:
        conversation = GPTAPIConversation(api_key, api_url, model, system_prompt, enable_logging=True)
    # 发送提示到GPT并获取回复
    gpt_message = await conversation.call_gpt_and_send(player_prompt)
    if gpt_message is None:
        gpt_message = _("Error: GPT response is None")
    print(_("gpt message: ") + gpt_message)

    if not enable_history:
        await conversation.close()
        conversation = None

    return gpt_message

async def send_data(websocket, message):
    """向客户端发送数据"""
    await websocket.send(json.dumps(message))

async def subscribe_events(websocket):
    """订阅事件"""
    message = {
        "body": {
            "eventName": "PlayerMessage"
        },
        "header": {
            "requestId": "5511ca37-07ed-4654-93a0-d1784c4b3f8f",  # uuid
            "messagePurpose": "subscribe",
            "version": 1,
            "EventName": "commandRequest"
        }
    }
    await send_data(websocket, message)

async def send_game_message(websocket, message):
    """向游戏内发送聊天信息"""
    say_message = message.replace('"', '\\"').replace(':', '：').replace('%', '\\%') # 转义特殊字符，避免报错
    print(say_message)
    game_message = {
        "body": {
            "origin": {
                "type": "say"
            },
            "commandLine": f'tellraw @a {{"rawtext":[{{"text":"§a{say_message}"}}]}}',
            "version": 1
        },
        "header": {
            "requestId": "5511ca37-07ed-4654-93a0-d1784c4b3f8f",  # uuid
            "messagePurpose": "commandRequest",
            "version": 1,
            "EventName": "commandRequest"
        }
    }
    await send_data(websocket, game_message)

async def handle_player_message(websocket, data):
    global conversation, enable_history
    """处理玩家消息事件"""
    sender = data['body']['sender']
    message = data['body']['message']
    
    if sender and message:
        print(_("Player {sender} says: {message}").format(sender=sender,message=message))
        if message.startswith(_("GPT chat")):
            prompt = message[len(_("GPT chat")+" "):]
            gpt_message = await gpt_main(prompt)  # 使用 await 调用异步函数
            # 分割消息为长度不超过50的多个部分
            message_parts = [gpt_message[i:i+50] for i in range(0, len(gpt_message), 50)]
            for part in message_parts:
                print(part)
                await send_game_message(websocket, part)
        elif message.startswith(_("GPT save")):
            await conversation.save_conversation()
            await conversation.close()
            conversation = None
            await send_game_message(websocket, _("Conversation closed, and data saved!"))
        elif message.startswith(_("GPT context")):
            await send_game_message(websocket, _("GPT Context state:{enable_history}").format(enable_history=enable_history))
            if message[len(_("GPT context")+" "):] == _("enable"):
                enable_history = True
                await send_game_message(websocket, _("GPT context enabled, watch out for tokens consumption!"))
            elif message[len(_("GPT chat")+" "):] == _("disable"):
                enable_history = False
                await send_game_message(websocket, _("GPT context disabled"))

async def handle_event(websocket, data):
    """根据事件类型处理事件"""
    header = data.get('header', {})
    event_name = header.get('eventName')
    if event_name == "PlayerMessage":
        await handle_player_message(websocket, data)

async def handle_connection(websocket, path):
    print(_("Client Connected"))
    await send_game_message(websocket, welcome_message)
    try:
        await send_data(websocket, {"Result": "true"})
        await subscribe_events(websocket)
        async for message in websocket:
            data = json.loads(message)
            await handle_event(websocket, data)
    except websockets.exceptions.ConnectionClosed:
        print(_("Connection Closed"))
    finally:
        print(_("Client Disconnected"))

async def main():
    async with websockets.serve(handle_connection, ip, port):
        await asyncio.Future()  

if __name__ == "__main__":
    asyncio.run(main())
