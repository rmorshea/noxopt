from typing import Annotated, TypeAlias
from noxopt import NoxOpt, Option, Session

nox = NoxOpt(auto_tag_depth=2, prefix="temp")


@nox.session
def format(s):
    print("format")


@nox.session
def check_python_tests(s):
    print("check_python_tests")


@nox.session
def check_python_style(s):
    print("check_python_style")


@nox.session
def check_javascript_tests(s):
    print("check_javascript_tests")
