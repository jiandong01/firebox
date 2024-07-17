class Configuration:
    def __init__(self, host="unix://var/run/docker.sock"):
        self.host = host

    def get_default_copy(self):
        return Configuration(host=self.host)
