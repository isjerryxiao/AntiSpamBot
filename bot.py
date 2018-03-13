#!/usr/bin/env python3
# -*- coding: utf-8 -*-

token = "token_here"
import logging
from re import match as re_match
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from datetime import datetime, timedelta
from telegram.error import TelegramError

logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

updater = Updater(token)


def start(bot, update):
    update.message.reply_text('你好{}，这个机器人会自动封禁新加入的bot，并等待管理员的审核。要让其正常工作，请将这个机器人添加进一个群组，设为管理员并打开封禁权限。'.format(update.message.from_user.first_name))
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


def kick_user(bot, chat_id, user):
    user_id = user.id
    try:
        if bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, until_date=datetime.utcnow()+timedelta(days=367)):
            button = InlineKeyboardButton(text="解除封禁", callback_data="unban {0}".format(user_id))
            bot.sendMessage(chat_id=chat_id,
                    text="发现新加入的bot: {0} ，已经将其封禁。"
                            "如需解封请管理员点击下面的按钮。".format(display_username(user)),
                    reply_markup=InlineKeyboardMarkup([[button]]))
            logger.info("Banned {0} in the group {1}".format(user_id, chat_id))
        else:
            raise TelegramError
    except TelegramError:
        bot.sendMessage(chat_id=chat_id,
                text="发现新加入的bot: {0} ，但机器人不是管理员导致无法实施有效行动。"
                        "请将机器人设为管理员并打开封禁权限。".format(display_username(user)))
        logger.info("Cannot ban {0} in the group {1}".format(user_id, chat_id))

def handle_inline_result(bot, update):
    chat_id = update.callback_query.message.chat.id
    message_id = update.callback_query.message.message_id
    user = update.callback_query.from_user
    data = update.callback_query.data
    bot_id = ""
    admin_ids = list()
    for chat_member in bot.get_chat_administrators(chat_id):
        admin_ids.append(chat_member.user.id)
    if user.id not in admin_ids:
        logger.info("A non-admin user {0} (id: {1}) clicked the button from the group {2}".format(display_username(user), user.id, chat_id))
        bot.answer_callback_query(callback_query_id=update.callback_query.id, text="你没有权限执行此操作。")
        return
    try:
        bot_id = re_match(r'unban ([0-9]+)', data).group(1)
        bot.restrict_chat_member(chat_id=chat_id, user_id=bot_id,
                can_send_messages=True, can_send_media_messages=True,
                can_send_other_messages=True, can_add_web_page_previews=True)
    except:
        if len(bot_id):
            logger.info("Cannot unban {0} in the group {1}".format(bot_id, chat_id))
        else:
            logger.info("Cannot unban someone in the group {0}".format(chat_id))
        return
    bot.sendMessage(chat_id=chat_id,
        text="解封成功。"
                "操作人 {0}".format(display_username(user, atuser=False)), reply_to_message_id=message_id)
    logger.info("Unbanned {0} in the group {1}".format(bot_id, chat_id))
    try:
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
    except:
        logger.info("Cannot remove keyboard in message {0} from the group {1}".format(message_id, chat_id))
    else:
        logger.debug("Removed keyboard in message {0} from the group {1}".format(message_id, chat_id))

def status_update(bot, update):
    chat_id = update.message.chat_id
    if update.message.new_chat_members:
        users = update.message.new_chat_members
        for user in users:
            if user.id == bot.id:
                logger.info("Myself joined the group {0}".format(chat_id))
            else:
                if user.is_bot:
                    kick_user(bot, chat_id, user)
                else:
                    logger.debug("{0} joined the group {1}".format(user.id, chat_id))


updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('source', source))
updater.dispatcher.add_handler(CallbackQueryHandler(handle_inline_result, pattern=r'unban [0-9]+'))
updater.dispatcher.add_handler(MessageHandler(Filters.status_update, status_update))
updater.start_polling()
updater.idle()
