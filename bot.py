#!/usr/bin/env python3
# -*- coding: utf-8 -*-

token = "token_here"
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from datetime import datetime, timedelta
from telegram.error import TelegramError

logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

updater = Updater(token)


def start(bot, update):
    update.message.reply_text('你好{}，这个机器人会自动封禁新加入的bot以及拉入bot的用户，并等待管理员的审核。要让其正常工作，请将这个机器人添加进一个群组，设为管理员并打开封禁权限。'.format(update.message.from_user.first_name))
    logger.debug("Start from {0}".format(update.message.from_user.id))


def source(bot, update):
    update.message.reply_text('Source code: https://github.com/Jerry981028/antibotbot')
    logger.debug("Source from {0}".format(update.message.from_user.id))


def display_username(user, atuser=True, shorten=False):
    if user.first_name and user.last_name:
        name = "{} {}".format(user.first_name, user.last_name)
    else:
        name = user.first_name
    if shorten:
        return name
    if user.username:
        if atuser:
            name += " (@{})".format(user.username)
        else:
            name += " ({})".format(user.username)
    return name


def ban_user(bot, chat_id, user, euser):
    try:
        if bot.restrict_chat_member(chat_id=chat_id, user_id=user.id, until_date=datetime.utcnow()+timedelta(days=367)) and \
                    bot.restrict_chat_member(chat_id=chat_id, user_id=euser.id, until_date=datetime.utcnow()+timedelta(days=367)):
            button = InlineKeyboardButton(text="解除封禁", callback_data="unban {0} {1}".format(user.id, euser.id))
            bot.send_message(chat_id=chat_id,
                    text="发现新加入的bot: {0} ，以及拉入bot的用户: {1} ，已经将其全部封禁。"
                            "如需解封请管理员点击下面的按钮。".format(display_username(user), display_username(euser)),
                            reply_markup=InlineKeyboardMarkup([[button]]))
            logger.info("Banned {0} and {1} in the group {2}".format(user.id, euser.id, chat_id))
        else:
            raise TelegramError
    except TelegramError:
        bot.send_message(chat_id=chat_id,
                text="发现新加入的bot: {0} ，但机器人不是管理员导致无法实施有效行动。"
                        "请将机器人设为管理员并打开封禁权限。".format(display_username(user)))
        logger.info("Cannot ban {0} in the group {1}".format(user.id, chat_id))


def unban_user(bot, unban_ids, update):
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
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text=message.text + "\n\n解封成功。操作人 {0}".format(display_username(user, atuser=False)), reply_markup=None)
    except:
        logger.info("Cannot remove keyboard in message {0} from the group {1}".format(message.message_id, chat_id))
    else:
        logger.debug("Removed keyboard in message {0} from the group {1}".format(message.message_id, chat_id))
    bot.answer_callback_query(callback_query_id=update.callback_query.id, text="解封成功。")


def handle_inline_result(bot, update):
    chat_id = update.callback_query.message.chat.id
    user = update.callback_query.from_user
    data = update.callback_query.data
    admin_ids = list()
    for chat_member in bot.get_chat_administrators(chat_id):
        admin_ids.append(chat_member.user.id)
    if user.id not in admin_ids:
        logger.info("A non-admin user {0} (id: {1}) clicked the button from the group {2}".format(display_username(user), user.id, chat_id))
        bot.answer_callback_query(callback_query_id=update.callback_query.id, text="你没有权限执行此操作。")
        return
    args = data.split()
    unban_ids = args[1:]
    unban_user(bot, unban_ids, update)

def at_admins(bot, update):
    chat_id = update.message.chat.id
    admins = list()
    for chat_member in bot.get_chat_administrators(chat_id):
        if chat_member.user.username != bot.username:
            admins.append(chat_member.user.username)
    update.message.reply_text(" ".join("@"+a for a in admins))

def status_update(bot, update):
    chat_id = update.message.chat_id
    if update.message.new_chat_members:
        users = update.message.new_chat_members
        euser = update.effective_user
        for user in users:
            if user.id == bot.id:
                logger.info("Myself joined the group {0}".format(chat_id))
            else:
                if user.is_bot:
                    ban_user(bot, chat_id, user, euser)
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
