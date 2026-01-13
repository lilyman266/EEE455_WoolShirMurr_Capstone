class Session:
    def __init__(self, DLL_rx, DLL_tx):
        self.reader = DLL_rx
        self.writer = DLL_tx




class ConnectedUplink(Session):
    pass

class GroundStationConnectedUplink(ConnectedUplink):
    pass

class AudimusConnectedUplink(ConnectedUplink):
    pass




class ConnectedDownlink(Session):
    pass

class GroundStationConnectedDownlink(ConnectedDownlink):
    pass

class AudimusConnectedDownlink(ConnectedDownlink):
    pass



class ConnectionlessDownlink(Session):
    pass

class GroundStationConnectionlessDownlink():
    pass

class AudimusConnectionlessDownlink():
    pass


