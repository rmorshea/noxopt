from __future__ import annotations

import functools
import sys
from argparse import ArgumentParser
from dataclasses import dataclass, fields, replace
from inspect import Parameter, signature
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Container,
    DefaultDict,
    Sequence,
    TypeVar,
    overload,
)

import nox
from nox.sessions import Session

from noxopt import _config


if sys.version_info < (3, 10):  # pragma: no cover
    from typing_extensions import (
        Annotated,
        Concatenate,
        ParamSpec,
        get_args,
        get_origin,
        get_type_hints,
    )
else:
    from typing import (
        Annotated,
        Concatenate,
        ParamSpec,
        get_args,
        get_origin,
        get_type_hints,
    )


__all__ = ["NoxOpt", "Option", "Session", "Annotated"]


if TYPE_CHECKING:
    from nox._decorators import Func

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

    def copy_method_signature(func):
        return lambda f: f


class NoxOpt:
    """Define a group of NoxOpt group"""

    def __init__(
        self,
        parser: ArgumentParser | None = None,
        auto_tag: bool = False,
        where: dict[str, Any] | None = None,
    ):
        self._parser = parser or ArgumentParser()
        self._options_by_flags: dict[str, Option] = {}
        self._auto_tag = _AutoTag() if auto_tag else None
        self._setup_funcs: DefaultDict[
            str, list[Callable[[Session], None]]
        ] = DefaultDict(list)
        self._common_session_kwargs: dict[str, Any] = where or {}
        if _config.NOXOPT_TESTING:
            self._common_session_kwargs["venv_backend"] = "none"

    @copy_method_signature(nox.session)
    def session(
        self,
        func: Any | None = None,
        *args: Any,
        name: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Designate the decorated function as a session with command line arguments."""

        def decorator(main_func: Any) -> Any:
            session_name = name or main_func.__name__.replace("_", "-")
            wrapper = self._create_setup_wrapper(
                session_name,
                self._create_parser_wrapper(main_func),
            )
            session = nox.session(
                *args,
                name=session_name,
                **kwargs,
                **self._common_session_kwargs,
            )(wrapper)
            if self._auto_tag:
                self._auto_tag.add_func(session_name, session)
            return session

        return decorator if func is None else decorator(func)

    @overload
    def setup(self, __func: Callable[..., None]) -> Callable[..., None]:
        ...

    @overload
    def setup(self, *names: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        ...

    def setup(self, *args: Any) -> Any:
        """Define a function that will run before"""
        first_arg, *rest_args = args
        if isinstance(first_arg, str):
            prefixes = args
            func = None
        else:
            func = first_arg
            prefixes = ()

        def decorator(func: Callable[..., None]) -> Callable[..., None]:
            wrapper = self._create_parser_wrapper(func)
            for p in prefixes or [""]:
                self._setup_funcs[p].append(wrapper)
            return wrapper

        return decorator if func is None else decorator(func)

    def _create_setup_wrapper(
        self, name: str, func: Callable[..., Any]
    ) -> Callable[..., Any]:
        def wrapper(session: Session) -> None:
            for prefix, setup_funcs in self._setup_funcs.items():
                if name.startswith(prefix):
                    for f in setup_funcs:
                        f(session)
            func(session)

        return wrapper

    def _create_parser_wrapper(self, func: Callable[..., Any]) -> Callable[..., Any]:
        own_params: set[str] = set()
        for param_name, option in _get_options_from_function(func).items():
            own_params.add(param_name)
            self._add_option_to_parser(option)

        @functools.wraps(func)
        def wrapper(session: Session) -> None:
            args_dict = self._parser.parse_args(session.posargs).__dict__
            func(session, **{k: v for k, v in args_dict.items() if k in own_params})

        return wrapper

    def _add_option_to_parser(self, option: Option) -> None:
        already_exists = False

        for flag in option.flags:
            existing = self._options_by_flags.get(flag)
            if not existing:
                self._options_by_flags[flag] = option
            elif existing != option:
                raise ValueError(
                    f"Conflicting session options:\n"
                    f"new:      {option}\n"
                    f"existing: {existing}"
                )
            else:
                already_exists = True

        if not already_exists:
            option.add_argument_to_parser(self._parser)


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


def _get_options_from_function(func: Callable[..., Any]) -> dict[str, Option]:
    options: dict[str, Option] = {}
    for name, (default, annotation) in _get_function_defaults_and_annotations(
        func
    ).items():
        opt = _get_annotated_option(annotation)

        if default is not UNDEFINED:
            if opt.type is bool:
                opt = replace(
                    opt,
                    action="store_false" if default else "store_true",
                    type=UNDEFINED,
                )
            else:
                opt = replace(opt, default=default)
        else:
            opt = replace(opt, required=True)

        if opt.flags is UNDEFINED:
            opt = replace(opt, flags="--" + name.replace("_", "-"))

        options[name] = opt

    return options


def _get_annotated_option(annotation: Any) -> Option:
    if get_origin(annotation) is not Annotated:
        if not callable(annotation):
            raise TypeError(
                f"Type hint {annotation} must be callable or it should "
                "be declared via Annotated[..., Option(...)] instead."
            )
        return Option(type=annotation)
    _, opt, *extra_args = get_args(annotation)
    if extra_args:
        raise ValueError(f"{annotation} has extra metadata {extra_args}")
    if not isinstance(opt, Option):
        raise ValueError(f"{annotation} metadata must be an Option")
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


class _AutoTag:
    r"""Session auto tagging utility

    Construct a graph of words, and at every branching point in the graph it creates a
    tag. For example the session names:

    - `a-x-1`
    - `a-x-2`
    - `a-y-1`
    - `a-y-2`
    - `b-x-1`
    - `b-x-2`

    Would create the graph:

    ```
          *
         / \
        a   b
       /\    \
      x  y    x
     /|  |\   |\
    1 2  1 2  1 2
    ```

    At every branching point in the graph a tag would be generated and applied to all
    functions with that prefix. So the tags would be:

    - `a`
    - `a-x`
    - `a-y`
    - `b-x`

    This isn't always perfect since technically, we could subtitute the tag `b-x` for
    just `b` since the shorted common string between `b-x-1` and `b-x-2` is `b`. But
    it works most of the time, and it makes the algorithm a bit easier to reason about.
    """

    def __init__(self, sep: str = "-"):
        self._sep = sep
        self._tag_tree = _TagNode()

    def add_func(self, name: str, func: Func) -> None:
        node = self._tag_tree

        # each branching point in the graph represents a tag
        for word in name.split(self._sep):
            if word in node.children:
                # this is a branching point in the graph
                if len(node.children) > 1:
                    node.add_tag(func)
                node = node.children[word]
            else:
                if len(node.children) == 1:
                    node.add_tag(func)
                    # We're about to create a new branching point - funcs added earlier
                    # will not have this nodes tag.
                    node.retroactively_add_tags()
                node = node.add_node(word, self._sep)

        # add this func to the last node
        node.add_func(func)


class _TagNode:
    def __init__(self, parent: _TagNode | None = None, tag: str | None = None):
        self.parent = parent
        self.tag = tag
        self.funcs: list[Func] = []
        self.children: dict[str, _TagNode] = {}

    def add_node(self, word: str, sep: str) -> _TagNode:
        tag = f"{self.tag}{sep}{word}" if self.tag else word
        child = self.children[word] = _TagNode(self, tag)
        return child

    def add_func(self, func: Func) -> None:
        self.funcs.append(func)

    def add_tag(self, func: Func) -> None:
        if self.tag:
            func.tags.append(self.tag)

    def retroactively_add_tags(self) -> None:
        to_visit = [self]
        while to_visit:
            node = to_visit.pop()
            for f in node.funcs:
                self.add_tag(f)
            to_visit.extend(node.children.values())
