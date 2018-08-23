#!/usr/bin/env python3
# -*- coding: utf-8 -*-

token = "token_here"
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from datetime import datetime, timedelta
from time import time
from telegram.error import TelegramError, BadRequest
from mwt import MWT

logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

updater = Updater(token)

at_admins_ratelimit = 10*60
last_at_admins_dict = dict()

@MWT(timeout=60*60)
def getAdminIds(bot, chat_id):
    admin_ids = list()
    for chat_member in bot.get_chat_administrators(chat_id):
        admin_ids.append(chat_member.user.id)
    return admin_ids

@MWT(timeout=60*60)
def getAdminUsernames(bot, chat_id):
    admins = list()
    for chat_member in bot.get_chat_administrators(chat_id):
        if chat_member.user.username != bot.username:
            admins.append(chat_member.user.username)
    return admins


def start(bot, update):
    update.message.reply_text('你好{}，这个机器人会自动封禁新加入的bot以及拉入bot的用户，并等待管理员的审核。要让其正常工作，请将这个机器人添加进一个群组，设为管理员并打开封禁权限。'.format(update.message.from_user.first_name))
    logger.debug("Start from {0}".format(update.message.from_user.id))


def source(bot, update):
    update.message.reply_text('Source code: https://github.com/Jerry981028/antibotbot')
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


def ban_user(bot, chat_id, user, invite_user):
    bot_banned = False
    try:
        if bot.restrict_chat_member(chat_id=chat_id, user_id=user.id, until_date=datetime.utcnow()+timedelta(days=367)):
            bot_banned = True
            if bot.restrict_chat_member(chat_id=chat_id, user_id=invite_user.id, until_date=datetime.utcnow()+timedelta(days=367)):
                button = InlineKeyboardButton(text="解除封禁", callback_data="unban {0} {1}".format(user.id, invite_user.id))
                bot.send_message(chat_id=chat_id,
                        text="发现新加入的bot: {0} ，以及拉入bot的用户: {1} ，已经将其全部封禁。".format(display_username(user),
                                        display_username(invite_user)), parse_mode="Markdown")
                # Can't get the original message in markdown format. Bad implement.
                bot.send_message(chat_id=chat_id, text="如需解封请管理员点击下面的按钮。", reply_markup=InlineKeyboardMarkup([[button]]))
                logger.info("Banned {0} and {1} in the group {2}".format(user.id, invite_user.id, chat_id))
            else:
                raise TelegramError
        else:
            raise TelegramError
    except (TelegramError, BadRequest):
        if bot_banned:
            admin_ids = getAdminIds(bot, chat_id)
            if invite_user.id in admin_ids:
                unban_user(bot, [user.id], callback_mode=False, non_callback_chat_id=chat_id)
                logger.info("Admin {1} invited bot {0} in the group {2}".format(user.id, invite_user.id, chat_id))
            else:
                button = InlineKeyboardButton(text="解除封禁", callback_data="unban {0}".format(user.id))
                bot.send_message(chat_id=chat_id,
                        text="发现新加入的bot: {0} ，以及拉入bot的用户: {1} 。\n"
                                "由于未知原因拉入bot的用户无法封禁，已经将bot封禁。".format(display_username(user),
                                        display_username(invite_user)), parse_mode="Markdown")
                bot.send_message(chat_id=chat_id, text="如需解封请管理员点击下面的按钮。", reply_markup=InlineKeyboardMarkup([[button]]))
                logger.info("Banned {0} but not {1} in the group {2}".format(user.id, invite_user.id, chat_id))
        else:
            bot.send_message(chat_id=chat_id,
                    text="发现新加入的bot: {0} ，但机器人不是管理员导致无法实施有效行动。"
                            "请将机器人设为管理员并打开封禁权限。".format(display_username(user)),
                    parse_mode="Markdown")
            logger.info("Cannot ban {0} and {1} in the group {2}".format(user.id, invite_user.id, chat_id))


def unban_user(bot, unban_ids, update=None, callback_mode=True, non_callback_chat_id=None):
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
                logger.info("Unbanned {0} in the group {1}".format(unban_id, chat_id))
            else:
                raise TelegramError
        except TelegramError:
            logger.info("Cannot unban {0} in the group {1}".format(unban_id, chat_id))
            return
    if not callback_mode:
        return
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=message.message_id,
            text="解封成功。操作人 {0}".format(display_username(user, atuser=False)),
            parse_mode="Markdown",
            reply_markup=None)
    except:
        logger.info("Cannot remove keyboard in message {0} from the group {1}".format(message.message_id, chat_id))
    else:
        logger.debug("Removed keyboard in message {0} from the group {1}".format(message.message_id, chat_id))
    bot.answer_callback_query(callback_query_id=update.callback_query.id, text="解封成功。")


def handle_inline_result(bot, update):
    chat_id = update.callback_query.message.chat.id
    user = update.callback_query.from_user
    data = update.callback_query.data
    admin_ids = getAdminIds(bot, chat_id)
    if user.id not in admin_ids:
        logger.info("A non-admin user {0} (id: {1}) clicked the button from the group {2}".format(display_username(user, markdown=False), user.id, chat_id))
        bot.answer_callback_query(callback_query_id=update.callback_query.id, text="你没有权限执行此操作。")
        return
    args = data.split()
    unban_ids = args[1:]
    unban_user(bot, unban_ids, update)

def at_admins(bot, update):
    global last_at_admins_dict, at_admins_ratelimit
    chat_id = update.message.chat.id
    last_at_admins = 0
    if chat_id in last_at_admins_dict:
        last_at_admins = last_at_admins_dict[chat_id]
    job_queue = updater.job_queue
    if time() - last_at_admins < at_admins_ratelimit:
        notice = update.message.reply_text("请再等待 {0} 秒".format(at_admins_ratelimit - (time() - last_at_admins)))
        def delete_notice(bot, job):
            try:
                update.message.delete()
            except TelegramError:
                logger.info("Unable to delete at_admin spam message {0} from {1}".format(update.message.message_id, update.message.from_user.id))
            else:
                logger.info("Deleted at_admin spam messages {0} and {1} from {2}".format(update.message.message_id, notice.message_id, update.message.from_user.id))
            notice.delete()
        job_queue.run_once(delete_notice, 5)
        job_queue.start()
        return
    admins = getAdminUsernames(bot, chat_id)
    update.message.reply_text(" ".join("@"+a for a in admins))
    last_at_admins_dict[chat_id] = time()
    logger.info("At_admin sent from {0} {1}".format(update.message.from_user.id, chat_id))

def status_update(bot, update):
    chat_id = update.message.chat_id
    if update.message.new_chat_members:
        users = update.message.new_chat_members
        invite_user = update.message.from_user
        for user in users:
            if user.id == bot.id:
                logger.info("Myself joined the group {0}".format(chat_id))
            else:
                if user.is_bot:
                    ban_user(bot, chat_id, user, invite_user)
                else:
                    logger.debug("{0} joined the group {1}".format(user.id, chat_id))


updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('source', source))
updater.dispatcher.add_handler(CommandHandler('admins', at_admins))
updater.dispatcher.add_handler(CommandHandler('admin', at_admins))
updater.dispatcher.add_handler(CallbackQueryHandler(handle_inline_result, pattern=r'unban'))
updater.dispatcher.add_handler(MessageHandler(Filters.status_update, status_update))
updater.start_polling()
updater.idle()
