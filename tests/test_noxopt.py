from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

import pytest
from nox._decorators import Func
from nox._options import options as nox_options
from nox.manifest import Manifest

from noxopt import Annotated, NoxOpt, Option, Session


if TYPE_CHECKING:
    from typing import Protocol

    class Executor(Protocol):
        def __call__(
            self,
            session: str = "",
            tag: str = "",
            posargs: Sequence[str] = ...,
        ) -> None:
            ...


@pytest.fixture
def registry(monkeypatch) -> dict[str, Func]:
    funcs: dict[str, Func] = {}
    monkeypatch.setattr("nox.registry._REGISTRY", funcs)
    return funcs


@pytest.fixture
def execute(registry) -> Executor:
    def execute(session: str = "", tag: str = "", posargs: Sequence[str] = ()) -> None:
        manifest = Manifest(registry, nox_options.namespace(posargs=posargs))

        to_exec = [session] if session else []
        to_exec.extend(k for k, v in registry.items() if tag in v.tags)
        for func_name in to_exec:
            try:
                manifest[func_name].execute()
            except SystemExit as error:
                raise RuntimeError(*error.args) from error

    return execute


def test_session_with_simple_option(execute: Executor):
    app = NoxOpt()

    number_value = None

    @app.session(venv_backend="none")
    def my_session(session: Session, number: int = 0) -> None:
        nonlocal number_value
        number_value = number

    execute(session="my-session")
    assert number_value == 0
    execute(session="my-session", posargs=["--number", "1"])
    assert number_value == 1


def test_session_with_annotated_option(execute: Executor):
    app = NoxOpt()

    number_value = None

    @app.session(venv_backend="none")
    def my_session(
        session: Session,
        # double the given number
        number: Annotated[int, Option(type=lambda i: int(i) * 2)] = 0,
    ) -> None:
        nonlocal number_value
        number_value = number

    execute(session="my-session", posargs=["--number", "2"])
    assert number_value == 4


def test_all_options_are_flags(execute: Executor):
    app = NoxOpt()

    with pytest.raises(ValueError, match="only supports flags"):

        @app.session(venv_backend="none")
        def my_session(
            session: Session, number: Annotated[int, Option(flags=["not-a-flag"])] = 0
        ) -> None:
            ...


def test_expect_metadata_to_be_option(execute: Executor):
    app = NoxOpt()

    with pytest.raises(ValueError, match="metadata must be an Option"):

        @app.session(venv_backend="none")
        def my_session(
            session: Session, number: Annotated[int, "not an option"] = 0
        ) -> None:
            ...


def test_only_kwarg_params(execute: Executor):
    app = NoxOpt()

    with pytest.raises(TypeError, match="Found non-keyword session parameters"):

        @app.session(venv_backend="none")
        def my_session(session: Session, *args: int) -> None:
            ...

    with pytest.raises(TypeError, match="Found non-keyword session parameters"):

        @app.session(venv_backend="none")
        def my_session(session: Session, **args: int) -> None:
            ...


def test_no_extra_metadata(execute: Executor):
    app = NoxOpt()

    with pytest.raises(ValueError, match="has extra metadata"):

        @app.session(venv_backend="none")
        def my_session(
            session: Session, number: Annotated[int, Option(), "extra-junk"] = 0
        ) -> None:
            ...


def tests_error_on_conflicting_options(execute: Executor):
    app = NoxOpt()

    @app.session(venv_backend="none")
    def my_session(session: Session, some_option: int = 0) -> None:
        ...

    with pytest.raises(ValueError, match="Conflicting session options"):

        @app.session(venv_backend="none")
        def my_session(session: Session, some_option: bool = 0) -> None:
            ...

    @app.session(venv_backend="none")
    def my_session(
        session: Session,
        some_option: Annotated[int, Option(type=int)] = 0,
    ) -> None:
        ...

    with pytest.raises(ValueError, match="Conflicting session options"):

        @app.session(venv_backend="none")
        def my_session(
            session: Session,
            some_option: Annotated[int, Option(type=int, help="different")] = 0,
        ) -> None:
            ...


def test_auto_tags_no_prefix(registry):
    app = NoxOpt(auto_tag=True)

    @app.session
    def a_x_1(session: Session) -> None:
        ...

    @app.session
    def a_x_2(session: Session) -> None:
        ...

    @app.session
    def a_y_1(session: Session) -> None:
        ...

    @app.session
    def a_y_2(session: Session) -> None:
        ...

    @app.session
    def b_x_1(session: Session) -> None:
        ...

    @app.session
    def b_x_2(session: Session) -> None:
        ...

    assert set(registry["a-x-1"].tags) == {"a", "a-x"}
    assert set(registry["a-x-2"].tags) == {"a", "a-x"}
    assert set(registry["a-y-1"].tags) == {"a", "a-y"}
    assert set(registry["a-y-2"].tags) == {"a", "a-y"}
    assert set(registry["b-x-1"].tags) == {"b-x"}
    assert set(registry["b-x-2"].tags) == {"b-x"}
