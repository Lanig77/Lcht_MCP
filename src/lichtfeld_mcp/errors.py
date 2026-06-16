"""Domain exceptions for the Lichtfeld MCP server."""


class LichtfeldMCPError(RuntimeError):
    """Base error raised by the MCP adapter layer."""


class ProjectNotOpenError(LichtfeldMCPError):
    """Raised when a scene operation requires an open project."""


class UnsupportedTargetError(LichtfeldMCPError):
    """Raised when an optimization or export target is unsupported."""


class InvalidSelectionError(LichtfeldMCPError):
    """Raised when a selection cannot be applied."""
