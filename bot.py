#!/usr/bin/env python3
# -*- coding: utf-8 -*-

token = "token_here"

VER = '20190524'
WELCOME_WORDS = ['{}: 为防止垃圾信息泛滥，请在5分钟内完成验证',
                 '{}: 本群组启用了加群验证，请在5分钟内完成验证'
                ]
# challenge words
CLG_DENY = ['把我踢了吧',
            '我是来发广告的',
            '我进错群了'
           ]
CLG_ACCEPT = ['点这里完成验证',
              '我不是机器人'
             ]
# please change
SALT = 'whatever'



import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, run_async
from datetime import datetime, timedelta
from time import time
from telegram.error import TelegramError, BadRequest
from mwt import MWT
from threading import Lock
from random import choice, randint, shuffle
from hashlib import md5, sha256

logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

updater = Updater(token)

at_admins_ratelimit = 10*60
last_at_admins_dict = dict()

class PendingChallengeManager:
    pending = dict()
    unban_pending = list()
    ticklock = Lock()
    def __init__(self, timeout=5*60, utimeout=30*60):
        self.timeout = timeout
        self.utimeout = utimeout
    def add(self, chat_id, user_id, invite_user_id, message_id, join_msgid):
        self.pending[(chat_id, message_id)] = (user_id, invite_user_id, int(time()), join_msgid)
    def remove(self, chat_id, message_id):
        try:
            del self.pending[(chat_id, message_id)]
        except KeyError:
            logger.error('Unable to delete {} from Pending Challenges.'.format((chat_id, message_id)))
    def add_unban(self, user_id, chat_id):
        self.unban_pending.append((user_id, chat_id, time()))
    def tick(self, bot, job):
        if not self.ticklock.acquire(0):
            return
        try:
            logger.debug('tick!')
            timenow = int(time())
            removable = list()
            for key in self.pending:
                (chat_id, message_id) = key
                (user_id, _, challenge_time, join_msgid) = self.pending[key]
                if timenow - challenge_time >= self.timeout:
                    logger.debug('Removing user {0} form {1} due to timeout.'.format(user_id, chat_id))
                    try:
                        kick_user(bot, [user_id], None, challenge=True, callback_mode=False,
                                  ncb_chat_id=chat_id, ncb_message_id=message_id)
                    except:
                        logger.error('Unable to removing user {0} form {1}'.format(user_id, chat_id))
                    try:
                        bot.delete_message(chat_id=chat_id, message_id=join_msgid)
                    except:
                        logger.info('Unable to delete enter message for {0} form {1}'.format(user_id, chat_id))
                    removable.append(key)
            for key in removable:
                self.remove(*key)

            removable = list()
            for unban in self.unban_pending:
                (user_id, chat_id, r_time) = unban
                if timenow - r_time >= self.utimeout:
                    try:
                        unban_user(bot, [user_id], callback_mode=False, non_callback_chat_id=chat_id, reason="Timeout.")
                    except:
                        logger.error('Unable to unban user {0} form {1}'.format(user_id, chat_id))
                    removable.append(unban)
            for key in removable:
                self.unban_pending.remove(key)
        finally:
            self.ticklock.release()

pcmgr = PendingChallengeManager(timeout=5*60, utimeout=30*60)

job_queue = updater.job_queue
job_queue.start()
job_queue.run_repeating(pcmgr.tick, 60)

class FakeMessage:
    def __init__(self, message_id):
        self.message_id = message_id

@MWT(timeout=60*60)
def getAdminIds(bot, chat_id):
    admin_ids = list()
    for chat_member in bot.get_chat_administrators(chat_id):
        admin_ids.append(chat_member.user.id)
    return admin_ids

@MWT(timeout=60*60)
def getAdminUsernames(bot, chat_id, markdown=False):
    admins = list()
    for chat_member in bot.get_chat_administrators(chat_id):
        if markdown:
            if chat_member.user.username != bot.username:
                admins.append(chat_member.user.mention_markdown(name=chat_member.user.name))
        else:
            if chat_member.user.username and chat_member.user.username != bot.username:
                admins.append(chat_member.user.username)
    return admins


def start(bot, update):
    update.message.reply_text('你好{}，机器人目前功能如下:\n'
                              '1.新加群用户需要在5分钟内点击按钮验证，否则将封禁30分钟。\n'
                              '2.会自动封禁新加入的bot以及拉入bot的用户，并等待管理员的审核。\n'
                              '要让其正常工作，请将这个机器人添加进一个群组，'
                              '设为管理员并打开封禁权限。'.format(update.message.from_user.first_name))
    logger.debug("Start from {0}".format(update.message.from_user.id))


def source(bot, update):
    update.message.reply_text('Source code: https://github.com/isjerryxiao/AntiSpamBot\nVersion: {}'.format(VER))
    logger.debug("Source from {0}".format(update.message.from_user.id))


def display_username(user, atuser=True, shorten=False, markdown=True):
    """
        atuser and shorten has no effect if markdown is True.
    """
    name = user.full_name
    if markdown:
        mdtext = user.mention_markdown(name=user.full_name)
        return mdtext
    if shorten:
        return name
    if user.username:
        if atuser:
            name += " (@{})".format(user.username)
        else:
            name += " ({})".format(user.username)
    return name


def antibot_ban_user(bot, chat_id, user, invite_user):
    bot_banned = False
    try:
        if bot.restrict_chat_member(chat_id=chat_id, user_id=user.id, until_date=datetime.utcnow()+timedelta(days=367)):
            bot_banned = True
            if bot.restrict_chat_member(chat_id=chat_id, user_id=invite_user.id, until_date=datetime.utcnow()+timedelta(days=367)):
                buttons = [InlineKeyboardButton(text="解除封禁", callback_data="unban {0} {1}".format(user.id, invite_user.id)),
                           InlineKeyboardButton(text="移除并封禁", callback_data="kick {0} {1}".format(user.id, invite_user.id))]
                bot.send_message(chat_id=chat_id,
                        text="发现新加入的bot: {0} ，以及拉入bot的用户: {1} ，已经将其全部封禁。\n"
                             "请管理员点击下面的按钮执行操作。".format(display_username(user), display_username(invite_user)),
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([buttons]))
                logger.info("Banned {0} and {1} in the group {2}".format(user.id, invite_user.id, chat_id))
            else:
                raise TelegramError
        else:
            raise TelegramError
    except (TelegramError, BadRequest):
        if bot_banned:
            admin_ids = getAdminIds(bot, chat_id)
            if invite_user.id in admin_ids:
                unban_user(bot, [user.id], callback_mode=False, non_callback_chat_id=chat_id, reason='Admin invited.')
                logger.info("Admin {1} invited bot {0} in the group {2}".format(user.id, invite_user.id, chat_id))
            else:
                # bad code. consider removing
                buttons = [InlineKeyboardButton(text="解除封禁", callback_data="unban {0}".format(user.id)),
                                    InlineKeyboardButton(text="移除并封禁", callback_data="kick {0}".format(user.id))]
                bot.send_message(chat_id=chat_id,
                        text="发现新加入的bot: {0} ，以及拉入bot的用户: {1} 。\n"
                             "由于未知原因拉入bot的用户无法封禁，已经将bot封禁。\n"
                             "请管理员点击下面的按钮执行操作。".format(display_username(user), display_username(invite_user)),
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([buttons]))
                logger.error("Banned {0} but not {1} in the group {2}".format(user.id, invite_user.id, chat_id))
        else:
            bot.send_message(chat_id=chat_id,
                    text="发现新加入的bot: {0} ，但机器人不是管理员导致无法实施有效行动。"
                         "请将机器人设为管理员并打开封禁权限。".format(display_username(user)),
                    parse_mode="Markdown")
            logger.error("Cannot ban {0} and {1} in the group {2}".format(user.id, invite_user.id, chat_id))


def kick_user(bot, kick_ids, update, challenge=False, kick_by_admin=False, callback_mode=True, ncb_message_id=None, ncb_chat_id=None):
    if callback_mode:
        chat_id = update.callback_query.message.chat.id
        message = update.callback_query.message
        user = update.callback_query.from_user
    else:
        assert(ncb_message_id and ncb_chat_id and challenge)
        chat_id = ncb_chat_id
        message = FakeMessage(ncb_message_id)
    for kick_id in kick_ids:
        try:
            if bot.kick_chat_member(chat_id=chat_id, user_id=kick_id, until_date=datetime.utcnow()+timedelta(days=367)):
                logger.info("Kicked {0} in the group {1}".format(kick_id, chat_id))
                if challenge and (kick_by_admin is False):
                    pcmgr.add_unban(kick_id, chat_id)
            else:
                raise TelegramError
        except TelegramError:
            logger.error("Cannot kick {0} in the group {1}".format(kick_id, chat_id))
            return
    if challenge:
        try:
            bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except:
            logger.error("Cannot delete challenge message {0} from the group {1}".format(message.message_id, chat_id))
        else:
            logger.debug("Deleted challenge message {0} from the group {1}".format(message.message_id, chat_id))
    else:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=message.message_id,
                text=message.text_markdown + "\n\n移除成功。操作人 {0}".format(display_username(user, atuser=False)),
                parse_mode="Markdown",
                reply_markup=None)
        except:
            logger.error("Cannot remove keyboard in message {0} from the group {1}".format(message.message_id, chat_id))
        else:
            logger.debug("Removed keyboard in message {0} from the group {1}".format(message.message_id, chat_id))
        bot.answer_callback_query(callback_query_id=update.callback_query.id, text="移除成功。")


def unban_user(bot, unban_ids, update=None, callback_mode=True, non_callback_chat_id=None, challenge=False, reason="None"):
    if not callback_mode:
        assert update == None
        chat_id = non_callback_chat_id
    else:
        chat_id = update.callback_query.message.chat.id
        message = update.callback_query.message
        user = update.callback_query.from_user
    for unban_id in unban_ids:
        try:
            if bot.restrict_chat_member(chat_id=chat_id, user_id=unban_id,
                    can_send_messages=True, can_send_media_messages=True,
                    can_send_other_messages=True, can_add_web_page_previews=True):
                logger.info("Unbanned {0} in the group {1}, reason: {2}".format(unban_id, chat_id, reason))
            else:
                raise TelegramError
        except TelegramError:
            logger.error("Cannot unban {0} in the group {1}".format(unban_id, chat_id))
            return
    if not callback_mode:
        return
    if challenge:
        try:
            bot.answer_callback_query(callback_query_id=update.callback_query.id, text="验证成功。", show_alert=True)
            bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except:
            logger.error("Cannot remove challenge message {0} from the group {1}".format(message.message_id, chat_id))
        else:
            logger.debug("Removed challenge message {0} from the group {1}".format(message.message_id, chat_id))
    else:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=message.message_id,
                text=message.text_markdown + "\n\n解封成功。操作人 {0}".format(display_username(user, atuser=False)),
                parse_mode="Markdown",
                reply_markup=None)
        except:
            logger.error("Cannot remove keyboard in message {0} from the group {1}".format(message.message_id, chat_id))
        else:
            logger.debug("Removed keyboard in message {0} from the group {1}".format(message.message_id, chat_id))
        bot.answer_callback_query(callback_query_id=update.callback_query.id, text="解封成功。")

def challenge_verification(bot, update):
    chat_id = update.callback_query.message.chat.id
    user = update.callback_query.from_user
    message_id = update.callback_query.message.message_id
    data = update.callback_query.data
    args = data.split()
    if not (args and len(args) == 5):
        logger.error('Wrong Inline challenge data length. ' + str(data))
        return
    (r_user_id, invite_user_id, join_msgid) = args[2:]
    admin_ids = getAdminIds(bot, chat_id)
    expected_callbacks = challenge_gen_pw(r_user_id, join_msgid)
    if user.id in admin_ids or int(r_user_id) == int(user.id) or int(invite_user_id) == int(user.id):
        if args[1] != expected_callbacks[1]:
            if args[1] != expected_callbacks[0]:
                logger.error('Wrong Inline challenge action, kicked.' + str(data))
            kick_by_admin = True if user.id in admin_ids else False
            kick_user(bot, [r_user_id], update, challenge=True, callback_mode=True, kick_by_admin=kick_by_admin)
            try:
                bot.delete_message(chat_id=chat_id, message_id=join_msgid)
            except:
                logger.info('Unable to delete enter message for {0} form {1}'.format(r_user_id, chat_id))
        else:
            unban_user(bot, [r_user_id], update, challenge=True, callback_mode=True, reason='Challenge passed.')
        pcmgr.remove(chat_id, message_id)
    else:
        logger.info("Naughty user {0} (id: {1}) clicked {3} "
                    "from the group {2}".format(display_username(user, markdown=False),
                                                user.id, chat_id, " ".join(data)))
        bot.answer_callback_query(callback_query_id=update.callback_query.id,
                                  text="点你妹！你就这么想被口球吗？",
                                  show_alert=True)

def handle_inline_result_unban(*args):
    handle_inline_result(*args, action_type=0)

def handle_inline_result_kick(*args):
    handle_inline_result(*args, action_type=1)

def handle_inline_result(bot, update, action_type=0):
    """
        action_type: unban=0 ; kick=1
    """
    chat_id = update.callback_query.message.chat.id
    user = update.callback_query.from_user
    data = update.callback_query.data
    admin_ids = getAdminIds(bot, chat_id)
    if user.id not in admin_ids:
        logger.info("A non-admin user {0} (id: {1}) clicked the button from the group {2}".format(display_username(user, markdown=False), user.id, chat_id))
        bot.answer_callback_query(callback_query_id=update.callback_query.id, text="你没有权限执行此操作。")
        return
    args = data.split()
    target_ids = args[1:]
    if action_type:
        kick_user(bot, target_ids, update)
    else:
        unban_user(bot, target_ids, update, reason='Admin Unbanned.')

def challenge_gen_pw(user_id, join_msgid):
    callbacks = list()
    for action in ("kick", "pass"):
        pw = "{}{}{}{}".format(SALT, user_id, join_msgid, action)
        pw_sha256 = sha256(pw.encode('utf-8', errors='ignore')).hexdigest()
        pw_sha256_md5 = md5(pw_sha256.encode('utf-8', errors='ignore')).hexdigest()
        callbacks.append(pw_sha256_md5)
    return callbacks

def simple_challenge(bot, chat_id, user, invite_user, join_msgid):
    try:
        if bot.restrict_chat_member(chat_id=chat_id, user_id=user.id, until_date=datetime.utcnow()+timedelta(days=367)):
            btn_callbacks = challenge_gen_pw(user.id, join_msgid)
            buttons = [[InlineKeyboardButton(text=choice(CLG_DENY), callback_data = \
                            "clg {kick_cb} {0} {1} {2}".format(user.id, invite_user.id, join_msgid, kick_cb=btn_callbacks[0]))
                       ],
                       [InlineKeyboardButton(text=choice(CLG_ACCEPT), callback_data = \
                            "clg {pass_cb} {0} {1} {2}".format(user.id, invite_user.id, join_msgid, pass_cb=btn_callbacks[1]))
                       ]
                      ]
            shuffle(buttons)
            msg = bot.send_message(chat_id=chat_id,
                    text=choice(WELCOME_WORDS).format(display_username(user)),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(buttons))
            pcmgr.add(chat_id, user.id, invite_user.id, msg.message_id, join_msgid)
        else:
            raise TelegramError
    except (TelegramError, BadRequest):
        bot.send_message(chat_id=chat_id,
                text="发现新加入的成员: {0} ，但机器人不是管理员导致无法实施有效行动。"
                     "请将机器人设为管理员并打开封禁权限。".format(display_username(user)),
                parse_mode="Markdown")
        logger.error("Cannot ban {0} and {1} in the group {2}".format(user.id, invite_user.id, chat_id))


def at_admins(bot, update):
    if update.message.chat.type in ('private', 'channel'):
        return
    global last_at_admins_dict, at_admins_ratelimit
    chat_id = update.message.chat.id
    last_at_admins = 0
    if chat_id in last_at_admins_dict:
        last_at_admins = last_at_admins_dict[chat_id]
    if time() - last_at_admins < at_admins_ratelimit:
        notice = update.message.reply_text("请再等待 {0} 秒".format(at_admins_ratelimit - (time() - last_at_admins)))
        def delete_notice(bot, job):
            try:
                update.message.delete()
            except TelegramError:
                logger.error("Unable to delete at_admin spam message {0} from {1}".format(update.message.message_id, update.message.from_user.id))
            else:
                logger.info("Deleted at_admin spam messages {0} and {1} from {2}".format(update.message.message_id, notice.message_id, update.message.from_user.id))
            notice.delete()
        job_queue.run_once(delete_notice, 5)
        return
    admins = getAdminUsernames(bot, chat_id, markdown=True)
    if admins:
        update.message.reply_text("  ".join(admins), parse_mode='Markdown')
    last_at_admins_dict[chat_id] = time()
    logger.info("At_admin sent from {0} {1}".format(update.message.from_user.id, chat_id))

@run_async
def status_update(bot, update):
    if update.message.chat.type in ('private', 'channel'):
        return
    chat_id = update.message.chat_id
    if update.message.new_chat_members:
        users = update.message.new_chat_members
        invite_user = update.message.from_user
        for user in users:
            if user.id == bot.id:
                logger.info("Myself joined the group {0}".format(chat_id))
            else:
                if user.is_bot:
                    antibot_ban_user(bot, chat_id, user, invite_user)
                else:
                    logger.debug("{0} joined the group {1}".format(user.id, chat_id))
                    if invite_user.id != user.id and invite_user.id in getAdminIds(bot, chat_id):
                        # An admin invited him.
                        pass
                    else:
                        simple_challenge(bot, chat_id, user, invite_user, update.message.message_id)

if __name__ == '__main__':
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('source', source))
    updater.dispatcher.add_handler(CommandHandler('admins', at_admins))
    updater.dispatcher.add_handler(CommandHandler('admin', at_admins))
    updater.dispatcher.add_handler(CallbackQueryHandler(challenge_verification, pattern=r'clg'))
    updater.dispatcher.add_handler(CallbackQueryHandler(handle_inline_result_unban, pattern=r'unban'))
    updater.dispatcher.add_handler(CallbackQueryHandler(handle_inline_result_kick, pattern=r'kick'))
    updater.dispatcher.add_handler(MessageHandler(Filters.status_update, status_update))
    updater.start_polling()
    updater.idle()
