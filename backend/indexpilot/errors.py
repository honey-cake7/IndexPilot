class DomainError(Exception):
    """User-safe domain failure; never include raw SQL, parameters or driver text."""

    def __init__(self, code: str, message: str, status: int = 422):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)
