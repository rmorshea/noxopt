# NoxOpt

[Nox](https://github.com/wntrblm/nox) sessions with options!

## Installation

It's just `pip install noxopt`!

## Basic Usage

Define a session with typed parameters:

```python
from noxopt import NoxOpt, Session

nox = NoxOpt()

@nox.session
def add_numbers(session: Session, x: int, y: int) -> None:
    session.log(x + y)
```

Now you can pass this session the declared option via the command line:

```bash
nox -s my-session -- --x 10 -- y 3
```

And you'll see the following output

```txt
nox > Running session my-session
nox > Creating virtual environment (virtualenv) using python in .nox/my-session
nox > 13
nox > Session my-session was successful.
```

Note that all options declared with the sessions of a `NoxOpt` group must be consistent.
That is, if one session defined `x: int`, another session in the same group cannot
define `x: bool` instead.

## Customizing Options

This time you're going to use some [`Annotated`](https://peps.python.org/pep-0593/)
metadata to customize your option:

```python
from typing import Annotated, TypeAlias
from noxopt import NoxOpt, Option, Session

nox = NoxOpt()

@nox.session
def sum_numbers(
    session: Session,
    nums: Annotated[list[int], Option(nargs="*", type=int)],
) -> None:
    session.log(sum(nums))
```

This time when you run it you can pass several of numbers:

```bash
nox -s sum-numbers -- --nums 10 3 26 4
```

And you'll see the following output

```txt
nox > Running session my-session
nox > Creating virtual environment (virtualenv) using python in .nox/my-session
nox > 43
nox > Session my-session was successful.
```

Note that the annotation for `nums` should be understood in the following way:

```python
# declare a type with metadata
Annotated[
    # your normal type annotation
    list[int],
    # configure the option associated with the type annotation above
    Option(nargs="*", type=int)
]
```

You'll find that `Option` has nearly the same parameters as
[`argparse.add_argument`](https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument).

If you need to use a given option more than once you can do so by defining it as a
variable:

```python
from functools import reduce
from typing import Annotated, TypeAlias
from noxopt import NoxOpt, Option, Session

nox = NoxOpt()

Integers = Annotated[list[int], Option(nargs="*", type=int)]

@nox.session
def sum_numbers(session: Session, nums: Integers) -> None:
    session.log(sum(nums))

@nox.session
def multiply_numbers(session: Session, nums: Integers) -> None:
    session.log(reduce(lambda x, y: x * y, nums, 0))
```

## Automatic Tags

An additional nicety of NoxOpt is that is can automatically create tags based on the
names of your sessions using the `NoxOpt(auto_tag=True)` parameter. The idea behind this
parameter is that if you have a set of sessions with a common naming scheme like:

```python
from noxopt import NoxOpt, Session

nox = NoxOpt(auto_tag=True)

@nox.session
def check_python_tests(session: Session) -> None:
    ...

@nox.session
def check_python_format(session: Session) -> None:
    ...

@nox.session
def check_javascript_tests(session: Session) -> None:
    ...

@nox.session
def check_javascript_format(session: Session) -> None:
    ...
```

NoxOpt will generate the following tags:

- `check` - run sessions begining with `check`
- `check-python` - run sessions begining with `check-python`
- `check-javascript`- run sessions begining with `check-javascript`

It does this by splitting every session name in the group on `-` characters and creating
tags based on their common prefixes.
