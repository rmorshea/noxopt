import sys
from pathlib import Path
from shutil import rmtree

import nox
import noxopt

ROOT = Path(__file__).parent


@nox.session(name="format")
def format(session: nox.Session) -> None:
    session.install("-r", "requirements.txt")
    session.run("black", ".")
    session.run("isort", ".")


@nox.session(name="check-tests", tags=["check"])
def check_tests(session: nox.Session) -> None:
    session.install("-r", "requirements/check-tests.txt")

    args = ["pytest", *session.posargs]

    check_cov = "--no-cov" not in session.posargs
    if check_cov:
        args = ["coverage", "run", "--source=noxopt", "--module", *args]
        session.install("-e", ".")
    else:
        args.remove("--no-cov")
        session.log("Coverage won't be checked")
        session.install(".")

    session.run(*args)

    if check_cov:
        session.run("coverage", "report")


@nox.session(name="check-format", tags=["check"])
def check_format(session: nox.Session) -> None:
    session.install("-r", "requirements/check-format.txt")
    session.run("flake8", "noxopt", "tests")
    session.run("black", ".", "--check")
    session.run("isort", ".", "--check-only")


@nox.session(name="check-types", tags=["check"])
def check_types(session: nox.Session) -> None:
    session.install("-r", "requirements/check-types.txt")
    session.run("mypy", "--version")
    session.run("mypy", "--show-error-codes", "--strict", "noxopt")
    session.run("mypy", "noxfile.py")


@nox.session
def build(session: nox.Session) -> None:
    rmtree(str(ROOT / "build"))
    rmtree(str(ROOT / "dist"))
    session.install("build", "wheel")
    session.run("python", "-m", "build", "--sdist", "--wheel", "--outdir", "dist", ".")


@nox.session
def release(session: nox.Session) -> None:
    session.install("twine")
    session.run("twine", "upload", "dist/*")


try:
    sys.modules["noxopt"]
except KeyError:
    pass
else:
    print(
        f"NoxOpt was imported somewhere in: {__file__}\n"
        "This must be avoided in order to keep all Nox sessions functional "
        "even when NoxOpt itself is in a broken state during development."
    )
    sys.exit(1)
