from __future__ import annotations

from typing import TYPE_CHECKING, Sequence
from nox._decorators import Func
from nox import Session
from nox._options import options as nox_options
from nox.manifest import Manifest
from noxopt import NoxOpt, Option

import pytest

if TYPE_CHECKING:
    from typing import Callable, Protocol

    class Executor(Protocol):
        def __call__(
            self,
            session: str = "",
            tag: str = "",
            posargs: Sequence[str] = ...,
        ) -> None:
            ...


@pytest.fixture
def execute(monkeypatch: pytest.MonkeyPatch) -> Executor:
    funcs: dict[str, Func] = {}
    monkeypatch.setattr("nox.registry._REGISTRY", funcs)

    def execute(session: str = "", tag: str = "", posargs: Sequence[str] = ()) -> None:
        manifest = Manifest(funcs, nox_options.namespace(posargs=posargs))

        to_exec = [session] if session else []
        to_exec.extend(k for k, v in funcs.items() if tag in v.tags)
        for func_name in to_exec:
            try:
                manifest[func_name].execute()
            except SystemExit as error:
                raise RuntimeError(*error.args) from error

    return execute


def test_add_session(execute: Executor):
    app = NoxOpt()

    some_option_value = None

    @app.session(venv_backend="none")
    def my_session(session: Session, some_option: int = 0) -> None:
        nonlocal some_option_value
        some_option_value = some_option

    execute(session="my-session", posargs=["--some-option", "0"])
    assert some_option_value == 0
