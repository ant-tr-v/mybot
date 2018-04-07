import telegram as telega
import threading
import time
from mybot.ww6StatBotPlayer import Player

class PinOnlineKm:
    def __init__(self, squadids: dict, bot: telega.Bot, database):
        self.bot = bot
        self.mes = ""
        self.squadids = squadids
        self.squabyid = {v[1]: v[0] for v in self.squadids.items()}
        self.users = {}
        self.oderedkm = ['3', '7', '10', '12', '15', '19', '22', '29', '36']
        self.kms = {x: set() for x in self.oderedkm}
        self.kmspw = {x: 0 for x in self.oderedkm}
        self.power = {sq: 0 for sq in squadids.keys()}
        self.names = {sq: set() for sq in squadids.keys()}
        self.messages = {}
        self.connections = {}
        self.copies = {}
        self.usersbyname = {}
        self.chatm = {}
        self.db = database
        self.cooldownstate = False
        self.planUpdate = False
        self.chats_to_update = set()

    def pin(self, sq, admin_chat, chatmes=""):
        if not admin_chat in self.connections.keys():
            self.connect(admin_chat)
        self.update()
        if sq not in self.squadids.keys():
            self.bot.sendMessage(chat_id=admin_chat, text="Не знаю отряда " + sq)
            return
        self.chatm[sq] = chatmes
        if self.squadids[sq] in self.messages.keys():
            self.bot.sendMessage(chat_id=admin_chat, text="Пин уже в отряде " + sq)
            self.chats_to_update.add(self.squadids[sq])
            self.update()
            return
        kms = [x for x in self.oderedkm]
        markup = [[telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[:3]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[3:6]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[6:]]]
        text = "#пинонлайн\n" + self.mes + "<b>" + self.chatm[sq] + "</b>"
        chat_id = self.squadids[sq]
        id = self.bot.sendMessage(chat_id=chat_id, text=text,
                                  reply_markup=telega.InlineKeyboardMarkup(markup), parse_mode='HTML').message_id
        self.messages[chat_id] = id
        try:
            self.bot.pinChatMessage(chat_id=chat_id, message_id=id)
        except:
            self.bot.sendMessage(chat_id=admin_chat, text=("Не смог запинить в " + sq))
        self.bot.sendMessage(chat_id=admin_chat, text=("Опрос доставлен в " + sq))
        self.update()

    def add(self, player: Player, chat_id, km):
        if player.id in self.users.keys():
            if (chat_id != self.users[player.id]) and (player.username not in self.kms[km]):
                self.delete(player)
            else:
                return False
        self.users[player.id] = (chat_id, km)
        self.kms[km].add(player.username)
        self.usersbyname[player.username] = player.id
        ps = player.stats[4]
        sq = self.squabyid[chat_id]
        self.power[sq] += ps.attack + ps.hp + ps.deff + ps.agility + 10
        self.kmspw[km] += ps.attack + ps.hp + ps.deff + ps.agility + 10
        self.names[sq].add(player.username)
        self.chats_to_update.add(chat_id)
        self.update()
        return True

    def delete(self, player: Player):
        if player.id not in self.users.keys():
            return False
        sq = self.squabyid[self.users[player.id][0]]
        km = self.users[player.id][1]
        ps = player.stats[4]
        self.power[sq] -= (ps.attack + ps.hp + ps.deff + ps.agility + 10)
        self.kmspw[km] -= (ps.attack + ps.hp + ps.deff + ps.agility + 10)
        self.names[sq].discard(player.username)
        self.kms[km].discard(player.username)
        del (self.users[player.id])
        self.chats_to_update.add(self.squadids[sq])
        self.update()
        return True

    def text(self):
        s = "<b>Пины</b>\n"
        for m in self.chatm.items():
            s += " " + m[0] + ": <b>" + m[1] + "</b>\n"
        s += "<b>Силы на данный момент:</b>\n"
        for sq in self.power.keys():
            if self.squadids[sq] in self.messages.keys():
                s += sq + ": <b>" + str(self.power[sq]) + "</b>🕳 (" + str(len(self.names[sq])) + ") "
                if self.names[sq]:
                    s += "[@" + " @".join(self.names[sq]) + "]\n"
                else:
                    s += "\n"
        s += "<b>Локации</b>\n"
        for km in self.oderedkm:
            if self.kms[km]:
                s += " <b>" + km + "км</b> (" + str(len(self.kms[km])) + ") [" + str(
                    self.kmspw[km]) + "] @" + " @".join(self.kms[km]) + "\n"
            else:
                s += " <b>" + km + "км</b> (0) ---\n"
        return s

    def copy_to(self, chat_id):
        text = self.text()
        id = self.bot.sendMessage(chat_id=chat_id, text=text, parse_mode='HTML').message_id
        self.copies[chat_id] = id

    def connect(self, chat_id):
        markup = [[telega.InlineKeyboardButton(text="Закрыть пин", callback_data="offkm")]]
        text = self.text()
        id = self.bot.sendMessage(chat_id=chat_id, text=text,
                                  reply_markup=telega.InlineKeyboardMarkup(markup)).message_id
        self.connections[chat_id] = id

    def update_chat(self, chat_id):
        sq = self.squabyid[chat_id]
        text = "#пинонлайн\n" + self.mes + "<b>" + self.chatm[sq] + "</b>" + "\n\nонлайн (" + str(
            len(self.names[sq])) + ")\n"
        for km in self.oderedkm:
            l = [u for u in self.kms[km] if self.users[self.usersbyname[u]][0] == chat_id]
            if l != []:
                text += "<b>" + km + "км</b> (" + str(len(l)) + "): @" + " @".join(l) + "\n"
            else:
                text += "<b>" + km + "км</b> (0) ---\n"
        kms = [x for x in self.oderedkm]
        markup = [[telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[:3]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[3:6]],
                  [telega.InlineKeyboardButton(text=k + "км", callback_data="onkm " + k) for k in kms[6:]]]
        try:
            self.bot.editMessageText(chat_id=chat_id, message_id=self.messages[chat_id], text=text,
                                     reply_markup=telega.InlineKeyboardMarkup(markup), parse_mode='HTML')
        except:
            pass

    def unfreeze(self):
        self.cooldownstate = False

    def update(self):
        self.planUpdate = False
        if self.cooldownstate:
            if not self.planUpdate:
                threading.Timer(0.07, self.update).start()
                self.planUpdate = True
            return
        self.cooldownstate = True
        list = self.chats_to_update.copy()
        self.chats_to_update.clear()
        for chat in list:
            self.update_chat(chat)
            time.sleep(1. / 100)
        markup = [[telega.InlineKeyboardButton(text="Закрыть пин", callback_data="offkm")]]
        text = self.text()
        for con in self.connections.items():
            try:
                self.bot.editMessageText(chat_id=con[0], message_id=con[1], text=text,
                                         reply_markup=telega.InlineKeyboardMarkup(markup), parse_mode='HTML')
            except:
                pass
        for con in self.copies.items():
            try:
                self.bot.editMessageText(chat_id=con[0], message_id=con[1], text=text, parse_mode='HTML')
            except:
                pass
        threading.Timer(0.05, self.unfreeze).start()

    def close(self):
        for m in self.messages.items():
            try:
                self.bot.editMessageReplyMarkup(chat_id=m[0], message_id=m[1])
            except:
                pass
        self.update()
        for m in self.connections.items():
            try:
                self.bot.editMessageReplyMarkup(chat_id=m[0], message_id=m[1])
            except:
                pass
