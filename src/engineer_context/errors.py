"""Provider failures, kept importable without transport dependencies."""


class ProviderError(ValueError):
    def __init__(self, status, reason):
        self.status = status
        self.reason = reason
        super().__init__(reason)


class InvalidCodeRequest(ValueError):
    """The owning contract rejected the request: caller input, not a gap."""
