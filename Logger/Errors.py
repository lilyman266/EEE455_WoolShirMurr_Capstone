class InvalidSendError(Exception):
    #sender should not be sending message
    def __init__(self, session, message=""):
        self.session = session
        super().__init__(message)


class InvalidReceiveError(Exception):
    #receiver should not be receiving message
    def __init__(self, session, message=""):
        self.session = session
        super().__init__(message)