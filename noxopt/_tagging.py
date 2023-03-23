from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    # avoid import error if this private module ever changes in the future
    from nox._decorators import Func


class AutoTag:
    r"""Session auto tagging utility

    Construct a graph of words, and at every branching point in the graph it creates a
    tag. For example the session names:

    - `a-x-1`
    - `a-x-2`
    - `a-y-1`
    - `a-y-2`
    - `b-x-1`
    - `b-x-2`

    Would create the graph:

    ```
          *
         / \
        a   b
       /\    \
      x  y    x
     /|  |\   |\
    1 2  1 2  1 2
    ```

    At every branching point in the graph a tag would be generated and applied to all
    functions with that prefix. So the tags would be:

    - `a`
    - `a-x`
    - `a-y`
    - `b-x`

    This isn't always perfect since technically, we could subtitute the tag `b-x` for
    just `b` since the shorted common string between `b-x-1` and `b-x-2` is `b`. But
    it works most of the time, and it makes the algorithm a bit easier to reason about.
    """

    def __init__(self, sep: str = "-"):
        self._sep = sep
        self._tag_tree = _TagNode()

    def add_func(self, name: str, func: Func) -> None:
        node = self._tag_tree

        # each branching point in the graph represents a tag
        for word in name.split(self._sep):
            if len(node.children) > 1:
                # this is a branching point in the graph
                node.add_tag(func)

            if word in node.children:
                node = node.children[word]
            else:
                if len(node.children) == 1:
                    node.add_tag(func)
                    # We're about to create a new branching point - funcs added earlier
                    # will not have this node's tag.
                    node.retroactively_add_tags()
                node = node.add_node(word, self._sep)

        # add this func to the last node
        node.add_func(func)


class _TagNode:
    def __init__(self, parent: _TagNode | None = None, tag: str | None = None):
        self.parent = parent
        self.tag = tag
        self.funcs: list[Func] = []
        self.children: dict[str, _TagNode] = {}

    def add_node(self, word: str, sep: str) -> _TagNode:
        tag = f"{self.tag}{sep}{word}" if self.tag else word
        child = self.children[word] = _TagNode(self, tag)
        return child

    def add_func(self, func: Func) -> None:
        self.funcs.append(func)

    def add_tag(self, func: Func) -> None:
        if self.tag:
            func.tags.append(self.tag)

    def retroactively_add_tags(self) -> None:
        to_visit = [self]
        while to_visit:
            node = to_visit.pop()
            for f in node.funcs:
                self.add_tag(f)
            to_visit.extend(node.children.values())
