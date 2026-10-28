"""Safe development backend. Hardware-unavailable mode never fabricates success."""
class MockTransport:
    def __init__(self):
        self.connected = False
        self.last_error = "Hardware backend not connected"

    def connect(self):
        return False

    def disconnect(self):
        self.connected = False

    def send(self, payload):
        return False

    def poll(self):
        return None
