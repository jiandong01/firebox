class ApiException(Exception):
    def __init__(self, status=None, reason=None, http_resp=None):
        self.status = status
        self.reason = reason
        self.body = None
        self.headers = None
        if http_resp:
            self.status = http_resp.status
            self.reason = http_resp.reason
            self.body = http_resp.data
            self.headers = http_resp.getheaders()


class NotFoundException(ApiException):
    pass


class UnauthorizedException(ApiException):
    pass


class ForbiddenException(ApiException):
    pass
