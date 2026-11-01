"""Errors named in the tool contracts (data/tools.md)."""


class ToolError(Exception):
    """Base class for errors raised by the supplied tools."""


class CustomerNotFound(ToolError):
    def __init__(self, customer_id: str) -> None:
        super().__init__(f"Unknown customer id: {customer_id}")
        self.customer_id = customer_id


class UpstreamTimeout(ToolError):
    def __init__(self, operation: str) -> None:
        super().__init__(f"Upstream timeout during {operation}")
        self.operation = operation


class InvalidCategory(ToolError):
    def __init__(self, category: str, allowed: list[str]) -> None:
        super().__init__(f"Invalid category {category!r}; expected one of {allowed}")
        self.category = category
        self.allowed = allowed
