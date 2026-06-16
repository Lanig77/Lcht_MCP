"""Domain exceptions for the Lichtfeld MCP server."""


class LichtfeldMCPError(RuntimeError):
    """Base error raised by the MCP adapter layer."""


class ProjectNotOpenError(LichtfeldMCPError):
    """Raised when a scene operation requires an open project."""


class UnsupportedTargetError(LichtfeldMCPError):
    """Raised when an optimization or export target is unsupported."""


class InvalidSelectionError(LichtfeldMCPError):
    """Raised when a selection cannot be applied."""


class InvalidPathError(LichtfeldMCPError):
    """Raised when a required path input is empty or malformed."""


class UnsupportedUnitError(LichtfeldMCPError):
    """Raised when a measurement unit is unsupported."""


class InvalidParameterError(LichtfeldMCPError):
    """Raised when a numeric or bounded parameter is invalid."""


class AdapterUnavailableError(LichtfeldMCPError):
    """Raised when a configured backend adapter cannot be used in this runtime."""
