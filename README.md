# NoxOpt

Nox sessions with options!

# Basic Usage

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

# Customizing Option

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
def sum_numbers(
    session: Session,
    nums: Annotated[list[int], Option(nargs="*", type=int)],
) -> None:
    session.log(sum(nums))

@nox.session
def multiply_numbers(
    session: Session,
    nums: Annotated[list[int], Option(nargs="*", type=int)],
) -> None:
    session.log(reduce(lambda x, y: x * y, nums, 0))
```

# Automatic Tags

An additional nicety of NoxOpt is that is can automatically create tags based on the
names of your sessions using the `auto_tag_depth` parameter. The idea behind this
parameter is that if you have a set of sessions with a common naming scheme - for example:

- `check-python-tests`
- `check-python-format`
- `check-javascript-tests`
- `check-javascript-format`

One might find it useful to be able to run say, all the sessions begining with
`check-python`. Thankfully if you set `NoxOpt(auto_tag_depth=2)`, NoxOpt will split
every session name on `-` characters and generate tags based on the first two words in
each. In this case, the set of tags would be:

- `check`
- `check-python`
- `check-javascript`

If you wish to disable this behavior in a given session you can set
`NoxOpt.session(tags=None)` when defining it.

# Using Multiple Nox Option Groups

It may be useful to divide sessions into different `NoxOpt` groups. This could be
because there a sessions that need to re-use the same parameter name, but with different
option setting, or because you need more control over automatic tags. To do this, all
you need to do is create two separate `NoxOpt` instances and add sessions to them.

The example below uses two `NoxOpt` instance to generate the following tags:

- `format`
- `check`
- `check-python`
- `check-javascript`

```python
from noxopt import NoxOpt, Session

formatters = NoxOpt(auto_tag_depth=1)
checkers = NoxOpt(auto_tag_depth=2)

@formatters.session
def format_python(session: Session) -> None:
    ...

@formatters.session
def format_javascript(session: Session) -> None:
    ...

@checkers.session
def check_python_tests(session: Session) -> None:
    ...

@checkers.session
def check_python_format(session: Session) -> None:
    ...

@checkers.session
def check_javascript_tests(session: Session) -> None:
    ...

@checkers.session
def check_javascript_format(session: Session) -> None:
    ...
```
