# This is the bot api backend of kick_user, restrict_user, unban_user, delete_message
import logging
logger = logging.getLogger('antispambot.backend')

from typing import List, Callable
from telegram import Bot, ChatPermissions
from telegram.ext import CallbackContext
from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError)

from utils import print_traceback
from datetime import datetime, timedelta

from config import DEBUG

def kick_user(context: CallbackContext, chat_id: int, kick_id: int, reason: str = '') -> bool:
    bot: Bot = context.bot
    try:
        if bot.kick_chat_member(chat_id=chat_id, user_id=kick_id, until_date=datetime.utcnow()+timedelta(days=367)):
            logger.info(f"Kicked {kick_id} in the group {chat_id}{', reason: ' if reason else ''}{reason}")
        else:
            raise TelegramError('kick_chat_member returned bad status')
    except TelegramError as err:
        logger.error(f"Cannot kick {kick_id} in the group {chat_id}, {err}")
    except Exception:
        print_traceback(DEBUG)
    else:
        return True
    return False


def _export_chat_permissions() -> List[ChatPermissions]:
    CHAT_PERMISSIONS_TUPLE: tuple = (
        'can_send_messages',
        'can_send_media_messages',
        'can_send_polls',
        'can_send_other_messages',
        'can_add_web_page_previews',
        'can_change_info',
        'can_invite_users',
        'can_pin_messages'
    )
    permissons = [ChatPermissions(), ChatPermissions()]
    for i in (0, 1):
        for p in CHAT_PERMISSIONS_TUPLE:
            setattr(permissons[i], p, bool(i))
    return permissons

(CHAT_PERMISSION_RO, CHAT_PERMISSION_RW) = _export_chat_permissions()


def retry_on_network_error(func: Callable) -> Callable:
    NET_RETRY = 3
    def wrapped(*args, **kwargs) -> bool:
        for t in range(NET_RETRY):
            try:
                return func(*args, **kwargs)
            except NetworkError as err:
                logger.info(f"Network issue {err} in {func.__name__}")
                continue
        else:
            logger.warning(f"Aborting, failed {t+1} times in {func.__name__}")
            return False

@retry_on_network_error
def restrict_user(context: CallbackContext, chat_id: int, user_id: int, extra: str = '') -> bool:
    try:
        if context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id,
                                permissions = CHAT_PERMISSION_RO,
                                until_date=datetime.utcnow()+timedelta(days=367)):
            logger.info(f"Restricted {user_id} in the group {chat_id}{extra}")
        else:
            raise TelegramError('restrict_chat_member returned bad status')
    except NetworkError:
        raise
    except TelegramError as err:
        logger.error(f"Cannot restrict {user_id} in the group {chat_id}, {err}")
    except Exception:
        print_traceback(DEBUG)
    else:
        return True
    return False

@retry_on_network_error
def unban_user(context: CallbackContext, chat_id: int, user_id: int, reason: str = '') -> bool:
    try:
        if context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id,
                                permissions = CHAT_PERMISSION_RW,
                                until_date=datetime.utcnow()+timedelta(days=367)):
            logger.info(f"Unbanned {user_id} in the group {chat_id}{', reason: ' if reason else ''}{reason}")
        else:
            raise TelegramError('restrict_chat_member returned bad status')
    except NetworkError:
        raise
    except TelegramError as err:
        logger.error(f"Cannot unban {user_id} in the group {chat_id}, {err}")
    except Exception:
        print_traceback(DEBUG)
    else:
        return True
    return False

@retry_on_network_error
def delete_message(context: CallbackContext, chat_id: int, message_id: int) -> bool:
    try:
        if context.bot.delete_message(chat_id=chat_id, message_id=message_id):
            logger.debug(f"Deleted message {message_id} in the group {chat_id}")
        else:
            raise TelegramError('delete_message returned bad status')
    except NetworkError:
        raise
    except TelegramError as err:
        logger.error(f"Cannot delete message {message_id} in the group {chat_id}, {err}")
    except Exception:
        print_traceback(DEBUG)
    else:
        return True
    return False
