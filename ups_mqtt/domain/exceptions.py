class UpsDomainError(Exception):
    pass


class NutUnavailable(UpsDomainError):
    pass


class NutParseError(UpsDomainError):
    pass
