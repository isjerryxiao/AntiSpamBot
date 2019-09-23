#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import List, Any
VER: str = '20190923-1'

# please change token and salt
TOKEN: str = "token_here"
SALT: str  = 'whatever'


WELCOME_WORDS: List[str] = [
    '{}: 为防止垃圾信息泛滥，请在5分钟内完成验证',
    '{}: 本群组启用了加群验证，请在5分钟内完成验证'
]

# challenge words
CLG_DENY: List[str] = [
    '把我踢了吧',
    '我是来发广告的',
    '我进错群了',
    '我就是不通过验证',
    '我不想进这儿的'
]

CLG_ACCEPT: List[str] = [
    '点这里完成验证',
    '我不是机器人'
]

PERMISSION_DENY: List[str] = [
    "这是给人家管理员点的地方！",
    "点你妹！你就这么想被口球吗？"
]

WORKERS: int             = 4
AT_ADMINS_RATELIMIT: int = 5*60
CHALLENGE_TIMEOUT: int   = 5*60
UNBAN_TIMEOUT: int       = 5*60

DEBUG = False

import logging
from telegram import Update, User, Bot, Message, Chat
from telegram.ext import CallbackContext, Job

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, run_async

from datetime import datetime, timedelta
from time import time
from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError)

from mwt import MWT
from utils import print_traceback
from random import choice, randint, shuffle
from hashlib import md5, sha256


logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('antispambot')

updater = Updater(TOKEN, workers=WORKERS, use_context=True)

def error_callback(update: Update, context:CallbackContext) -> None:
    error: Exception = context.error
    try:
        raise error
    except Exception:
        print_traceback(debug=DEBUG)

def collect_error(func):
    '''
        designed to fix a bug in the telegram library
    '''
    def wrapped(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception:
            print_traceback(debug=DEBUG)
    return wrapped

def fName(user: User, atuser: bool = True, markdown: bool = True) -> str:
    name: str = user.full_name
    if markdown:
        mdtext: str = user.mention_markdown(name=user.full_name)
        return mdtext
    elif user.username:
        if atuser:
            name += " (@{})".format(user.username)
        else:
            name += " ({})".format(user.username)
    return name

@MWT(timeout=60*60)
def getAdminIds(bot: Bot, chat_id: int) -> List[int]:
    admin_ids = list()
    for chat_member in bot.get_chat_administrators(chat_id):
        admin_ids.append(chat_member.user.id)
    return admin_ids

@MWT(timeout=60*60)
def getAdminUsernames(bot: Bot, chat_id: int, markdown: bool = False) -> List[str]:
    admins = list()
    for chat_member in bot.get_chat_administrators(chat_id):
        if markdown:
            if chat_member.user.id != bot.id:
                admins.append(chat_member.user.mention_markdown(name=chat_member.user.name))
        else:
            if chat_member.user.username and chat_member.user.username != bot.username:
                admins.append(chat_member.user.username)
    return admins

@run_async
@collect_error
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text((f'你好{update.message.from_user.first_name}'
                                '，机器人目前功能如下:\n'
                               f'1.新加群用户需要在{int(CHALLENGE_TIMEOUT/60)}分钟内点击'
                               f'按钮验证，否则将封禁{int(UNBAN_TIMEOUT/60)}分钟。\n'
                                '  若该用户为群成员邀请，则邀请人也可以帮助验证。\n'
                                '2.新加群的bot需要拉入用户或管理员确认。\n'
                                '要让其正常工作，请将这个机器人添加进一个群组，'
                                '设为管理员并打开封禁权限。'))
    logger.debug(f"Start from {update.message.from_user.id}")

@run_async
@collect_error
def source(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(f'Source code: https://github.com/isjerryxiao/AntiSpamBot\nVersion: {VER}')
    logger.debug(f"Source from {update.message.from_user.id}")


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
CHAT_PERMISSION_RO: ChatPermissions = ChatPermissions()
CHAT_PERMISSION_RW: ChatPermissions = ChatPermissions()
for p in CHAT_PERMISSIONS_TUPLE:
    setattr(CHAT_PERMISSION_RO, p, False)
for p in CHAT_PERMISSIONS_TUPLE[:5]:
    setattr(CHAT_PERMISSION_RW, p, True)

def get_chat_permissions(context: CallbackContext, chat_id: int) -> ChatPermissions:
    @MWT(timeout=8*60*60)
    def get_chat(chat_id: int) -> Chat:
        chat: Chat = context.bot.get_chat(chat_id)
        return chat
    try:
        chat: Chat = get_chat(chat_id)
    except TelegramError as err:
        logger.warning(f'Cannot get chat permission for {chat_id}, {err}, using default')
        return CHAT_PERMISSION_RW
    except Exception:
        print_traceback(DEBUG)
        return CHAT_PERMISSION_RW
    else:
        permisson: ChatPermissions = chat.permissions
        return permisson


def restrict_user(context: CallbackContext, chat_id: int, user_id: int, extra: str = '') -> bool:
    try:
        if context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id,
                                permissions = CHAT_PERMISSION_RO,
                                until_date=datetime.utcnow()+timedelta(days=367)):
            logger.info(f"Restricted {user_id} in the group {chat_id}{extra}")
        else:
            raise TelegramError('restrict_chat_member returned bad status')
    except TelegramError as err:
        logger.error(f"Cannot restrict {user_id} in the group {chat_id}, {err}")
    except Exception:
        print_traceback(DEBUG)
    else:
        return True
    return False

def unban_user(context: CallbackContext, chat_id: int, user_id: int, reason: str = '') -> bool:
    try:
        chat_permission = get_chat_permissions(context, chat_id)
        if context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id,
                                permissions = chat_permission,
                                until_date=datetime.utcnow()+timedelta(days=367)):
            logger.info(f"Unbanned {user_id} in the group {chat_id}{', reason: ' if reason else ''}{reason}")
        else:
            raise TelegramError('restrict_chat_member returned bad status')
    except TelegramError as err:
        logger.error(f"Cannot unban {user_id} in the group {chat_id}, {err}")
    except Exception:
        print_traceback(DEBUG)
    else:
        return True
    return False

def delete_message(context: CallbackContext, chat_id: int, message_id: int) -> bool:
    try:
        if context.bot.delete_message(chat_id=chat_id, message_id=message_id):
            logger.debug(f"Deleted message {message_id} in the group {chat_id}")
        else:
            raise TelegramError('delete_message returned bad status')
    except TelegramError as err:
        logger.error(f"Cannot delete message {message_id} in the group {chat_id}, {err}")
    except Exception:
        print_traceback(DEBUG)
    else:
        return True
    return False


def challenge_gen_pw(user_id: int, join_msgid: int, real: bool = True) -> str:
    if real:
        action = 'pass'
    else:
        action = str(time())
    pw = "{}{}{}{}".format(SALT, user_id, join_msgid, action)
    pw_sha256 = sha256(pw.encode('utf-8', errors='ignore')).hexdigest()
    pw_sha256_md5 = md5(pw_sha256.encode('utf-8', errors='ignore')).hexdigest()
    # telegram limits callback_data to 64 bytes max, we need to be brief
    callback = pw_sha256_md5[:8]
    return callback

def challange_hash(user_id: int, chat_id: int, join_msgid: int) -> str:
    hashes = [str(hash(str(i))) for i in (user_id, chat_id, join_msgid)]
    identity = hash(''.join(hashes))
    return str(identity)

@run_async
@collect_error
def challenge_verification(update: Update, context: CallbackContext) -> None:
    bot: Bot = context.bot
    chat_id: int = update.callback_query.message.chat.id
    user: User = update.callback_query.from_user
    message_id: int = update.callback_query.message.message_id
    data: str = update.callback_query.data
    if not data:
        logger.error('Empty Inline challenge data.')
        return
    args: List[str] = data.split()
    if not (args and len(args) == 5):
        logger.error(f'Wrong Inline challenge data length. {data}')
        return
    (r_user_id, invite_user_id, join_msgid) = args[2:]
    admin_ids = getAdminIds(bot, chat_id)
    expected_callback = challenge_gen_pw(r_user_id, join_msgid)
    if user.id in admin_ids or str(r_user_id) == str(user.id) or str(invite_user_id) == str(user.id):
        if args[1] != expected_callback:
            kick_by_admin = True if user.id in admin_ids else False
            kick_user(context, chat_id, r_user_id, 'Kicked by admin' if kick_by_admin else 'Challange failed')
            def then_unban(_: Any) -> None:
                unban_user(context, chat_id, r_user_id, reason='Unban timeout reached.')
            context.job_queue.run_once(then_unban, UNBAN_TIMEOUT, name='unban_job')
        else:
            unban_user(context, chat_id, r_user_id, reason='Challenge passed.')
            bot.answer_callback_query(callback_query_id=update.callback_query.id,
                                    text='验证成功。',
                                    show_alert=True)
        for _msg_id in (join_msgid, message_id):
            delete_message(context, chat_id=chat_id, message_id=_msg_id)
        mjobs: tuple = context.job_queue.get_jobs_by_name(challange_hash(r_user_id, chat_id, join_msgid))
        assert len(mjobs) == 1
        mjob: Job = mjobs[0]
        mjob.schedule_removal()
    else:
        logger.info((f"Naughty user {fName(user, markdown=False)} (id: {user.id}) clicked a button"
                     f"from the group {chat_id}"))
        bot.answer_callback_query(callback_query_id=update.callback_query.id,
                                  text=choice(PERMISSION_DENY),
                                  show_alert=True)

def simple_challenge(context, chat_id, user, invite_user, join_msgid) -> None:
    bot: Bot = context.bot
    try:
        if restrict_user(context, chat_id=chat_id, user_id=user.id, extra=', is_bot=True' if user.is_bot else ''):
            amount_fake_btns: int = randint(1, len(CLG_DENY) if len(CLG_DENY) < 3 else 3)
            fake_btns_text: list = CLG_DENY.copy()
            shuffle(fake_btns_text)
            fake_btns_text: list = fake_btns_text[:amount_fake_btns]
            buttons = [
                *[
                    [InlineKeyboardButton(text=fake_btn_text, callback_data = \
                        f"clg {challenge_gen_pw(user.id, join_msgid, real=False)} {user.id} {invite_user.id} {join_msgid}")
                    ] for fake_btn_text in fake_btns_text
                ],
                [InlineKeyboardButton(text=choice(CLG_ACCEPT), callback_data = \
                    f"clg {challenge_gen_pw(user.id, join_msgid)} {user.id} {invite_user.id} {join_msgid}")
                ]
            ]
            shuffle(buttons)
            msg: Message = bot.send_message(chat_id=chat_id,
                                            text=choice(WELCOME_WORDS).format(fName(user, markdown=True)),
                                            parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(buttons))
            def kick_then_unban(_: Any) -> None:
                def then_unban(_: Any) -> None:
                    unban_user(context, chat_id, user.id, reason='Unban timeout reached.')
                if kick_user(context, chat_id, user.id, reason='Challange timeout.'):
                    context.job_queue.run_once(then_unban, UNBAN_TIMEOUT, name='unban_job')
                for _msg_id in (join_msgid, msg.message_id):
                    delete_message(context, chat_id=chat_id, message_id=_msg_id)
            context.job_queue.run_once(kick_then_unban, CHALLENGE_TIMEOUT,
                                       name=challange_hash(user.id, chat_id, join_msgid))
        else:
            raise TelegramError
    except (TelegramError, BadRequest):
        bot.send_message(chat_id=chat_id,
                text="发现新加入的成员: {0} ，但机器人不是管理员导致无法实施有效行动。"
                     "请将机器人设为管理员并打开封禁权限。".format(fName(user, markdown=True)),
                parse_mode="Markdown")
        logger.error((f"Cannot restrict {user.id} and {invite_user.id} in "
                      f"the group {chat_id}{', is_bot=True' if user.is_bot else ''}"))


@run_async
@collect_error
def at_admins(update: Update, context: CallbackContext) -> None:
    chat_type: str = update.message.chat.type
    if chat_type in ('private', 'channel'):
        return
    bot: Bot = context.bot
    chat_id: int = update.message.chat.id
    last_at_admins: float = context.chat_data.setdefault('last_at_admins', 0)
    if time() - last_at_admins < AT_ADMINS_RATELIMIT:
        notice: Message = update.message.reply_text(f"请再等待 {round(AT_ADMINS_RATELIMIT - (time() - last_at_admins), 3)} 秒")
        def delete_notice(context: Any) -> None:
            update.message.delete()
            notice.delete()
            logger.info(f"Deleted at_admin spam messages {update.message.message_id} and {notice.message_id} from {update.message.from_user.id}")
        context.job_queue.run_once(delete_notice, 5)
        return
    admins: List[str] = getAdminUsernames(bot, chat_id, markdown=True)
    if admins:
        update.message.reply_text("  ".join(admins), parse_mode='Markdown')
    context.chat_data["last_at_admins"]: float = time()
    logger.info(f"At_admin sent from {update.message.from_user.id} {chat_id}")


@run_async
@collect_error
def status_update(update: Update, context: CallbackContext) -> None:
    chat_type: str = update.message.chat.type
    if chat_type in ('private', 'channel'):
        return
    bot: Bot = context.bot
    chat_id: int = update.message.chat_id
    if update.message.new_chat_members:
        users: List[User] = update.message.new_chat_members
        invite_user: User = update.message.from_user
        for user in users:
            if user.id == bot.id:
                logger.info(f"Myself joined the group {chat_id}")
            else:
                logger.debug(f"{user.id} joined the group {chat_id}")
                if invite_user.id != user.id and invite_user.id in getAdminIds(bot, chat_id):
                    # An admin invited him.
                    logger.info(f"{'bot ' if user.is_bot else ''}{user.id} invited by admin {invite_user.id} into the group {chat_id}")
                else:
                    simple_challenge(context, chat_id, user, invite_user, update.effective_message.message_id)

if __name__ == '__main__':
    updater.dispatcher.add_error_handler(error_callback)
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('source', source))
    updater.dispatcher.add_handler(CommandHandler('admins', at_admins))
    updater.dispatcher.add_handler(CommandHandler('admin', at_admins))
    updater.dispatcher.add_handler(CallbackQueryHandler(challenge_verification, pattern=r'clg'))
    updater.dispatcher.add_handler(MessageHandler(Filters.status_update, status_update))
    logger.info('Antispambot started.')
    updater.start_polling()
    updater.idle()
