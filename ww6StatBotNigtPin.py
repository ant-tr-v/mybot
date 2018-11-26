class NightPin:
    def __init__(self):
        self.players_all = []
        self.players_unknown = []
        self.players_going = []
        self.players_onkm = []
        self.players_declined = []
        self.km = -1
        self.active = False

    def open(self, km):
        self.km = km
        self.active = True

    def close(self):
        self.players_all.clear()
        self.players_unknown.clear()
        self.players_going.clear()
        self.players_onkm.clear()
        self.players_declined.clear()
        self.km = -1
        self.active = False

    def add(self, players):
        self.players_unknown.extend(players)
        self.players_all.extend(players)

    def set_going(self, player):
        if player in self.players_unknown:
            self.players_unknown.remove(player)
        if player in self.players_onkm:
            self.players_onkm.remove(player)
        if player in self.players_declined:
            self.players_declined.remove(player)
        if player not in self.players_going:
            self.players_going.append(player)

    def set_declined(self, player):
        if player in self.players_unknown:
            self.players_unknown.remove(player)
        if player in self.players_onkm:
            self.players_onkm.remove(player)
        if player in self.players_going:
            self.players_going.remove(player)
        if player not in self.players_declined:
            self.players_declined.append(player)

    def set_onkm(self, player):
        if player in self.players_unknown:
            self.players_unknown.remove(player)
        if player in self.players_declined:
            self.players_declined.remove(player)
        if player in self.players_going:
            self.players_going.remove(player)
        if player not in self.players_onkm:
            self.players_onkm.append(player)