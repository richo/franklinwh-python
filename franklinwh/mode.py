MODE_TIME_OF_USE = "time_of_use"
MODE_SELF_CONSUMPTION = "self_consumption"
MODE_EMERGENCY_BACKUP = "emergency_backup"

MODE_MAP = {
        9322: MODE_TIME_OF_USE,
        9323: MODE_SELF_CONSUMPTION,
        9324: MODE_EMERGENCY_BACKUP,
        }

class Mode(object):
    @staticmethod
    def time_of_use(soc=20):
        mode = Mode(soc)
        mode.currendId = 9322
        mode.workMode = 1
        return mode

    @staticmethod
    def emergency_backup(soc=100):
        mode = Mode(soc)
        mode.currendId = 9324
        mode.workMode = 3
        return mode

    @staticmethod
    def self_consumption(soc=20):
        mode = Mode(soc)
        mode.currendId = 9323
        mode.workMode = 2
        return mode

    def __init__(self, soc):
        self.soc = soc
        self.currendId = None
        self.workMode = None

    def payload(self, gateway):
        return {
                "currendId": str(self.currendId),
                "gatewayId": gateway,
                "lang": "EN_US",
                "oldIndex": "1", # Who knows if this matters
                "soc": str(self.soc),
                "stromEn": "1",
                "workMode": str(self.workMode),
                }
