from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from docent.core.tool import Tool

_REGISTRY: dict[str, type[Tool]] = {}
_RESERVED_NAMES = frozenset({"list", "info", "config", "version"})

T = TypeVar("T", bound=Tool)


def register_tool(cls: type[T]) -> type[T]:
    """Decorator: validate a Tool subclass and add it to the registry.

    Registers the *class*, not an instance. Instances are created per
    invocation by the caller (CLI command, UI request handler, etc.) so
    tool runs never share mutable state.
    """
    if not isinstance(cls, type) or not issubclass(cls, Tool):
        raise TypeError(
            f"@register_tool must decorate a Tool subclass; got {cls!r}"
        )

    for attr in ("name", "description", "input_schema"):
        if not hasattr(cls, attr):
            raise TypeError(
                f"Tool {cls.__name__} is missing required class attribute '{attr}'"
            )

    if not isinstance(cls.name, str) or not cls.name:
        raise TypeError(
            f"Tool {cls.__name__}.name must be a non-empty string"
        )

    if cls.name in _RESERVED_NAMES:
        raise ValueError(
            f"Tool name '{cls.name}' is reserved for a built-in CLI command; choose another"
        )

    if not isinstance(cls.input_schema, type) or not issubclass(cls.input_schema, BaseModel):
        raise TypeError(
            f"Tool {cls.__name__}.input_schema must be a Pydantic BaseModel subclass"
        )

    if cls.name in _REGISTRY:
        existing = _REGISTRY[cls.name]
        raise ValueError(
            f"Tool name '{cls.name}' is already registered by "
            f"{existing.__module__}.{existing.__name__}; cannot re-register "
            f"from {cls.__module__}.{cls.__name__}"
        )

    _REGISTRY[cls.name] = cls
    return cls


def get_tool(name: str) -> type[Tool]:
    if name not in _REGISTRY:
        raise KeyError(f"No tool registered with name '{name}'")
    return _REGISTRY[name]


def all_tools() -> dict[str, type[Tool]]:
    return dict(_REGISTRY)
