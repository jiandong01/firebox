class Configuration:
    def __init__(self, host="unix://var/run/docker.sock"):
        self.host = host
        # Add any other configuration parameters you need

    def get_default_copy(self):
        return Configuration(host=self.host)
