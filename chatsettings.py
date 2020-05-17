# These options can be changed per group
CHAT_SETTINGS = {
    'WELCOME_WORDS': [
        '新入群的用户，请在 %time% 秒内回答如下问题',
    ],

    'CLG_QUESTIONS': [
        ['archlinux 是一个 什么 GNU/Linux 发行版', '滚动', '滑动', '移动', '转动', '跳动', '活动', '浮动', '不动'],
        ['您进群的目的是什么', '学习交流', '发小广告', '垃圾信息', '炸群爆破'],
    ],

    'CHALLENGE_SUCCESS': [
        "验证成功。",
    ],

    'PERMISSION_DENY': [
        "您无需验证",
        "瞎点什么，没你什么事！",
        "点你妹！你就这么想被口球吗？",
    ],

    'CHALLENGE_TIMEOUT': 5*60,
    'MIN_CLG_TIME': 15,
    'UNBAN_TIMEOUT': 5*60,
    'FLOOD_LIMIT': 5,
}

CHAT_SETTINGS_HELP = {
    'WELCOME_WORDS': ("欢迎词", "设置欢迎词，其中%time%代表验证时间限制(秒)，多个选择请分多行输入"),
    'CLG_QUESTIONS': ("验证问题", "设置验证问题，格式为:\n问题\n正确答案\n错误答案\n(多个错误答案)"),
    'CHALLENGE_SUCCESS': ("验证成功消息", "验证成功时的弹窗消息，应为一段文字，多个选择请分多行输入"),
    'PERMISSION_DENY': ("无需验证消息", "无需验证时的弹窗消息，应为一段文字，多个选择请分多行输入"),
    'CHALLENGE_TIMEOUT': ("验证超时时间", "验证超时时间，单位为秒，范围为1到3600"),
    'MIN_CLG_TIME': ("动态最小验证时间", "动态验证时间的最小值，单位为秒，范围为0到验证超时时间"),
    'UNBAN_TIMEOUT': ("解封时间", "超时或者验证失败后的解封时间，单位为秒，设置为0或大于86400即为永久封禁"),
    'FLOOD_LIMIT': ("防止刷屏", "在验证超时时间内，超过一定数量的加群触发刷屏防护。设置为0为禁用，1为始终启用"),
}
