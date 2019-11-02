# Antibotbot for Telegram groups
[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](./LICENSE)  

The bot is currently running as [@ArchCNAntiSpamBot](http://telegram.me/ArchCNAntiSpamBot).  

To run the bot yourself, you will need: 
- Python 3.7+
- The [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) module

## Deploying
### With bot api only
1. Get a bot [token](https://core.telegram.org/bots#6-botfather).  
2. Change TOKEN to the one you just got and SALT to whatever string you want inside [config.py](https://github.com/isjerryxiao/AntiSpamBot/blob/master/config.py#L2).  
3. You're ready to go. Install requirements with `pip3 install -r requirements.txt`    
   and then launch the bot with `python3 bot.py`.  

### With mtproto userbot api
#### This is only useful when you have an admin account with no add_new_admin permission.
1. Get a bot token and modify TOKEN as well as SALT inside config.py as mentioned above.  
2. Get the [API ID and hash](https://docs.telethon.dev/en/latest/basic/signing-in.html#signing-in) for your telegram user account.  
3. Put your api_id and hash [here](https://github.com/isjerryxiao/AntiSpamBot/blob/master/config.py#L51).  
4. Set [USER_BOT_BACKEND](https://github.com/isjerryxiao/AntiSpamBot/blob/master/config.py#L50) to `True`.  
5. You're ready to go. Install requirements with `pip3 install -r requirements-userbot.txt`    
   and then launch the bot with `python3 bot.py`.  
