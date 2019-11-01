#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import List, Any, Callable, Tuple, Set
VER: str = '20191101-2'

from config import (SALT, WORKERS, AT_ADMINS_RATELIMIT, STORE_CHAT_MESSAGES,
                    GARBAGE_COLLENTION_INTERVAL,
                    CHAT_SETTINGS as CHAT_SETTINGS_DEFAULT, CHAT_SETTINGS_HELP,
                    USER_BOT_BACKEND, DEBUG)
assert not [k for k in CHAT_SETTINGS_DEFAULT if k not in CHAT_SETTINGS_HELP]

import logging
from ratelimited import mqbot
from telegram import Update, User, Bot, Message
from telegram.ext import CallbackContext, Job, PicklePersistence

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          CallbackQueryHandler, run_async)
from telegram.ext.filters import InvertedFilter

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

ppersistence = PicklePersistence(filename='antispambot.pickle', store_user_data=False)
updater = Updater(bot=mqbot, workers=WORKERS, persistence=ppersistence, use_context=True)

def error_callback(update: Update, context:CallbackContext) -> None:
    error: Exception = context.error
    try:
        raise error
    except Exception:
        print_traceback(debug=DEBUG)

def collect_error(func: Callable) -> Callable:
    '''
        designed to fix a bug in the telegram library
    '''
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            print_traceback(debug=DEBUG)
    return wrapped

def filter_old_updates(func: Callable[[Update, CallbackContext], Callable]) -> Callable:
    '''
        do not process very old updates
    '''
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs) -> Any:
        msg: Message = update.effective_message
        sent_time: datetime = msg.edit_date if msg.edit_date else msg.date
        seconds_from_now: float = (datetime.utcnow() - sent_time).total_seconds()
        if int(seconds_from_now) > 5*60:
            logger.warning(f'Not processing update {update.update_id} since it\'s too old ({int(seconds_from_now)}).')
            return
        else:
            return func(update, context, *args, **kwargs)
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
@filter_old_updates
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text((f'你好{update.message.from_user.first_name}'
                                '，机器人目前功能如下:\n'
                                '1.新加群用户需要在一定时间内点击'
                                '按钮验证，否则将被封禁一段时间。\n'
                                '若该用户为群成员邀请，则邀请人也可以帮助验证。\n'
                                '2.新加群的bot需要拉入用户或管理员确认。\n'
                                '要让其正常工作，请将这个机器人添加进一个群组，'
                                '设为管理员并打开封禁权限。'),
                              isgroup=update.message.chat.type != 'private')
    logger.debug(f"Start from {update.message.from_user.id}")

@run_async
@collect_error
@filter_old_updates
def source(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(f'Source code: https://github.com/isjerryxiao/AntiSpamBot\nVersion: {VER}',
                              isgroup=update.message.chat.type != 'private')
    logger.debug(f"Source from {update.message.from_user.id}")

class chatSettings:
    __data = dict()
    def __init__(self, datadict):
        for k in CHAT_SETTINGS_DEFAULT:
            d = datadict.get(k, None)
            self.__data[k] = d
    def get(self, name):
        if name in CHAT_SETTINGS_DEFAULT:
            ret = self.__data.get(name, None)
            if ret is None:
                return CHAT_SETTINGS_DEFAULT[name]
            else:
                return ret
    def choice(self, name):
        data = self.get(name)
        if type(data) is list:
            return choice(data)
    def get_clg_accecpt_deny(self):
        l = self.choice('CLG_QUESTIONS')
        return (l[0], l[1], l[2:])
    def __process(self, name: str, inputstr: str) -> str:
        if name == 'WELCOME_WORDS':
            uinput = [l[:4000] for l in inputstr.split('\n') if l]
            self.__data[name] = uinput
        elif name == 'CLG_QUESTIONS':
            uinput = [l for l in inputstr.split('\n') if l]
            if len(uinput) < 3:
                return False
            uinput[0] = uinput[0][:4000]
            for i in range(1, len(uinput)):
                uinput[i] = uinput[i][:200]
            if not self.__data.get(name, None):
                self.__data[name] = CHAT_SETTINGS_DEFAULT[name].copy()
            self.__data[name].append(uinput)
        elif name in ('CHALLENGE_SUCCESS', 'PERMISSION_DENY'):
            uinput = [l[:30] for l in inputstr.split('\n') if l]
            self.__data[name] = uinput
        elif name in ('CHALLENGE_TIMEOUT', 'UNBAN_TIMEOUT', 'FLOOD_LIMIT'):
            try:
                seconds = int(inputstr)
                if name == 'CHALLENGE_TIMEOUT':
                    if seconds > 3600 or seconds < 1:
                        raise ValueError
                elif name == 'UNBAN_TIMEOUT':
                    if seconds > 86400 or seconds < 0:
                        seconds = 0
                elif name == 'FLOOD_LIMIT':
                    if seconds < 0 or seconds > 1000:
                        seconds = 1
                else:
                    raise NotImplementedError(f"{name} is unknown")
            except ValueError:
                return False
            else:
                self.__data[name] = seconds
        else:
            raise NotImplementedError(f"{name} is unknown")
        return name
    def delete_clg_question(self, index: int):
        name = 'CLG_QUESTIONS'
        if not self.__data.get(name, None):
            self.__data[name] = CHAT_SETTINGS_DEFAULT[name].copy()
        if index >= 0 and len(self.__data[name]) > index and len(self.__data[name]) >= 2:
            return self.__data[name].pop(index)
        else:
            return False
    def put(self, name: str, inputstr: str):
        if not inputstr:
            self.__data[name] = None
            return True
        elif name in CHAT_SETTINGS_DEFAULT:
            return self.__process(name, inputstr)
    def to_dict(self):
        return self.__data

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
    my_msg = context.chat_data.setdefault('my_msg', [None, list()]) # [msgid, [CorrectCallback, FakeCallback, ..]]
    rest_users = context.chat_data.setdefault('rest_users', dict()) # {user_id: [int(time), join_msgid, bot_invite_uid]}
    settings = chatSettings(context.chat_data.get('chat_settings', dict()))
    if not data:
        logger.error('Empty Inline challenge data.')
        return
    args: List[str] = data.split()
    if args and len(args) == 2:
        args.append('')
    if not (args and len(args) == 3):
        logger.error(f'Wrong Inline challenge data length. {data}')
        return
    (btn_callback, bot_uid) = args[1:]
    # bot_uid is '' if the restricted user is not a bot
    if bot_uid == '' and data not in my_msg[1]:
        # Unknown callback, maybe is from a previous message, ignore.
        bot.answer_callback_query(callback_query_id=update.callback_query.id, text="Try again")
        return
    if bot_uid:
        try:
            r_user_id = int(bot_uid)
        except ValueError:
            logger.error(f'Bad bot_uid, {data}')
            bot.answer_callback_query(callback_query_id=update.callback_query.id, text="Fail")
            return
    else:
        r_user_id = user.id
    rul = rest_users.get(r_user_id, None)
    if type(rul) is not list:
        naughty_user = True
    else:
        (_, join_msgid, bot_invite_uid) = rul
        if bot_uid == '':
            naughty_user = False
        elif user.id == bot_invite_uid or user.id in getAdminIds(bot, chat_id):
            naughty_user = False
        else:
            naughty_user = True
    if not naughty_user:
        # Remove old job first, then take action
        if settings.get('CHALLENGE_TIMEOUT') > 0:
            mjobs: tuple = context.job_queue.get_jobs_by_name(challange_hash(r_user_id, chat_id, join_msgid))
            if len(mjobs) == 1:
                mjob: Job = mjobs[0]
                mjob.schedule_removal()
            else:
                logger.error(f'There is no pending job for {r_user_id} in the group {chat_id}')
                if DEBUG:
                    try:
                        raise Exception
                    except Exception:
                        print_traceback(debug=DEBUG)
        if (bot_uid == '' and data != my_msg[1][0]) or (bot_uid and btn_callback != challenge_gen_pw(r_user_id, join_msgid)):
            kick_user(context, chat_id, r_user_id, 'Challange failed')
            def then_unban(_: CallbackContext) -> None:
                unban_user(context, chat_id, r_user_id, reason='Unban timeout reached.')
            UNBAN_TIMEOUT = settings.get('UNBAN_TIMEOUT')
            if UNBAN_TIMEOUT > 0:
                context.job_queue.run_once(then_unban, UNBAN_TIMEOUT, name='unban_job')
            rest_users.pop(r_user_id)
            if bot_uid or len(rest_users) == 0:
                delete_message(context, chat_id=chat_id, message_id=message_id)
            delete_message(context, chat_id=chat_id, message_id=join_msgid)
        else:
            unban_user(context, chat_id, r_user_id, reason='Challenge passed.')
            bot.answer_callback_query(callback_query_id=update.callback_query.id,
                                    text=settings.choice('CHALLENGE_SUCCESS'),
                                    show_alert=True)
            rest_users.pop(r_user_id)
            if bot_uid or len(rest_users) == 0:
                delete_message(context, chat_id=chat_id, message_id=message_id)

    else:
        logger.info((f"Naughty user {fName(user, markdown=False)} (id: {user.id}) clicked a button"
                     f" from the group {chat_id}"))
        bot.answer_callback_query(callback_query_id=update.callback_query.id,
                                  text=settings.choice('PERMISSION_DENY'),
                                  show_alert=True)

def simple_challenge(context, chat_id, user, invite_user, join_msgid) -> None:
    bot: Bot = context.bot
    my_msg = context.chat_data.setdefault('my_msg', [None, list()]) # [msgid, [CorrectCallback, FakeCallback, ..]]
    rest_users = context.chat_data.setdefault('rest_users', dict()) # {user_id: [int(time), join_msgid, bot_invite_uid]}
    settings = chatSettings(context.chat_data.get('chat_settings', dict()))
    (CLG_QUESTION, CLG_ACCEPT, CLG_DENY) = settings.get_clg_accecpt_deny()
    # flooding protection
    FLOOD_LIMIT = settings.get('FLOOD_LIMIT')
    if FLOOD_LIMIT == 0:
        flag_flooding = False
    elif FLOOD_LIMIT == 1:
        flag_flooding = True
    else:
        if len(rest_users) + 1 >= FLOOD_LIMIT:
            flag_flooding = True
        else:
            flag_flooding = False
    def organize_btns(buttons: List[InlineKeyboardButton]) -> List[List[InlineKeyboardButton]]:
        '''
            Shuffle buttons and put them into a 2d array
        '''
        shuffle(buttons)
        output = [list(),]
        LENGTH_PER_LINE = 16
        MAXIMUM_PER_LINE = 4
        clength = LENGTH_PER_LINE
        for btn in buttons:
            l = len(btn.text)
            clength -= l
            if clength < 0 or len(output[-1]) >= MAXIMUM_PER_LINE:
                clength = LENGTH_PER_LINE - l
                output.append([btn])
            else:
                output[-1].append(btn)
        return output
    try:
        if restrict_user(context, chat_id=chat_id, user_id=user.id, extra=((' [flooding]' if flag_flooding else '') + \
                                                                           (' [bot]' if user.is_bot else ''))):
            if my_msg[0] is not None and (not (user.is_bot or not(flag_flooding))):
                delete_message(context, chat_id, my_msg[0])
            buttons = [
                InlineKeyboardButton(text=CLG_ACCEPT, callback_data = \
                    (f"clg {challenge_gen_pw(user.id, join_msgid)} "
                     f"{user.id if user.is_bot or not(flag_flooding) else ''}")),
                *[InlineKeyboardButton(text=fake_btn_text, callback_data = \
                    (f"clg {challenge_gen_pw(user.id, join_msgid, real=False)} "
                     f"{user.id if user.is_bot or not(flag_flooding) else ''}"))
                for fake_btn_text in CLG_DENY]
            ]
            callback_datalist = [btn.callback_data for btn in buttons]
            buttons = organize_btns(buttons)
            msg: Message = bot.send_message(chat_id=chat_id,
                                            reply_to_message_id=join_msgid,
                                            text=('' if user.is_bot or not(flag_flooding) else \
                                                        f'待验证用户: {len(rest_users)+1}名\n') + \
                                                 settings.choice('WELCOME_WORDS').replace(
                                                    '%time%', f"{settings.get('CHALLENGE_TIMEOUT')}") + \
                                                    f"\n{CLG_QUESTION}",
                                            parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(buttons),
                                            isgroup=False) # These messages are essential and should not be delayed.
            if not (user.is_bot or not(flag_flooding)):
                my_msg[0] = msg.message_id
                my_msg[1] = callback_datalist
            bot_invite_uid = invite_user.id if user.is_bot or not(flag_flooding) else None
            rest_users[user.id] = [int(time()), join_msgid, bot_invite_uid]
            # User restricted and buttons sent, now search for this user's previous messages and delete them
            sto_msgs: List[Tuple[int, int, int]] = context.chat_data.get('stored_messages', list())
            msgids_to_delete: Set[int] = set([u_m_t[1] for u_m_t in sto_msgs if u_m_t[0] == user.id])
            for _mid in msgids_to_delete:
                delete_message(context, chat_id, _mid)
            # kick them after timeout
            def kick_then_unban(_: CallbackContext) -> None:
                def then_unban(_: CallbackContext) -> None:
                    unban_user(context, chat_id, user.id, reason='Unban timeout reached.')
                if kick_user(context, chat_id, user.id, reason='Challange timeout.'):
                    UNBAN_TIMEOUT = settings.get('UNBAN_TIMEOUT')
                    if UNBAN_TIMEOUT > 0:
                        context.job_queue.run_once(then_unban, UNBAN_TIMEOUT, name='unban_job')
                rest_users.pop(user.id)
                if (user.is_bot or not(flag_flooding)) or len(rest_users) == 0:
                    delete_message(context, chat_id=chat_id, message_id=msg.message_id)
                delete_message(context, chat_id=chat_id, message_id=join_msgid)
            CHALLENGE_TIMEOUT = settings.get('CHALLENGE_TIMEOUT')
            if CHALLENGE_TIMEOUT > 0:
                context.job_queue.run_once(kick_then_unban, CHALLENGE_TIMEOUT,
                                           name=challange_hash(user.id, chat_id, join_msgid))
        else:
            raise TelegramError('')
    except TelegramError:
        bot.send_message(chat_id=chat_id,
                text="发现新加入的成员: {0} ，但机器人不是管理员导致无法实施有效行动。"
                     "请将机器人设为管理员并打开封禁权限。".format(fName(user, markdown=True)),
                parse_mode="Markdown")
        logger.error((f"Cannot restrict {user.id} and {invite_user.id} in "
                      f"the group {chat_id}{' [bot]' if user.is_bot else ''}"))


@run_async
@collect_error
@filter_old_updates
def at_admins(update: Update, context: CallbackContext) -> None:
    chat_type: str = update.message.chat.type
    if chat_type in ('private', 'channel'):
        return
    bot: Bot = context.bot
    chat_id: int = update.message.chat.id
    last_at_admins: float = context.chat_data.setdefault('last_at_admins', 0.0)
    if time() - last_at_admins < AT_ADMINS_RATELIMIT:
        notice: Message = update.message.reply_text(f"请再等待{AT_ADMINS_RATELIMIT - (time() - last_at_admins): .3f}秒")
        def delete_notice(_: CallbackContext) -> None:
            for _msg_id in (update.message.message_id, notice.message_id):
                delete_message(context, chat_id=chat_id, message_id=_msg_id)
            logger.info((f"Deleted at_admin spam messages {update.message.message_id} and "
                         f"{notice.message_id} from {update.message.from_user.id}"))
        context.job_queue.run_once(delete_notice, 5)
    else:
        admins: List[str] = getAdminUsernames(bot, chat_id, markdown=True)
        if admins:
            update.message.reply_text("  ".join(admins), parse_mode='Markdown')
        context.chat_data["last_at_admins"]: float = time()
        logger.info(f"At_admin sent from {update.message.from_user.id} {chat_id}")

def write_settings(update: Update, context: CallbackContext) -> None:
    settings_call = context.chat_data.get('settings_call', None)
    if settings_call is None:
        return
    if update.message.from_user.id not in getAdminIds(context.bot, update.message.chat_id):
        return
    try:
        lasttime = float(settings_call[0])
        caller_uid = int(settings_call[1])
        item = str(settings_call[2])
    except Exception:
        context.chat_data['settings_call'] = None
        return
    if caller_uid != update.message.from_user.id:
        return
    if time() - lasttime > 120.0:
        context.chat_data['settings_call'] = None
        return
    params = [line.strip() for line in update.message.text.split('\n') if line]
    if len(params) == 0:
        return
    if item not in CHAT_SETTINGS_DEFAULT:
        return
    settings = chatSettings(context.chat_data.get('chat_settings', dict()))
    ret = settings.put(item, '\n'.join(params))
    context.chat_data['settings_call'] = None
    if ret:
        settings_menu(update, context, additional_text="设置成功\n\n")
        context.chat_data['chat_settings'] = settings.to_dict()
        ppersistence.flush()
    else:
        settings_menu(update, context, additional_text="您的输入有误，请重试\n\n")

@run_async
@collect_error
@filter_old_updates
def settings_menu(update: Update, context: CallbackContext, additional_text: str = '') -> None:
    chat_type: str = update.message.chat.type
    if chat_type in ('private', 'channel'):
        return
    if update.message.from_user.id in getAdminIds(context.bot, update.message.chat.id):
        buttons = [
            [InlineKeyboardButton(text=CHAT_SETTINGS_HELP[item][0], callback_data = f"settings {item}")]
        for item in CHAT_SETTINGS_DEFAULT]
        update.message.reply_text(text=f"{additional_text}请选择一项设置",
                                  reply_markup=InlineKeyboardMarkup(buttons))

@run_async
@collect_error
@filter_old_updates
def settings_cancel(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id in getAdminIds(context.bot, update.message.chat.id):
        settings_call = context.chat_data.get('settings_call', None)
        if settings_call:
            context.chat_data['settings_call'] = None
            update.message.reply_text('取消成功')
        else:
            update.message.reply_text('今日无事可做')

@run_async
@collect_error
def settings_callback(update: Update, context: CallbackContext) -> None:
    user: User = update.callback_query.from_user
    chat_id: int = update.callback_query.message.chat.id
    callback_answered: bool = False
    if user.id in getAdminIds(context.bot, chat_id):
        message: int = update.callback_query.message
        data: str = update.callback_query.data

        args: List[str] = data.split()
        if not (args and len(args) in (2,3)):
            logger.error(f'Wrong Inline settings data length. {data}')
            update.callback_query.answer()
        else:
            if args[1] not in CHAT_SETTINGS_DEFAULT:
                update.callback_query.answer(f'Unexpected {args[1]}')
                return
            item = args[1]
            settings = chatSettings(context.chat_data.get('chat_settings', dict()))
            helptext = f"设置项: {CHAT_SETTINGS_HELP.get(item, [item, None])[0]}\n"
            helptext += "当前设置: "
            current_value = settings.get(item)
            buttons = [[InlineKeyboardButton(text="恢复默认", callback_data = f"{' '.join(args[:2])} default")]]
            # handle default
            if len(args) == 3 and args[2] == 'default':
                if settings.put(item, ''):
                    context.chat_data['chat_settings'] = settings.to_dict()
                    ppersistence.flush()
                    update.callback_query.answer('成功', show_alert=True)
                    # refresh
                    settings = chatSettings(context.chat_data.get('chat_settings', dict()))
                    current_value = settings.get(item)
                else:
                    update.callback_query.answer('失败', show_alert=True)
            if item == 'CLG_QUESTIONS':
                # handle delete
                if len(args) == 3 and args[2] not in ('set', 'default'):
                    try:
                        index = int(args[2])
                    except ValueError:
                        logger.error(f'Upexpected CLG_QUESTIONS index {data}')
                        return
                    callback_answered = True
                    if settings.delete_clg_question(index):
                        context.chat_data['chat_settings'] = settings.to_dict()
                        ppersistence.flush()
                        update.callback_query.answer('成功', show_alert=True)
                        # refresh
                        settings = chatSettings(context.chat_data.get('chat_settings', dict()))
                        current_value = settings.get(item)
                    else:
                        update.callback_query.answer('失败', show_alert=True)
                if len(current_value) <= 10:
                    buttons += [[InlineKeyboardButton(text="添加新项", callback_data = f"{' '.join(args[:2])} set")]]
                for i in range(len(current_value)):
                    name = current_value[i][0]
                    corr_answ = current_value[i][1]
                    fals_answ = current_value[i][2:]
                    if len(current_value) > 1:
                        buttons.append([InlineKeyboardButton(text=f"删除 {i+1}:{name[:20]}",
                                                             callback_data = f"{' '.join(args[:2])} {i}")])
                    helptext += f"\n问题{i+1: >2d} :{name}\n正确答案: {corr_answ}"
                    for f in fals_answ:
                        helptext += f"\n错误答案: {f}"
            else:
                buttons += [[InlineKeyboardButton(text="更改", callback_data = f"{' '.join(args[:2])} set")]]
                if type(current_value) is list:
                    current_value = '\n'.join([f"备选项: {x}" for x in current_value])
                    helptext += '\n'
                helptext += str(current_value)
            if len(args) == 3 and args[2] == 'set':
                helptext += '\n\n'
                helptext += f"设置说明:\n{CHAT_SETTINGS_HELP.get(item, [None, None])[1]}\n"
                helptext += "\n您正在设置新选项\n请在120秒内回复格式正确的内容，/cancel 取消设置。"
                context.chat_data['settings_call'] = [time(), user.id, item]
                reply_markup = None
            else:
                reply_markup = InlineKeyboardMarkup(buttons)
            if not callback_answered:
                update.callback_query.answer()
            helptext = helptext[:4096]
            if message.text == helptext and message.reply_markup is not None and reply_markup is not None:
                if len(message.reply_markup.inline_keyboard) == len(reply_markup.inline_keyboard):
                    return
            message.edit_text(helptext, reply_markup=reply_markup)
    else:
        update.callback_query.answer()

@run_async
@collect_error
@filter_old_updates
def new_messages(update: Update, context: CallbackContext) -> None:
    if not (update.effective_user and update.effective_message):
        return
    chat_type: str = update.message.chat.type
    if chat_type in ('private', 'channel'):
        return
    sto_msgs: List[Tuple[int, int, int]] = context.chat_data.setdefault('stored_messages', list())
    sto_msgs.append((update.effective_user.id, update.effective_message.message_id, int(time())))
    while len(sto_msgs) > STORE_CHAT_MESSAGES:
        sto_msgs.pop(0)
    if update.message.text:
        write_settings(update, context)

@run_async
@collect_error
@filter_old_updates
def new_mems(update: Update, context: CallbackContext) -> None:
    chat_type: str = update.message.chat.type
    if chat_type in ('private', 'channel'):
        return
    bot: Bot = context.bot
    chat_id: int = update.message.chat_id
    assert update.message.new_chat_members
    users: List[User] = update.message.new_chat_members
    invite_user: User = update.message.from_user
    for user in users:
        if user.id == bot.id:
            logger.info(f"Myself joined the group {chat_id}")
        else:
            logger.debug(f"{user.id} joined the group {chat_id}")
            if invite_user.id != user.id and invite_user.id in getAdminIds(bot, chat_id):
                # An admin invited him.
                logger.info((f"{'bot ' if user.is_bot else ''}{user.id} invited by admin "
                                f"{invite_user.id} into the group {chat_id}"))
            else:
                simple_challenge(context, chat_id, user, invite_user, update.effective_message.message_id)

def do_garbage_collection(context: CallbackContext) -> None:
    u_freed:   int = 0
    m_freed:   int = 0
    u_checked: int = 0
    m_checked: int = 0
    all_chat_data = updater.dispatcher.chat_data
    for chat_id in all_chat_data:
        rest_users = all_chat_data[chat_id].get('rest_users', None)
        if type(rest_users) is dict:
            for uid in [k for k in rest_users]:
                try:
                    u_checked += 1
                    if int(time()) - rest_users[uid][0] > 7200:
                        u_freed += 1
                        rest_users.pop(uid)
                except Exception:
                    print_traceback(debug=DEBUG)
        sto_msgs = all_chat_data[chat_id].get('stored_messages', None)
        if type(sto_msgs) is not list:
            to_rm = list()
            try:
                for item in sto_msgs:
                    m_checked += 1
                    if len(item) == 3:
                        stime = item[2]
                        if int(time()) - stime > 7200:
                            to_rm.append(item)
            except Exception:
                print_traceback(debug=DEBUG)
            for item in to_rm:
                m_freed += 1
                try:
                    sto_msgs.remove(item)
                except Exception:
                    print_traceback(debug=DEBUG)
    logger.info((f'Scheduled garbage collection checked {u_checked} users, {m_checked} messages, '
                 f'freed {u_freed} users, {m_freed} messages.'))

if __name__ == '__main__':
    if USER_BOT_BACKEND:
        from userbot_backend import (kick_user, restrict_user, unban_user, delete_message,
                                     userbot_updater)
    else:
        from bot_backend import kick_user, restrict_user, unban_user, delete_message
    updater.job_queue.start()
    updater.job_queue.run_repeating(do_garbage_collection, GARBAGE_COLLENTION_INTERVAL)
    updater.dispatcher.add_error_handler(error_callback)
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('source', source))
    updater.dispatcher.add_handler(CommandHandler('admins', at_admins))
    updater.dispatcher.add_handler(CommandHandler('admin', at_admins))
    updater.dispatcher.add_handler(CommandHandler('settings', settings_menu))
    updater.dispatcher.add_handler(CommandHandler('cancel', settings_cancel))
    updater.dispatcher.add_handler(CallbackQueryHandler(challenge_verification, pattern=r'clg'))
    updater.dispatcher.add_handler(CallbackQueryHandler(settings_callback, pattern=r'settings'))
    updater.dispatcher.add_handler(MessageHandler(Filters.status_update.new_chat_members, new_mems))
    updater.dispatcher.add_handler(MessageHandler(InvertedFilter(Filters.status_update), new_messages))
    if USER_BOT_BACKEND:
        logger.info('Antispambot started with userbot backend.')
        try:
            userbot_updater.start()
            updater.start_polling()
            updater.idle()
        finally:
            userbot_updater.stop()
    else:
        logger.info('Antispambot started.')
        updater.start_polling()
        updater.idle()
