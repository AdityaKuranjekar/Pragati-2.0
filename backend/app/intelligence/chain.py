"""Demo chain (taxonomy-valid JEE nodes, PROTOTYPE_PLAN.md §2). Both edges are PROPOSED and must be
shown as unreviewed until a teacher reviews them (B14)."""
from __future__ import annotations

from .events import AttemptEvent
from .graph import Edge, Graph

A = "jee.math.complex_numbers.algebra_complex_argand"
R = "jee.math.quadratic_equations.roots_nature"
F = "jee.math.quadratic_equations.equation_formation"

NAMES = {
    A: "Algebra of complex numbers",
    R: "Nature of roots and discriminant",
    F: "Formation of quadratic equations",
}

DEMO_GOAL = F


def demo_graph(review_status: str = "proposed") -> Graph:
    return Graph([A, R, F], [Edge(A, R, review_status), Edge(R, F, review_status)])


def make_events(learner: str, script: list[tuple[str, bool]], start_seq: int = 0,
                prefix: str = "e") -> list[AttemptEvent]:
    """script: list of (concept_id, correct). Event ids are deterministic from learner and position."""
    out = []
    for i, (concept, correct) in enumerate(script):
        seq = start_seq + i
        out.append(AttemptEvent(
            event_id=f"{prefix}-{learner}-{seq}", learner_id=learner, concept_id=concept,
            item_id=f"item-{concept.split('.')[-1]}-{seq % 20}", correct=correct, seq=seq))
    return out


# Demo fixtures ([DEMO FIXTURE]): two learners with different evidence on the same chain.
LEARNER_A = [(A, True)] * 5 + [(R, False)] * 3          # strong algebra, weak roots
LEARNER_B = [(A, False)] * 3                             # weak algebra foundation
