"""E3/E9 simulator package. `simulator.py` is independent of the estimator: it must not import
anything from backend/app/intelligence (enforced by ml/evaluation/tests/test_sim.py). Only `compare.py`,
the harness, imports the engine, because it has to run it."""
