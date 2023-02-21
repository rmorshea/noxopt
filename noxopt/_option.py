from __future__ import annotations

import sys
from argparse import ArgumentParser
from dataclasses import dataclass, fields, replace
from inspect import Parameter, signature
from typing import Any, Callable, Container, Sequence, cast


if sys.version_info < (3, 10):  # pragma: no cover
    from typing_extensions import (
        Annotated,
        get_args,
        get_origin,
        get_type_hints,
        TypedDict,
    )
else:
    from typing import Annotated, get_args, get_origin, get_type_hints, TypedDict


UNDEFINED = cast(Any, type("Undefined", (), {"__repr__": lambda self: "UNDEFINED"})())


def get_function_options(func: Callable[..., Any]) -> dict[str, Option]:
    return {
        k: _create_option(k, d, a)
        for k, (d, a) in _get_function_defaults_and_annotations(
            _get_maybe_wrapped_func(func)
        ).items()
    }


@dataclass
class Option:
    flags: Sequence[str] = UNDEFINED
    # remainder are alphabetical
    action: str | None = UNDEFINED
    choices: Container[Any] = UNDEFINED
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
        parser.add_argument(*flags, **kwargs)


def _create_option(name: str, default: Any, annotation: Any) -> Option:
    if get_origin(annotation) is Annotated:
        anno_args = get_args(annotation)
    else:
        anno_args = (annotation, Option())

    opt_type, opt, *extra_args = anno_args

    if not isinstance(opt, Option):
        raise ValueError(f"{annotation} metadata must be an Option")

    if extra_args:
        raise ValueError(f"{annotation} has extra metadata {extra_args}")

    if opt.type is UNDEFINED:
        if not callable(opt_type):
            raise TypeError(
                f"Annotation {annotation} for parameter {name!r} is not callable."
                f"Declare option type with Annotated[..., Option(type=...)] instead."
            )
        opt = replace(opt, type=opt_type)

    if opt.type is bool:
        opt = replace(
            opt,
            action="store_false" if default is True else "store_true",
            type=UNDEFINED,
            default=UNDEFINED,
        )
    elif default is not UNDEFINED:
        opt = replace(opt, default=default)
    else:
        opt = replace(opt, required=True)

    if opt.flags is UNDEFINED:
        opt = replace(opt, flags="--" + name.replace("_", "-"))

    return opt


def _get_function_defaults_and_annotations(
    maybe_wrapped: _MaybeWrappedFunc,
) -> dict[str, tuple[Parameter, Any]]:
    parameters = list(signature(maybe_wrapped["func"]).parameters.values())
    annotations = get_type_hints(maybe_wrapped["func"], include_extras=True)

    parameters = [
        p
        # skip first positional arg (the nox session obj) + any partial positional args
        for p in parameters[maybe_wrapped["skip_pos_args_num"] + 1 :]
        # skip any partial kwargs
        if p.name not in maybe_wrapped["skip_kwarg_names"]
    ]

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


def _get_maybe_wrapped_func(func: Callable[..., Any]) -> Callable[..., Any]:
    skip_pos_args_num = len(getattr(func, "args", ()))
    skip_kwarg_names = set(getattr(func, "kwargs", {}))
    while True:
        maybed_func = (
            # functools.wraps does this
            getattr(func, "__wrapped__", None)
            # functools.partial does this
            or getattr(func, "func", None)
        )
        if callable(maybed_func):
            func = maybed_func
        else:
            break
    return _MaybeWrappedFunc(func, skip_pos_args_num, skip_kwarg_names)


class _MaybeWrappedFunc(TypedDict):
    func: Callable[..., Any]
    skip_pos_args_num: int
    skip_kwarg_names: set[str]
