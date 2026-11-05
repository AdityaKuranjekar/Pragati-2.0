"""Prerequisite DAG. Edge direction: prerequisite -> dependent. Rejects cycles and unknown nodes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

REVIEW_STATES = frozenset({"proposed", "reviewed"})


@dataclass(frozen=True)
class Edge:
    prereq: str
    dependent: str
    review_status: str = "proposed"


class Graph:
    def __init__(self, nodes: Iterable[str], edges: Iterable[Edge]):
        self.nodes = tuple(dict.fromkeys(nodes))
        node_set = set(self.nodes)
        self.edges = tuple(edges)
        self._pre: dict[str, set[str]] = {n: set() for n in self.nodes}
        self._dep: dict[str, set[str]] = {n: set() for n in self.nodes}
        for e in self.edges:
            if e.prereq not in node_set or e.dependent not in node_set:
                raise ValueError(f"edge references unknown node: {e.prereq} -> {e.dependent}")
            if e.prereq == e.dependent:
                raise ValueError(f"self-loop on {e.prereq}")
            if e.review_status not in REVIEW_STATES:
                raise ValueError(f"unknown review_status {e.review_status}")
            if e.dependent in self._pre and e.prereq in self._pre[e.dependent]:
                raise ValueError(f"duplicate edge {e.prereq} -> {e.dependent}")
            self._pre[e.dependent].add(e.prereq)
            self._dep[e.prereq].add(e.dependent)
        self._topo = self._toposort()

    def _toposort(self) -> tuple[str, ...]:
        indeg = {n: len(self._pre[n]) for n in self.nodes}
        order = [n for n in self.nodes if indeg[n] == 0]
        out = []
        while order:
            n = order.pop(0)
            out.append(n)
            for d in sorted(self._dep[n]):
                indeg[d] -= 1
                if indeg[d] == 0:
                    order.append(d)
        if len(out) != len(self.nodes):
            raise ValueError("prerequisite graph contains a cycle")
        return tuple(out)

    def topo_order(self) -> tuple[str, ...]:
        return self._topo

    def prereqs(self, node: str) -> frozenset[str]:
        return frozenset(self._pre[node])

    def dependents(self, node: str) -> frozenset[str]:
        return frozenset(self._dep[node])

    def ancestors(self, node: str) -> frozenset[str]:
        seen, stack = set(), list(self._pre[node])
        while stack:
            n = stack.pop()
            if n not in seen:
                seen.add(n)
                stack.extend(self._pre[n])
        return frozenset(seen)

    def descendants(self, node: str) -> frozenset[str]:
        seen, stack = set(), list(self._dep[node])
        while stack:
            n = stack.pop()
            if n not in seen:
                seen.add(n)
                stack.extend(self._dep[n])
        return frozenset(seen)

    def edge(self, prereq: str, dependent: str) -> Edge:
        for e in self.edges:
            if e.prereq == prereq and e.dependent == dependent:
                return e
        raise KeyError(f"no edge {prereq} -> {dependent}")

    def without_edge(self, prereq: str, dependent: str) -> "Graph":
        """Sensitivity helper (E7): same graph with one prerequisite link removed."""
        kept = [e for e in self.edges if not (e.prereq == prereq and e.dependent == dependent)]
        return Graph(self.nodes, kept)
