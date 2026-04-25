from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, TypeVar

from pydantic import BaseModel

from docent.core.context import Context


@dataclass(frozen=True)
class Action:
    """Metadata attached to a method by `@action`.

    The registry introspects each Tool class for methods carrying an `Action`
    via `_docent_action`. CLI name defaults to the method name with
    underscores → dashes (override via `name=`).
    """

    description: str
    input_schema: type[BaseModel]
    name: str | None = None


F = TypeVar("F", bound=Callable[..., Any])


def action(
    *,
    description: str,
    input_schema: type[BaseModel],
    name: str | None = None,
) -> Callable[[F], F]:
    """Decorator: mark a method on a Tool as an invocable action."""

    def decorator(fn: F) -> F:
        fn._docent_action = Action(  # type: ignore[attr-defined]
            description=description, input_schema=input_schema, name=name
        )
        return fn

    return decorator


class Tool(ABC):
    """Base class for every Docent tool.

    Two paths:
    - **Single-action**: set `input_schema` and override `run()`.
    - **Multi-action**: decorate one or more methods with `@action(...)`.

    A tool must be one or the other - never both. Enforced at registration.
    Metadata lives as class attributes so the registry (and later the UI)
    can read it without constructing an instance.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    category: ClassVar[str | None] = None

    input_schema: ClassVar[type[BaseModel] | None] = None

    def run(self, inputs: BaseModel, context: Context) -> Any:
        """Single-action entry point. Multi-action tools don't override this."""
        raise NotImplementedError(
            f"{type(self).__name__}.run() not implemented - "
            f"is this a multi-action tool? Invoke one of its @action methods instead."
        )


def collect_actions(cls: type[Tool]) -> dict[str, tuple[str, Action]]:
    """Return `{cli_action_name: (method_name, Action)}` for all `@action` methods.

    Raises `ValueError` on CLI-name collisions between actions.
    """
    found: dict[str, tuple[str, Action]] = {}
    for attr_name in dir(cls):
        attr = getattr(cls, attr_name, None)
        if callable(attr) and hasattr(attr, "_docent_action"):
            meta: Action = attr._docent_action  # type: ignore[attr-defined]
            cli_name = meta.name or attr_name.replace("_", "-")
            if cli_name in found:
                prev_method = found[cli_name][0]
                raise ValueError(
                    f"Tool {cls.__name__} has two actions with the same CLI name "
                    f"'{cli_name}': {prev_method} and {attr_name}"
                )
            found[cli_name] = (attr_name, meta)
    return found
