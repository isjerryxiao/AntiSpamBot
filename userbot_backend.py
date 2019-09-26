from typing import Union
import logging
logger = logging.getLogger('antispambot.userbot_backend')

API_ID = 00000 # Your api id
API_HASH = 'Your api hash'


from typeguard import typechecked

from telethon import TelegramClient
from telethon.tl.types import PeerUser, PeerChat, PeerChannel
from telethon.tl.types import InputPeerUser, InputPeerChat, InputPeerChannel
from telegram.ext import CallbackContext
from utils import print_traceback

session_name: str = 'antispam'
client = TelegramClient(session_name, API_ID, API_HASH)

DEBUG: bool = False


@typechecked
def client_init() -> None:
    async def __client_init() -> None:
        await client.get_dialogs()
    client.loop.run_until_complete(__client_init())

@typechecked
async def get_input_entity(user_id: int, chat: Union[int, PeerChat, PeerChannel]) -> InputPeerUser:
    MESSAGES_TO_GET = 10
    try:
        return await client.get_input_entity(PeerUser(user_id))
    except ValueError:
        await client.get_messages(chat, MESSAGES_TO_GET)
        return await client.get_input_entity(PeerUser(user_id))


@typechecked
async def userbot_kick_user(chat_id: int, user_id: int) -> bool:
    try:
        await client.edit_permissions(
                  await client.get_input_entity(chat_id),
                  await get_input_entity(user_id, chat_id),
                  until_date = 0,
                  view_messages = False,
                  send_messages = False,
                  send_media = False,
                  send_stickers = False,
                  send_gifs = False,
                  send_games = False,
                  send_inline = False,
                  send_polls = False,
                  change_info = False,
                  invite_users = False,
                  pin_messages = False
              )
        return True
    except Exception:
        print_traceback(debug=DEBUG)
        return False

@typechecked
async def userbot_restrict_user(chat_id: int, user_id: int) -> bool:
    try:
        await client.edit_permissions(
                  await client.get_input_entity(chat_id),
                  await get_input_entity(user_id, chat_id),
                  until_date = 0,
                  view_messages = True,
                  send_messages = False,
                  send_media = False,
                  send_stickers = False,
                  send_gifs = False,
                  send_games = False,
                  send_inline = False,
                  send_polls = False,
                  change_info = False,
                  invite_users = False,
                  pin_messages = False
              )
        return True
    except Exception:
        print_traceback(debug=DEBUG)
        return False

@typechecked
async def userbot_unban_user(chat_id: int, user_id: int) -> bool:
    try:
        await client.edit_permissions(
                  await client.get_input_entity(chat_id),
                  await get_input_entity(user_id, chat_id),
                  until_date = 0
              )
        return True
    except Exception:
        print_traceback(debug=DEBUG)
        return False

@typechecked
async def userbot_delete_message(chat_id: int, message_id: int) -> bool:
    try:
        await client.delete_messages(
                  await client.get_input_entity(chat_id),
                  [message_id,],
                  revoke = True
              )
        return True
    except Exception:
        print_traceback(debug=DEBUG)
        return False

@typechecked
def kick_user(context: CallbackContext, chat_id: int, user_id: Union[int, str], reason: str = '') -> bool:
    user_id = int(user_id)
    ret = client.loop.run_until_complete(userbot_kick_user(chat_id, user_id))
    if ret:
        logger.info(f"Kicked {user_id} in the group {chat_id}{', reason: ' if reason else ''}{reason}")
    else:
        logger.error(f"Cannot kick {user_id} in the group {chat_id}")
    return ret

@typechecked
def restrict_user(context: CallbackContext, chat_id: int, user_id: Union[int, str], extra: str = '') -> bool:
    user_id = int(user_id)
    ret = client.loop.run_until_complete(userbot_restrict_user(chat_id, user_id))
    if ret:
        logger.info(f"Restricted {user_id} in the group {chat_id}{extra}")
    else:
        logger.error(f"Cannot restrict {user_id} in the group {chat_id}")
    return ret

@typechecked
def unban_user(context: CallbackContext, chat_id: int, user_id: Union[int, str], reason: str = '') -> bool:
    user_id = int(user_id)
    ret = client.loop.run_until_complete(userbot_unban_user(chat_id, user_id))
    if ret:
        logger.info(f"Unbanned {user_id} in the group {chat_id}{', reason: ' if reason else ''}{reason}")
    else:
        logger.error(f"Cannot unban {user_id} in the group {chat_id}")
    return ret

@typechecked
def delete_message(context: CallbackContext, chat_id: int, message_id: Union[int, str]) -> bool:
    message_id = int(message_id)
    ret = client.loop.run_until_complete(userbot_delete_message(chat_id, message_id))
    if ret:
        logger.debug(f"Deleted message {message_id} in the group {chat_id}")
    else:
        logger.error(f"Cannot delete message {message_id} in the group {chat_id}")
    return ret
