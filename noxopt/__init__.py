from __future__ import annotations
from dataclasses import dataclass, fields, replace

from inspect import signature, Parameter
import functools
from argparse import ArgumentParser
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Container,
    Sequence,
    TypeVar,
    get_origin,
    get_type_hints,
    get_args,
    ParamSpec,
    Concatenate,
)

import nox
from nox.sessions import Session


__all__ = ["NoxOpt", "Option"]


if TYPE_CHECKING:
    UNDEFINED: Any

    F = TypeVar("F", bound=Callable[..., None])
    P = ParamSpec("P")
    R = TypeVar("R")

    def copy_method_signature(
        func: Callable[P, R]
    ) -> Callable[[Callable[..., Any]], Callable[Concatenate[Any, P], R]]:
        ...

else:
    UNDEFINED = type("Undefined", (), {"__repr__": lambda self: "UNDEFINED"})()
    copy_method_signature = lambda f: lambda g: g


class NoxOpt:
    """Define a set of sessions with arguments

    Arguments:
        parser:
            A manually defined argument parser
        prefix:
            A prefix added to all session and automatically generated tag names.
        auto_tag_depth:
            Automatically generates tags based on session names up to the given depth
            (disable by default). For example given a session named 'foo-bar-pew-zap'
            with a `auto_tag_depth=3` the tags 'foo', 'foo-bar', and 'foo-bar-pew' will
            be automatically added.

            This is useful if you have a set of sessions like:

                - `check-python-tests`
                - `check-python-style`
                - `check-javascript-tests`
                - `check-javascript-style`

            Since you can set `auto_tag_depth=2` and be able to execute a command like
            `nox -t check-python` and Nox will automatically run all your sessions that
            begin with `check-python`.

    Note:
        By default underscores in session function names are replaced with dashes as are
        paramter names when defining command line arguments.
    """

    def __init__(
        self,
        parser: ArgumentParser | None = None,
        session_prefix: str = "",
        auto_tag_depth: int = 0,
    ):
        self._parser = parser or ArgumentParser()
        self._options_by_flags: dict[str, Option] = {}
        self._auto_tag_depth = auto_tag_depth
        self._session_prefix = session_prefix

    @copy_method_signature(nox.session)
    def session(
        self,
        func: Any | None = None,
        *args: Any,
        name: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Designate the decorated function as a session with command line arguments."""

        def decorator(func: F) -> F:
            session_name = name or func.__name__.replace("_", "-")

            if self._session_prefix:
                session_name = f"{self._session_prefix}-{session_name}"

            if self._auto_tag_depth:
                prefix_len = self._session_prefix.count("-") + 1
                tag_parts = session_name.split("-")[: self._auto_tag_depth + prefix_len]
                auto_tags = {"-".join(tag_parts[:i]) for i in range(1, len(tag_parts))}
                # merge automatic tags with any provided by the user
                kwargs["tags"] = list(set(kwargs.get("tags", set())) | auto_tags)

            own_params: set[str] = set()
            for param_name, option in _get_options_from_function(func).items():
                own_params.add(param_name)
                self._add_option_to_parser(option)

            @nox.session(*args, name=session_name, **kwargs)  # type: ignore[call-overload]
            @functools.wraps(func)
            def wrapper(session: Session) -> None:
                args_dict = self._parser.parse_args(session.posargs).__dict__
                func(session, **{k: v for k, v in args_dict.items() if k in own_params})

            return func

        return decorator if func is None else decorator(func)

    def _add_option_to_parser(self, option: Option) -> None:
        already_exists = False

        for flag in option.flags:
            existing = self._options_by_flags.get(flag)
            if not existing:
                self._options_by_flags[flag] = option
            elif existing != option:
                raise ValueError(f"Session argument {flag} already exists")
            else:
                already_exists = True

        if not already_exists:
            option.add_argument_to_parser(self._parser)


@dataclass
class Option:
    flags: Sequence[str] = UNDEFINED
    # remainder are alphabetical
    action: str | None = UNDEFINED
    choices: Container = UNDEFINED
    const: Any = UNDEFINED
    default: Any | None = UNDEFINED
    dest: str = UNDEFINED
    help: str = UNDEFINED
    metavar: str = UNDEFINED
    nargs: str | int | None = UNDEFINED
    required: bool = UNDEFINED
    type: int | float | Callable[[Any], Any] = UNDEFINED

    def __post_init__(self) -> None:
        if isinstance(self.flags, str):
            self.flags = (self.flags,)
        if self.flags is not UNDEFINED:
            for f in self.flags:
                if not f.startswith("-"):
                    raise ValueError(f"Option only supports flags, but got {f!r}")

    def add_argument_to_parser(self, parser: ArgumentParser) -> None:
        kwargs = {
            k: v
            for k, v in (
                # Can't use asdict() since that deep copies and we need
                # to filter using an identity check against UNDEFINED.
                [(f.name, getattr(self, f.name)) for f in fields(self)]
            )
            if v is not UNDEFINED
        }

        flags = kwargs.pop("flags")
        print(kwargs)
        parser.add_argument(*flags, **kwargs)


def _get_options_from_function(func: Callable[..., Any]) -> dict[str, Option]:
    options: dict[str, Option] = {}
    for name, (default, annotation) in _get_function_defaults_and_annotations(
        func
    ).items():
        opt = _get_annotated_option(annotation) or Option()

        if default is not UNDEFINED:
            opt = replace(opt, default=default)
        else:
            opt = replace(opt, required=True)

        true_annotation = get_origin(annotation) or annotation
        if opt.type is UNDEFINED:
            if not callable(true_annotation):
                raise TypeError(
                    f"Type hint {annotation} must be Annotated with an Option"
                )
            opt = replace(opt, type=true_annotation)

        if opt.flags is UNDEFINED:
            opt = replace(opt, flags="--" + name.replace("_", "-"))

        options[name] = opt

    return options


def _get_annotated_option(annotation: Any) -> Option | None:
    if type(annotation) is not Annotated:
        return None
    opt, *extra_args = get_args(annotation)
    if extra_args:
        raise ValueError(
            "Found extra Annotated metadata for parameter {name!r} of {func}"
        )
    if not isinstance(opt, Option):
        raise ValueError(
            "Expected the Annotated metadata for parameter {name!r} of {func} to be an Option, not {opt}"
        )
    return opt


def _get_function_defaults_and_annotations(
    func: Callable[..., Any]
) -> dict[str, tuple[Parameter, Any]]:
    parameters = list(signature(func).parameters.values())
    annotations = get_type_hints(func, include_extras=True)

    # delete first positional argument
    del parameters[0]

    kw_param_kinds = (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
    non_kws = [p.name for p in parameters if p.kind not in kw_param_kinds]
    if non_kws:
        raise TypeError(f"Found non-keyword session parameters {', '.join(non_kws)}")

    return {
        param.name: (
            UNDEFINED if param.default is Parameter.empty else param.default,
            annotations[param.name],
        )
        for param in parameters
    }
