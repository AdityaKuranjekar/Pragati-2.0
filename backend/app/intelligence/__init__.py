"""Pragati 2.0 adaptive engine v0.

Pure Python, no database, no LLM. Inputs are ordered attempt events and a prerequisite graph;
outputs are concept states, a diagnosis and one recommendation with its reason and trace.
See docs/architecture/decisions/ADR-003-learner-event-model.md and docs/pragati-2.0/PROTOTYPE_PLAN.md (S2).
"""
