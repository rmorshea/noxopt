from typing import Annotated

from nox import Session, parametrize

from noxopt import NoxOpt, Option


group = NoxOpt()


@group.session
@parametrize("num", [1, 2, 3])
def log_nums(session: Session, num: int, mult: Annotated[int, Option()]) -> None:
    session.log(num * mult)
