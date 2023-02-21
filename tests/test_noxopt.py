from __future__ import annotations

import re
from contextlib import ExitStack
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
            raises: Exception | tuple[type[Exception], str | re.Pattern] | None = ...,
            prints: str | re.Pattern | None = ...,
            logs: str | re.Pattern | None = ...,
        ) -> None:
            ...


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Func]:
    funcs: dict[str, Func] = {}
    monkeypatch.setattr("nox.registry._REGISTRY", funcs)
    return funcs


@pytest.fixture
def execute(
    registry: dict[str, Func],
    capsys: pytest.CaptureFixture,
    caplog: pytest.LogCaptureFixture,
) -> Executor:
    def execute(
        session: str = "",
        tag: str = "",
        posargs: Sequence[str] = (),
        raises: Exception | tuple[type[Exception], str | re.Pattern] | None = None,
        prints: str | re.Pattern | None = None,
        logs: str | re.Pattern | None = None,
    ) -> None:
        manifest = Manifest(registry, nox_options.namespace(posargs=posargs))

        if raises:
            if isinstance(raises, tuple):
                etype, epat = raises
            else:
                etype, epat = type(raises), str(raises)

            if not isinstance(epat, re.Pattern):
                epat = re.compile(epat)
        else:
            etype = epat = None

        to_exec = [session] if session else []
        to_exec.extend(k for k, v in registry.items() if tag in v.tags)
        for func_name in to_exec:
            with ExitStack() as context:
                if etype and epat:
                    context.enter_context(pytest.raises(etype, match=epat))
                manifest[func_name].execute()

        if prints:
            if not isinstance(prints, re.Pattern):
                prints = re.compile(prints)

            readout = capsys.readouterr()
            for line in readout.out.split("\n") + readout.err.split("\n"):
                if prints.search(line):
                    break
            else:
                raise AssertionError(f"No output matches pattern {prints.pattern!r}")

        if logs:
            if not isinstance(logs, re.Pattern):
                logs = re.compile(logs)

            for line in caplog.messages:
                if logs.search(line):
                    break
            else:
                raise AssertionError(f"No log matches pattern {logs.pattern!r}")

    return execute


def test_session_with_simple_option(execute: Executor):
    group = NoxOpt()

    number_value = None

    @group.session
    def my_session(session: Session, number: int = 0) -> None:
        nonlocal number_value
        number_value = number

    execute(session="my-session")
    assert number_value == 0
    execute(session="my-session", posargs=["--number", "1"])
    assert number_value == 1


def test_session_with_annotated_option(execute: Executor):
    group = NoxOpt()

    number_value = None

    @group.session
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
    group = NoxOpt()

    with pytest.raises(ValueError, match="only supports flags"):

        @group.session
        def my_session(
            session: Session, number: Annotated[int, Option(flags=["not-a-flag"])] = 0
        ) -> None:
            ...


def test_expect_metadata_to_be_option(execute: Executor):
    group = NoxOpt()

    with pytest.raises(ValueError, match="metadata must be an Option"):

        @group.session
        def my_session(
            session: Session, number: Annotated[int, "not an option"] = 0
        ) -> None:
            ...


def test_only_kwarg_params(execute: Executor):
    group = NoxOpt()

    with pytest.raises(TypeError, match="Found non-keyword session parameters"):

        @group.session
        def my_session(session: Session, *args: int) -> None:
            ...

    with pytest.raises(TypeError, match="Found non-keyword session parameters"):

        @group.session
        def my_session(session: Session, **args: int) -> None:
            ...


def test_no_extra_metadata(execute: Executor):
    group = NoxOpt()

    with pytest.raises(ValueError, match="has extra metadata"):

        @group.session
        def my_session(
            session: Session, number: Annotated[int, Option(), "extra-junk"] = 0
        ) -> None:
            ...


def tests_error_on_conflicting_options(execute: Executor):
    group = NoxOpt()

    @group.session
    def my_session(session: Session, some_option: int = 0) -> None:
        ...

    with pytest.raises(ValueError, match="Conflicting session options"):

        @group.session
        def my_session(session: Session, some_option: bool = 0) -> None:
            ...

    @group.session
    def my_session(
        session: Session,
        some_option: Annotated[int, Option(type=int)] = 0,
    ) -> None:
        ...

    with pytest.raises(ValueError, match="Conflicting session options"):

        @group.session
        def my_session(
            session: Session,
            some_option: Annotated[int, Option(type=int, help="different")] = 0,
        ) -> None:
            ...


def test_auto_tags_no_prefix(registry):
    group = NoxOpt(auto_tag=True)

    @group.session
    def a_x_1(session: Session) -> None:
        ...

    @group.session
    def a_x_2(session: Session) -> None:
        ...

    @group.session
    def a_y_1(session: Session) -> None:
        ...

    @group.session
    def a_y_2(session: Session) -> None:
        ...

    @group.session
    def b_x_1(session: Session) -> None:
        ...

    @group.session
    def b_x_2(session: Session) -> None:
        ...

    assert set(registry["a-x-1"].tags) == {"a", "a-x"}
    assert set(registry["a-x-2"].tags) == {"a", "a-x"}
    assert set(registry["a-y-1"].tags) == {"a", "a-y"}
    assert set(registry["a-y-2"].tags) == {"a", "a-y"}
    assert set(registry["b-x-1"].tags) == {"b-x"}
    assert set(registry["b-x-2"].tags) == {"b-x"}


def test_setup_funcs(execute: Executor):
    group = NoxOpt(auto_tag=True)

    calls = []

    @group.setup
    def setup_app(session: Session):
        calls.append("setup-all")

    @group.setup("session-x")
    def setup_x(session: Session, setup_param: str = "not-set") -> None:
        assert setup_param == "is-set"
        calls.append("setup-x")

    @group.setup("session-y")
    def setup_y(session: Session, setup_param: str = "not-set") -> None:
        assert setup_param == "is-set"
        calls.append("setup-y")

    @group.session
    def session_x_1(session: Session, session_param: bool = False):
        assert session_param
        calls.append("session-x-1")

    @group.session
    def session_x_2(session: Session, session_param: bool = False):
        assert session_param
        calls.append("session-x-2")

    @group.session
    def session_y_1(session: Session, session_param: bool = False):
        assert session_param
        calls.append("session-y-1")

    @group.session
    def session_y_2(session: Session, session_param: bool = False):
        assert session_param
        calls.append("session-y-2")

    execute(tag="session-x", posargs=["--setup-param", "is-set", "--session-param"])
    assert calls == [
        "setup-all",
        "setup-x",
        "session-x-1",
        "setup-all",
        "setup-x",
        "session-x-2",
    ]

    calls.clear()

    execute(tag="session-y", posargs=["--setup-param", "is-set", "--session-param"])
    assert calls == [
        "setup-all",
        "setup-y",
        "session-y-1",
        "setup-all",
        "setup-y",
        "session-y-2",
    ]


def test_required_argument(execute: Executor, caplog: pytest.LogCaptureFixture):
    group = NoxOpt()

    @group.session
    def session_with_required(session: Session, required: str):
        assert required == "expected"

    execute(
        "session-with-required",
        posargs=[],
        raises=SystemExit(2),
        prints=r"the following arguments are required: --required",
    )

    execute(
        "session-with-required",
        posargs=["--required", "wrong"],
        logs="AssertionError",
    )

    execute(
        "session-with-required",
        posargs=["--required", "expected"],
        logs="AssertionError",
    )
