from __future__ import annotations

import functools
from argparse import ArgumentParser
from typing import TYPE_CHECKING, Any, Callable, DefaultDict, TypeVar, overload

import nox
from nox.sessions import Session

from noxopt import _config
from noxopt._option import Option, get_function_options
from noxopt._tagging import AutoTag


if TYPE_CHECKING:
    from typing import Concatenate, ParamSpec

    AnyFunc = Callable[..., Any]

    F = TypeVar("F", bound=Callable[..., None])
    P = ParamSpec("P")
    R = TypeVar("R")

    def copy_method_signature(
        func: Callable[P, R]
    ) -> Callable[[AnyFunc], Callable[Concatenate[Any, P], R]]:
        ...

else:

    def copy_method_signature(func):
        return lambda f: f


class NoxOpt:
    """Define a group of NoxOpt group"""

    def __init__(
        self,
        parser: ArgumentParser | None = None,
        auto_tag: bool = False,
        where: dict[str, Any] | None = None,
        explicit_options: bool = False,
    ):
        self._parser = parser or ArgumentParser("")
        self._options_by_flags: dict[str, Option] = {}
        self._auto_tag = AutoTag() if auto_tag else None
        self._explicit_options = explicit_options
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
            wrapper = _copy_nox_parametrize(
                main_func,
                self._create_setup_wrapper(
                    session_name,
                    self._create_parser_wrapper(main_func),
                ),
            )
            session = nox.session(
                *args,
                name=session_name,
                **{**self._common_session_kwargs, **kwargs},
            )(wrapper)
            if self._auto_tag:
                self._auto_tag.add_func(session_name, session)
            return session

        return decorator if func is None else decorator(func)

    @overload
    def setup(self, __func: Callable[..., None]) -> Callable[..., None]:
        ...

    @overload
    def setup(self, *names: str) -> Callable[[AnyFunc], AnyFunc]:
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

    def _create_setup_wrapper(self, name: str, func: AnyFunc) -> AnyFunc:
        @functools.wraps(func)
        def wrapper(session: Session, *args: Any, **kwargs: Any) -> None:
            for prefix, setup_funcs in self._setup_funcs.items():
                if name.startswith(prefix):
                    for f in setup_funcs:
                        f(session)
            func(session, *args, **kwargs)

        return wrapper

    def _create_parser_wrapper(self, func: AnyFunc) -> AnyFunc:
        own_params: set[str] = set()
        for name, option in get_function_options(func, self._explicit_options).items():
            own_params.add(name)
            self._add_option_to_parser(option)

        @functools.wraps(func)
        def wrapper(session: Session, *args: Any, **kwargs: Any) -> None:
            args_dict = self._parser.parse_args(session.posargs).__dict__
            func(
                session,
                *args,
                **kwargs,
                **{k: v for k, v in args_dict.items() if k in own_params},
            )

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


def _copy_nox_parametrize(func: AnyFunc, wrapper: AnyFunc) -> Callable[[Any], AnyFunc]:
    # nox.parametrize adds this attribbute
    if hasattr(func, "parametrize"):
        wrapper.parametrize = func.parametrize  # type: ignore[attr-defined]
    return wrapper
