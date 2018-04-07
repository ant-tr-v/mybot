import time


def send_split(bot, msg, chat_id, N):
    split = msg.split('\n')
    for i in range(0, len(split), N):
        time.sleep(1. / 30)
        bot.sendMessage(chat_id=chat_id, text='\n'.join(split[i:min(i + N, len(split))]), parse_mode='HTML',
                        disable_web_page_preview=True)


def pin(bot, chat_id, text, uid):
    id = -1
    try:
        id = bot.sendMessage(chat_id=chat_id, text=text, parse_mode='HTML').message_id
    except:
        bot.sendMessage(chat_id=uid, text="Не удалось доставить сообщение")
    time.sleep(0.5)
    try:
        bot.pinChatMessage(chat_id=chat_id, message_id=id)
    except:
        bot.sendMessage(chat_id=uid, text="Я не смог запинить((")
        return
    bot.sendMessage(chat_id=uid, text="Готово\nСообщение в пине")
