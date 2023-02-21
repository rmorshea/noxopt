# NoxOpt

[Nox](https://github.com/wntrblm/nox) sessions with options!

## Installation

It's just `pip install noxopt`!

## Basic Usage

Define a session with typed parameters:

```python
from noxopt import NoxOpt, Session

group = NoxOpt()

@group.session
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
from typing import Annotated
from noxopt import NoxOpt, Option, Session

group = NoxOpt()

@group.session
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

group = NoxOpt()

Integers = Annotated[list[int], Option(nargs="*", type=int)]

@group.session
def sum_numbers(session: Session, nums: Integers) -> None:
    session.log(sum(nums))

@group.session
def multiply_numbers(session: Session, nums: Integers) -> None:
    session.log(reduce(lambda x, y: x * y, nums, 0))
```

## Parametrizing Sessions

If want to use the
[`@nox.parametrize`](https://nox.thea.codes/en/stable/config.html#parametrizing-sessions)
decorator with NoxOpt you'll need to explicitely declare which parameters should be
treated as command line options. This is done by annotating them with
`Annotated[YourType, Option()]`:

```python
from typing import Annotated
from nox import Session, parametrize
from noxopt import NoxOpt, Option

group = NoxOpt()

@group.session
@parametrize("num", [1, 2, 3])
def log_nums(session: Session, num: int, mult: Annotated[int, Option()]) -> None:
    session.log(num * mult)

```

You could now run:

```bash
nox -s multiply-nums -- --mult 2
```

And see the output:

```
nox > Running session multiply-nums(num=1)
nox > Creating virtual environment (virtualenv) using python in .nox/multiply-nums-num-1
nox > 2
nox > Session multiply-nums(num=1) was successful.
nox > Running session multiply-nums(num=2)
nox > Creating virtual environment (virtualenv) using python in .nox/multiply-nums-num-2
nox > 4
nox > Session multiply-nums(num=2) was successful.
nox > Running session multiply-nums(num=3)
nox > Creating virtual environment (virtualenv) using python in .nox/multiply-nums-num-3
nox > 6
nox > Session multiply-nums(num=3) was successful.
nox > Ran multiple sessions:
nox > * multiply-nums(num=1): success
nox > * multiply-nums(num=2): success
nox > * multiply-nums(num=3): success
```

## Common Setup

NoxOpt allows you to add logic that runs before sessions in a group.

```python
from noxopt import NoxOpt, Session

group = NoxOpt()

@nox.setup
def setup(session: Session) -> None:
    ...  # your setup logic here

@group.session
def my_session(session: Sesssion) -> None:
    ... # your session here
```

Here, the `setup` function will run before all sessions in the `NoxOpt` group. To
run setup only on specific sessions in a group you specify a prefix. Any sessions
whose names begin with that prefix will share the same setup procedure:

```python
from noxopt import NoxOpt, Session

group = NoxOpt()

@nox.setup("python")
def setup_python(session: Session) -> None:
    ...  # your setup logic here

@group.session
def python_tests(session: Session) -> None:
    ...

@group.session
def javascript_tests(session: Session) -> None:
    ...
```

Here, `setup_python` will only run when any session whose name begins with `python` is
executed. In this case that would only apply to the `python-tests` session.

You can also declare common settings for all sessions within a group by passing
`NoxOpt(where=dict(...))`. This parameter accepts a dictionary that will be passed to
the `nox.session` decorator as keyword arguments when constructing each session. So, if
you wanted to run all sessions in a group with Python 3.10 and 3.11 you would configure:

```python
from noxopt import NoxOpt

# run all sessions in this group using Python 3.10 and 3.11
group = NoxOpt(where=dict(python=["3.10", "3.11"]))
```

## Automatic Tags

An additional nicety of NoxOpt is that is can automatically create tags based on the
names of your sessions using the `NoxOpt(auto_tag=True)` parameter. The idea behind this
parameter is that if you have a set of sessions with a common naming scheme like:

```python
from noxopt import NoxOpt, Session

group = NoxOpt(auto_tag=True)

@group.session
def check_python_tests(session: Session) -> None:
    ...

@group.session
def check_python_format(session: Session) -> None:
    ...

@group.session
def check_javascript_tests(session: Session) -> None:
    ...

@group.session
def check_javascript_format(session: Session) -> None:
    ...
```

NoxOpt will generate the following tags which, if run with `nox -t <tag>` will execute...

- `check` - all sessions
- `check-python` - only `check-python-tests` and `check-python-format`
- `check-javascript`- only `check-javascript-tests` and `check-javascript-format`

It does this by splitting every session name in the `NoxOpt` group on `-` characters
a tag where there are at least two or more sessions with a common prefix.
