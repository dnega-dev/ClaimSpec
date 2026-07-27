"""ClaimSpec exception hierarchy."""


class ClaimSpecError(Exception):
    """Base class for expected ClaimSpec errors."""


class ContractParseError(ClaimSpecError):
    """Raised when a contract cannot be parsed."""

    def __init__(self, message, source=None, line=None, column=None):
        self.message = message
        self.source = source
        self.line = line
        self.column = column
        location = ""
        if source:
            location = source
        if line is not None:
            location += (":" if location else "line ") + str(line)
            if column is not None:
                location += ":" + str(column)
        super().__init__((location + ": " if location else "") + message)


class TraceValidationError(ClaimSpecError):
    """Raised when a trace is not structurally valid."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("invalid trace: " + "; ".join(self.errors))


class ContractValidationError(ClaimSpecError):
    """Raised when a parsed contract is semantically invalid."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("invalid contract: " + "; ".join(self.errors))
