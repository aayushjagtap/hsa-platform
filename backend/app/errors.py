class DomainError(Exception):
    """Base for errors the API turns into a clean HTTP response."""

    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class ContributionLimitError(DomainError):
    status_code = 422
