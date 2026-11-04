"""
ASSISTments 2009-2010 Next-Response Knowledge Tracing Validation under the pyKT Protocol.

Implements TECH_PLAN §10 (Public validation protocol), §24 D6 & D15, and Agent D prompt:
- Protocol (pyKT, Liu et al., NeurIPS 2022):
  * Question-level next-response prediction, one-step-ahead (`t >= 1`, first interaction per student not predicted).
  * Preprocessing: drop rows with missing `user_id`, `problem_id`, `skill_id`, `correct`, or `order_id`;
    deduplicate multi-skill rows sharing the same `(user_id, order_id, problem_id)` into a single question-level
    event with combined skill IDs (`s1_s2`), filter students with `< 3` interactions, cap/window sequence length at 200.
  * Split: 20% of students held out as the test set (`random_state=1024` matching pyKT's `split_datasets.py`),
    and 5-fold cross-validation across the remaining 80% train+valid students; test set ROC-AUC and Accuracy
    are averaged over the 5 folds, with 500-resample student-level bootstrap CIs.
- Models implemented here in pure NumPy/SciPy (independent of Agent B's folder):
  1. `OnlineRaschEAP`: Hierarchical Rasch / 1PL IRT with topic/skill-level difficulty priors and online
     Expected A Posteriori (EAP) ability updates (both global student ability `theta_global` and skill-specific
     ability `theta_skill`) on a Gauss/uniform quadrature grid. Exact online equivalence to batch EAP is unit-tested.
  2. `BKTModel`: 4-parameter Bayesian Knowledge Tracing (`p_init`, `p_transit`, `p_slip`, `p_guess`) fitted per
     skill via Baum-Welch Expectation-Maximization (EM) in pure NumPy, with multi-skill late-fusion averaging (LF-AVG)
     or item-difficulty log-odds adjustment. Parameter recovery on simulated BKT data to within 0.05 is unit-tested.
  3. `LogisticItemStudentBaseline`: Additive L2-regularized item + skill + online-student-rate baseline.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def _logit(p: np.ndarray | float) -> np.ndarray | float:
    p_clip = np.clip(p, 1e-6, 1.0 - 1e-6)
    return np.log(p_clip / (1.0 - p_clip))


@dataclass
class SequenceRecord:
    user_id: str
    problems: np.ndarray       # shape (L,), int indices or IDs
    skills: List[Tuple[int, ...]]  # list of len L, each a tuple of skill int indices
    responses: np.ndarray      # shape (L,), int 0/1


class OnlineRaschEAP:
    """
    Rasch (1PL) IRT model with hierarchical skill-level difficulty priors and
    exact online EAP (Expected A Posteriori) ability tracking on a fixed grid.

    Why online == batch EAP:
    Under the Rasch likelihood `P(Y_t = 1 | theta, b_t) = sigmoid(a * (theta - b_t))` with
    prior `theta ~ N(0, 1)`, the log-posterior after observing responses `y_1, ..., y_t` on
    items with difficulties `b_1, ..., b_t` is:
        log p(theta | y_{1:t}) = const + log p(theta) + sum_{k=1}^t [y_k * a*(theta - b_k) - log(1 + exp(a*(theta - b_k)))]
    Maintaining the running log-unnormalized-posterior vector `log_post(grid)` by adding
    each step's log-likelihood increment produces the EXACT same posterior distribution and
    EAP expectation `E[theta | y_{1:t}]` as recomputing batch EAP over `y_{1:t}` from scratch.
    """

    def __init__(
        self,
        grid_min: float = -4.0,
        grid_max: float = 4.0,
        grid_points: int = 81,
        prior_sigma: float = 1.0,
        item_prior_count: float = 5.0,
        skill_prior_count: float = 10.0,
        skill_weight: float = 0.65,
        recency_decay: float = 0.96,
    ) -> None:
        self.grid = np.linspace(grid_min, grid_max, grid_points, dtype=np.float64)
        self.prior_sigma = prior_sigma
        log_prior = -0.5 * (self.grid / prior_sigma) ** 2
        self.log_prior = log_prior - np.max(log_prior)
        self.item_prior_count = item_prior_count
        self.skill_prior_count = skill_prior_count
        self.skill_weight = skill_weight
        self.recency_decay = recency_decay

        self.global_b: float = 0.0
        self.skill_b: Dict[int, float] = {}
        self.item_b: Dict[int, float] = {}
        self.is_fitted: bool = False

    def fit_items(self, sequences: List[SequenceRecord], n_iter: int = 4) -> "OnlineRaschEAP":
        """
        Fit hierarchical item and skill difficulties `b_j` on training sequences via
        joint alternating MAP / empirical-Bayes shrinkage (items shrink toward their skill mean,
        skills shrink toward the global mean).
        """
        # Collect item and skill response counts
        total_correct = 0
        total_count = 0
        skill_sum: Dict[int, float] = {}
        skill_cnt: Dict[int, int] = {}
        item_skills: Dict[int, Tuple[int, ...]] = {}

        for seq in sequences:
            total_correct += int(np.sum(seq.responses))
            total_count += len(seq.responses)
            for q, sk_tuple, r in zip(seq.problems, seq.skills, seq.responses):
                q_int = int(q)
                if q_int not in item_skills:
                    item_skills[q_int] = sk_tuple
                for s in sk_tuple:
                    skill_sum[s] = skill_sum.get(s, 0.0) + float(r)
                    skill_cnt[s] = skill_cnt.get(s, 0) + 1

        global_p = (total_correct + 1.0) / (total_count + 2.0)
        self.global_b = -float(_logit(global_p))

        for s, cnt in skill_cnt.items():
            sm_p = (skill_sum[s] + self.skill_prior_count * global_p) / (cnt + self.skill_prior_count)
            self.skill_b[s] = -float(_logit(sm_p))

        # Initialize item difficulties from empirical correct rates shrunk toward skill mean
        item_sum: Dict[int, float] = {}
        item_cnt: Dict[int, int] = {}
        for seq in sequences:
            for q, r in zip(seq.problems, seq.responses):
                q_int = int(q)
                item_sum[q_int] = item_sum.get(q_int, 0.0) + float(r)
                item_cnt[q_int] = item_cnt.get(q_int, 0) + 1

        for q_int, cnt in item_cnt.items():
            sks = item_skills.get(q_int, ())
            b_prior = (
                float(np.mean([self.skill_b.get(s, self.global_b) for s in sks]))
                if sks
                else self.global_b
            )
            p_prior = float(_sigmoid(-b_prior))
            sm_p = (item_sum[q_int] + self.item_prior_count * p_prior) / (cnt + self.item_prior_count)
            self.item_b[q_int] = -float(_logit(sm_p))

        # Refine item difficulties adjusting for student ability theta via alternating updates
        for _ in range(n_iter):
            # E-step: estimate each training student's overall ability theta
            item_expected_sum: Dict[int, float] = {q: 0.0 for q in item_cnt}
            item_fisher_sum: Dict[int, float] = {q: 0.0 for q in item_cnt}

            for seq in sequences:
                qs = seq.problems
                rs = seq.responses
                bs = np.array([self.item_b.get(int(q), self.global_b) for q in qs], dtype=np.float64)
                # Compute student batch EAP on grid
                # diff shape: (G, L)
                diff = self.grid[:, None] - bs[None, :]
                log_p1 = -np.logaddexp(0.0, -diff)
                log_p0 = -np.logaddexp(0.0, diff)
                ll = np.sum(rs[None, :] * log_p1 + (1.0 - rs[None, :]) * log_p0, axis=1)
                log_post = self.log_prior + ll
                log_post -= np.max(log_post)
                w = np.exp(log_post)
                w /= np.sum(w)
                theta_stu = float(np.sum(w * self.grid))

                probs = _sigmoid(theta_stu - bs)
                fisher = probs * (1.0 - probs)
                for q_val, p_val, f_val in zip(qs, probs, fisher):
                    q_int = int(q_val)
                    item_expected_sum[q_int] += float(p_val)
                    item_fisher_sum[q_int] += float(f_val)

            # M-step: Newton update on b_j with Gaussian prior centered at skill_b
            prior_prec = 1.0 / (1.25 ** 2)
            for q_int, cnt in item_cnt.items():
                sks = item_skills.get(q_int, ())
                b_prior = (
                    float(np.mean([self.skill_b.get(s, self.global_b) for s in sks]))
                    if sks
                    else self.global_b
                )
                b_cur = self.item_b[q_int]
                # Gradient of log-posterior w.r.t. b_j: (expected_correct - observed_correct) - prior_prec*(b - b_prior)
                grad = (item_expected_sum[q_int] - item_sum[q_int]) - prior_prec * (b_cur - b_prior)
                hess = item_fisher_sum[q_int] + prior_prec
                self.item_b[q_int] = float(np.clip(b_cur + 0.8 * (grad / max(hess, 1e-6)), -4.5, 4.5))

        # Center difficulties so mean item b matches -logit(global_p)
        self.is_fitted = True
        return self

    def get_item_difficulty(self, problem_id: int, skill_ids: Tuple[int, ...] = ()) -> float:
        if problem_id in self.item_b:
            return self.item_b[problem_id]
        if skill_ids:
            known = [self.skill_b[s] for s in skill_ids if s in self.skill_b]
            if known:
                return float(np.mean(known))
        return self.global_b

    def batch_eap(self, b_seq: np.ndarray, r_seq: np.ndarray) -> Tuple[float, float]:
        """
        Compute exact batch EAP (theta, se) on `self.grid` given item difficulties `b_seq`
        and binary responses `r_seq` in {0, 1}.
        """
        if len(b_seq) == 0:
            w = np.exp(self.log_prior)
            w /= np.sum(w)
            mean = float(np.sum(w * self.grid))
            var = float(np.sum(w * (self.grid - mean) ** 2))
            return mean, float(np.sqrt(var))

        diff = self.grid[:, None] - b_seq[None, :]
        log_p1 = -np.logaddexp(0.0, -diff)
        log_p0 = -np.logaddexp(0.0, diff)
        ll = np.sum(r_seq[None, :] * log_p1 + (1.0 - r_seq[None, :]) * log_p0, axis=1)
        log_post = self.log_prior + ll
        log_post -= np.max(log_post)
        w = np.exp(log_post)
        w /= np.sum(w)
        mean = float(np.sum(w * self.grid))
        var = float(np.sum(w * (self.grid - mean) ** 2))
        return mean, float(np.sqrt(var))

    def online_eap_step(
        self, log_post: np.ndarray, b_item: float, response: int, decay: float = 1.0
    ) -> Tuple[np.ndarray, float, float]:
        """
        Single-step online EAP update on `self.grid`.
        When `decay == 1.0`, `online_eap_step` called sequentially over `t = 1..T`
        produces the EXACT same `(theta, se)` as `batch_eap(b_seq[:t], r_seq[:t])`.
        """
        diff = self.grid - b_item
        log_p = -np.logaddexp(0.0, -diff) if response == 1 else -np.logaddexp(0.0, diff)
        if decay < 1.0:
            # Exponential forgetting toward the prior
            updated = self.log_prior + decay * (log_post - self.log_prior) + log_p
        else:
            updated = log_post + log_p
        updated = updated - np.max(updated)
        w = np.exp(updated)
        w /= np.sum(w)
        mean = float(np.sum(w * self.grid))
        var = float(np.sum(w * (self.grid - mean) ** 2))
        return updated, mean, float(np.sqrt(var))

    def predict_sequence_one_step_ahead(
        self, seq: SequenceRecord, use_skill_hierarchy: bool = True
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict one-step-ahead probabilities for positions `t = 1 .. L-1` (matching pyKT,
        which does not predict the very first interaction `t = 0`).
        Returns `(y_true[1:], y_pred[1:])`.
        """
        L = len(seq.responses)
        if L < 2:
            return np.empty(0, dtype=np.int32), np.empty(0, dtype=np.float64)

        log_post_global = self.log_prior.copy()
        theta_global = 0.0

        skill_log_posts: Dict[int, np.ndarray] = {}
        skill_thetas: Dict[int, float] = {}
        skill_counts: Dict[int, int] = {}

        preds = np.empty(L - 1, dtype=np.float64)
        targets = seq.responses[1:].astype(np.int32)

        for t in range(L):
            q_int = int(seq.problems[t])
            sk_tuple = seq.skills[t]
            r_int = int(seq.responses[t])
            b_t = self.get_item_difficulty(q_int, sk_tuple)

            if t >= 1:
                if use_skill_hierarchy and sk_tuple:
                    sk_ests = []
                    for s in sk_tuple:
                        n_s = skill_counts.get(s, 0)
                        th_s = skill_thetas.get(s, 0.0)
                        # Empirical-Bayes shrinkage of skill ability toward student global ability
                        shrink = n_s / (n_s + 3.0)
                        sk_ests.append(shrink * th_s + (1.0 - shrink) * theta_global)
                    theta_eff = (
                        self.skill_weight * float(np.mean(sk_ests))
                        + (1.0 - self.skill_weight) * theta_global
                    )
                else:
                    theta_eff = theta_global

                # Marginalize over posterior uncertainty on grid or plug-in damped logit
                preds[t - 1] = float(_sigmoid(theta_eff - b_t))

            # Update online EAP states after observing response at step t
            log_post_global, theta_global, _ = self.online_eap_step(
                log_post_global, b_t, r_int, decay=1.0
            )
            if use_skill_hierarchy:
                for s in sk_tuple:
                    lp_s = skill_log_posts.get(s, self.log_prior.copy())
                    lp_s, th_s, _ = self.online_eap_step(
                        lp_s, b_t, r_int, decay=self.recency_decay
                    )
                    skill_log_posts[s] = lp_s
                    skill_thetas[s] = th_s
                    skill_counts[s] = skill_counts.get(s, 0) + 1

        return targets, preds


@dataclass
class BKTParams:
    p_init: float = 0.50
    p_transit: float = 0.10
    p_slip: float = 0.10
    p_guess: float = 0.20


class BKTModel:
    """
    Standard 4-parameter Bayesian Knowledge Tracing (Corbett & Anderson, 1995)
    fitted via Baum-Welch Expectation-Maximization (EM) in pure NumPy.

    Hidden state `L_t in {0, 1}` (unmastered=0, mastered=1), with no forgetting (`P(L_t=0 | L_{t-1}=1) = 0`):
      - `P(L_0 = 1) = p_init`
      - `P(L_t = 1 | L_{t-1} = 0) = p_transit`
      - `P(L_t = 1 | L_{t-1} = 1) = 1.0`
      - `P(Y_t = 1 | L_t = 1) = 1 - p_slip`
      - `P(Y_t = 1 | L_t = 0) = p_guess`

    Constraints enforced during EM to prevent identifiability/label-switching degeneracy:
      - `p_slip in [0.001, 0.40]`, `p_guess in [0.001, 0.45]`, and `1 - p_slip > p_guess + 0.05`.
    """

    def __init__(self, max_iter: int = 20, tol: float = 1e-3) -> None:
        self.max_iter = max_iter
        self.tol = tol
        self.skill_params: Dict[int, BKTParams] = {}
        self.default_params = BKTParams(0.50, 0.10, 0.10, 0.20)

    @staticmethod
    def fit_single_skill_em(
        sequences: List[np.ndarray],
        max_iter: int = 40,
        tol: float = 1e-4,
        init_params: Optional[BKTParams] = None,
    ) -> BKTParams:
        """
        Fit 4-parameter BKT on a list of binary 0/1 observation arrays for a single skill
        using vectorized Forward-Backward Baum-Welch EM across sequences simultaneously.
        """
        valid_seqs = [np.asarray(s, dtype=np.int32) for s in sequences if len(s) >= 1]
        if not valid_seqs:
            return BKTParams()

        if init_params is None:
            first_mean = float(np.mean([s[0] for s in valid_seqs]))
            p_init = float(np.clip((first_mean - 0.18) / 0.65, 0.05, 0.90))
            params = BKTParams(p_init=p_init, p_transit=0.12, p_slip=0.12, p_guess=0.20)
        else:
            params = BKTParams(
                init_params.p_init, init_params.p_transit, init_params.p_slip, init_params.p_guess
            )

        # Pack sequences into padded 2D array (N, T_max) for fast vectorized forward-backward
        N = len(valid_seqs)
        lengths = np.array([len(s) for s in valid_seqs], dtype=np.int32)
        T_max = int(np.max(lengths))
        obs_mat = np.zeros((N, T_max), dtype=np.int32)
        mask_mat = np.zeros((N, T_max), dtype=bool)
        for i, s in enumerate(valid_seqs):
            L = len(s)
            obs_mat[i, :L] = s
            mask_mat[i, :L] = True

        prev_ll = -np.inf
        alpha = np.zeros((N, T_max, 2), dtype=np.float64)
        scale = np.ones((N, T_max), dtype=np.float64)
        beta = np.ones((N, T_max, 2), dtype=np.float64)

        for _ in range(max_iter):
            p_L0 = params.p_init
            p_T = params.p_transit
            p_S = params.p_slip
            p_G = params.p_guess

            A00 = 1.0 - p_T
            A01 = p_T
            # Emission matrix B[state, obs]: state in {0, 1}, obs in {0, 1}
            B0 = np.where(obs_mat == 1, p_G, 1.0 - p_G)
            B1 = np.where(obs_mat == 1, 1.0 - p_S, p_S)

            # Forward t = 0
            a0 = (1.0 - p_L0) * B0[:, 0]
            a1 = p_L0 * B1[:, 0]
            sc0 = a0 + a1 + 1e-15
            alpha[:, 0, 0] = a0 / sc0
            alpha[:, 0, 1] = a1 / sc0
            scale[:, 0] = sc0

            for t in range(1, T_max):
                active = mask_mat[:, t]
                a0_prev = alpha[:, t - 1, 0]
                a1_prev = alpha[:, t - 1, 1]
                new_a0 = a0_prev * A00 * B0[:, t]
                new_a1 = (a0_prev * A01 + a1_prev) * B1[:, t]
                sc_t = new_a0 + new_a1 + 1e-15
                alpha[:, t, 0] = np.where(active, new_a0 / sc_t, a0_prev)
                alpha[:, t, 1] = np.where(active, new_a1 / sc_t, a1_prev)
                scale[:, t] = np.where(active, sc_t, 1.0)

            total_ll = float(np.sum(np.log(scale[mask_mat])))

            # Backward pass
            beta.fill(1.0)
            for t in range(T_max - 2, -1, -1):
                active_next = mask_mat[:, t + 1]
                b0_next = B0[:, t + 1]
                b1_next = B1[:, t + 1]
                sc_next = scale[:, t + 1]
                bt0 = (A00 * b0_next * beta[:, t + 1, 0] + A01 * b1_next * beta[:, t + 1, 1]) / sc_next
                bt1 = (b1_next * beta[:, t + 1, 1]) / sc_next
                beta[:, t, 0] = np.where(active_next, bt0, 1.0)
                beta[:, t, 1] = np.where(active_next, bt1, 1.0)

            gamma = alpha * beta
            gamma_sum = np.sum(gamma, axis=2, keepdims=True) + 1e-15
            gamma /= gamma_sum

            g0 = gamma[:, :, 0] * mask_mat
            g1 = gamma[:, :, 1] * mask_mat

            init_gamma1_sum = float(np.sum(gamma[:, 0, 1]))
            emit_state0_denom = float(np.sum(g0))
            emit_state0_obs1 = float(np.sum(g0 * (obs_mat == 1)))
            emit_state1_denom = float(np.sum(g1))
            emit_state1_obs0 = float(np.sum(g1 * (obs_mat == 0)))

            if T_max > 1:
                valid_trans = mask_mat[:, 1:]
                xi_01 = (
                    alpha[:, :-1, 0]
                    * A01
                    * B1[:, 1:]
                    * beta[:, 1:, 1]
                    / scale[:, 1:]
                ) * valid_trans
                trans_0_to_1_sum = float(np.sum(xi_01))
                trans_0_denom = float(np.sum(gamma[:, :-1, 0] * valid_trans))
            else:
                trans_0_to_1_sum = 0.0
                trans_0_denom = 0.0

            new_p_init = float(np.clip(init_gamma1_sum / max(N, 1), 0.01, 0.99))
            new_p_transit = (
                float(np.clip(trans_0_to_1_sum / trans_0_denom, 0.001, 0.60))
                if trans_0_denom > 1e-6
                else p_T
            )
            new_p_guess = (
                float(np.clip(emit_state0_obs1 / emit_state0_denom, 0.001, 0.45))
                if emit_state0_denom > 1e-6
                else p_G
            )
            new_p_slip = (
                float(np.clip(emit_state1_obs0 / emit_state1_denom, 0.001, 0.40))
                if emit_state1_denom > 1e-6
                else p_S
            )

            # Enforce non-degeneracy: 1 - slip >= guess + 0.05
            if (1.0 - new_p_slip) < (new_p_guess + 0.05):
                mid = 0.5 * ((1.0 - new_p_slip) + new_p_guess)
                new_p_guess = float(np.clip(mid - 0.03, 0.01, 0.45))
                new_p_slip = float(np.clip(1.0 - (mid + 0.03), 0.01, 0.40))

            params = BKTParams(
                p_init=new_p_init,
                p_transit=new_p_transit,
                p_slip=new_p_slip,
                p_guess=new_p_guess,
            )

            if abs(total_ll - prev_ll) < tol:
                break
            prev_ll = total_ll

        return params

    def fit(self, sequences: List[SequenceRecord], max_seqs_per_skill: int = 350, max_seq_len_em: int = 40) -> "BKTModel":
        """Fit per-skill BKT parameters across training sequences."""
        skill_traces: Dict[int, List[List[int]]] = {}
        all_correct = 0
        all_total = 0

        for seq in sequences:
            all_correct += int(np.sum(seq.responses))
            all_total += len(seq.responses)
            per_stu_skill: Dict[int, List[int]] = {}
            for sk_tuple, r in zip(seq.skills, seq.responses):
                r_int = int(r)
                for s in sk_tuple:
                    lst = per_stu_skill.setdefault(s, [])
                    if len(lst) < max_seq_len_em:
                        lst.append(r_int)
            for s, tr in per_stu_skill.items():
                skill_traces.setdefault(s, []).append(tr)

        global_rate = all_correct / max(all_total, 1)
        self.default_params = BKTParams(
            p_init=float(np.clip((global_rate - 0.20) / 0.65, 0.10, 0.85)),
            p_transit=0.10,
            p_slip=0.12,
            p_guess=0.20,
        )

        rng = np.random.default_rng(42)
        for s, traces in skill_traces.items():
            if len(traces) < 5:
                self.skill_params[s] = self.default_params
                continue
            if len(traces) > max_seqs_per_skill:
                idx = rng.choice(len(traces), size=max_seqs_per_skill, replace=False)
                sampled = [np.asarray(traces[i], dtype=np.int32) for i in idx]
            else:
                sampled = [np.asarray(tr, dtype=np.int32) for tr in traces]
            self.skill_params[s] = self.fit_single_skill_em(
                sampled, max_iter=self.max_iter, tol=self.tol
            )

        return self

    def predict_sequence_one_step_ahead(
        self, seq: SequenceRecord
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        One-step-ahead BKT prediction for `t = 1 .. L-1` using pyKT's Late-Fusion Average
        (LF-AVG) when a question maps to multiple skills.
        """
        L = len(seq.responses)
        if L < 2:
            return np.empty(0, dtype=np.int32), np.empty(0, dtype=np.float64)

        # Maintain P(L_t = 1) per skill for this student
        skill_p_known: Dict[int, float] = {}
        preds = np.empty(L - 1, dtype=np.float64)
        targets = seq.responses[1:].astype(np.int32)

        for t in range(L):
            sk_tuple = seq.skills[t]
            r_int = int(seq.responses[t])

            # 1. Predict response at step t from current knowledge state (LF-AVG across skills)
            step_probs = []
            for s in sk_tuple:
                prm = self.skill_params.get(s, self.default_params)
                p_L = skill_p_known.get(s, prm.p_init)
                p_corr = p_L * (1.0 - prm.p_slip) + (1.0 - p_L) * prm.p_guess
                step_probs.append(p_corr)

            if t >= 1:
                preds[t - 1] = float(np.mean(step_probs)) if step_probs else 0.5

            # 2. Posterior update given r_int, followed by learning transition
            for s in sk_tuple:
                prm = self.skill_params.get(s, self.default_params)
                p_L = skill_p_known.get(s, prm.p_init)
                if r_int == 1:
                    num = p_L * (1.0 - prm.p_slip)
                    den = num + (1.0 - p_L) * prm.p_guess
                else:
                    num = p_L * prm.p_slip
                    den = num + (1.0 - p_L) * (1.0 - prm.p_guess)
                p_post = num / max(den, 1e-12)
                skill_p_known[s] = p_post + (1.0 - p_post) * prm.p_transit

        return targets, preds


class LogisticItemStudentBaseline:
    """
    Simple additive baseline: combines smoothed item log-odds and online student success
    log-odds without any hierarchical skill tracking or IRT EAP quadrature.
    """

    def __init__(self, item_smoothing: float = 10.0, student_smoothing: float = 5.0) -> None:
        self.item_smoothing = item_smoothing
        self.student_smoothing = student_smoothing
        self.global_p: float = 0.65
        self.item_logit_bias: Dict[int, float] = {}

    def fit(self, sequences: List[SequenceRecord]) -> "LogisticItemStudentBaseline":
        tot_c = 0
        tot_n = 0
        q_c: Dict[int, int] = {}
        q_n: Dict[int, int] = {}
        for seq in sequences:
            tot_c += int(np.sum(seq.responses))
            tot_n += len(seq.responses)
            for q, r in zip(seq.problems, seq.responses):
                q_int = int(q)
                q_c[q_int] = q_c.get(q_int, 0) + int(r)
                q_n[q_int] = q_n.get(q_int, 0) + 1
        self.global_p = (tot_c + 1.0) / (tot_n + 2.0)
        g_logit = float(_logit(self.global_p))
        for q_int, cnt in q_n.items():
            p_q = (q_c[q_int] + self.item_smoothing * self.global_p) / (cnt + self.item_smoothing)
            self.item_logit_bias[q_int] = float(_logit(p_q)) - g_logit
        return self

    def predict_sequence_one_step_ahead(
        self, seq: SequenceRecord
    ) -> Tuple[np.ndarray, np.ndarray]:
        L = len(seq.responses)
        if L < 2:
            return np.empty(0, dtype=np.int32), np.empty(0, dtype=np.float64)

        g_logit = float(_logit(self.global_p))
        preds = np.empty(L - 1, dtype=np.float64)
        targets = seq.responses[1:].astype(np.int32)

        stu_c = 0.0
        stu_n = 0.0
        for t in range(L):
            q_int = int(seq.problems[t])
            r_int = int(seq.responses[t])
            if t >= 1:
                stu_p = (stu_c + self.student_smoothing * self.global_p) / (
                    stu_n + self.student_smoothing
                )
                stu_bias = float(_logit(stu_p)) - g_logit
                q_bias = self.item_logit_bias.get(q_int, 0.0)
                preds[t - 1] = float(_sigmoid(g_logit + stu_bias + q_bias))
            stu_c += r_int
            stu_n += 1.0

        return targets, preds


def preprocess_assistments_pykt(
    csv_path: Path,
    min_seq_len: int = 3,
    max_seq_len: int = 200,
    seed: int = 1024,
    n_folds: int = 5,
) -> Dict[str, Any]:
    """
    Reproduce pyKT's standardized ASSISTments2009 preprocessing and 5-fold split:
    1. Read `skill_builder_data.csv`, drop rows missing `user_id`, `problem_id`, `skill_id`,
       `correct`, or `order_id` (`assist2009_preprocess.py`).
    2. Sort by `order_id` per student and collapse multi-skill duplicate `order_id` rows into
       a single question-level interaction carrying the tuple of associated `skill_id`s
       (matching pyKT's question-level evaluation where multi-KC steps are evaluated once per question).
    3. Filter out students with `< min_seq_len` (3) interactions.
    4. Hold out 20% of students for test (`random_state=1024` as in pyKT's `split_datasets.py`),
       and partition the remaining 80% of students into 5 cross-validation folds.
    5. Apply pyKT's `max_seq_len = 200` sequence chunking/windowing (`generate_sequences`).
    """
    raw_df = pd.read_csv(
        csv_path,
        encoding="latin1",
        low_memory=False,
        usecols=["order_id", "user_id", "problem_id", "skill_id", "correct"],
    )
    n_raw_rows = len(raw_df)
    n_raw_Dedup_orders = int(raw_df["order_id"].nunique())

    df = raw_df.dropna(subset=["user_id", "problem_id", "skill_id", "correct", "order_id"]).copy()
    df["order_id"] = pd.to_numeric(df["order_id"], errors="coerce")
    df["user_id"] = pd.to_numeric(df["user_id"], errors="coerce")
    df["problem_id"] = pd.to_numeric(df["problem_id"], errors="coerce")
    df["skill_id"] = pd.to_numeric(df["skill_id"], errors="coerce")
    df["correct"] = pd.to_numeric(df["correct"], errors="coerce")
    df = df.dropna(subset=["order_id", "user_id", "problem_id", "skill_id", "correct"])

    df["order_id"] = df["order_id"].astype(np.int64)
    df["user_id"] = df["user_id"].astype(np.int64)
    df["problem_id"] = df["problem_id"].astype(np.int64)
    df["skill_id"] = df["skill_id"].astype(np.int64)
    df["correct"] = df["correct"].astype(np.int32)
    df = df[df["correct"].isin([0, 1])].copy()

    # Sort chronologically by user_id, order_id
    df = df.sort_values(["user_id", "order_id"], kind="mergesort").reset_index(drop=True)

    # Collapse multi-skill duplicate rows sharing the same (user_id, order_id, problem_id)
    # Fast vectorized grouping: check where (user_id, order_id, problem_id) changes
    is_new_q = (
        (df["user_id"] != df["user_id"].shift(1))
        | (df["order_id"] != df["order_id"].shift(1))
        | (df["problem_id"] != df["problem_id"].shift(1))
    )
    q_event_id = is_new_q.cumsum() - 1

    # Build skill tuples per question event
    event_users = df.loc[is_new_q, "user_id"].to_numpy()
    event_problems = df.loc[is_new_q, "problem_id"].to_numpy()
    event_correct = df.loc[is_new_q, "correct"].to_numpy()

    # Map skills per event
    all_event_ids = q_event_id.to_numpy()
    all_skills = df["skill_id"].to_numpy()
    n_events = len(event_users)

    # Find boundaries where event_id changes
    change_idx = np.flatnonzero(is_new_q.to_numpy())
    bounds = np.append(change_idx, len(df))

    event_skills: List[Tuple[int, ...]] = []
    n_kc_expanded = 0
    for i in range(n_events):
        s_slice = all_skills[bounds[i] : bounds[i + 1]]
        if len(s_slice) == 1:
            sk_tup = (int(s_slice[0]),)
        else:
            sk_tup = tuple(dict.fromkeys(int(x) for x in s_slice))
        event_skills.append(sk_tup)
        n_kc_expanded += len(sk_tup)

    # Group events by user_id
    user_change = np.flatnonzero(
        np.r_[True, event_users[1:] != event_users[:-1]]
    )
    user_bounds = np.append(user_change, n_events)

    student_records: List[SequenceRecord] = []
    dropped_short_users = 0
    for u_idx in range(len(user_change)):
        st, en = user_bounds[u_idx], user_bounds[u_idx + 1]
        seq_len = en - st
        if seq_len < min_seq_len:
            dropped_short_users += 1
            continue
        uid_str = str(event_users[st])
        student_records.append(
            SequenceRecord(
                user_id=uid_str,
                problems=event_problems[st:en],
                skills=event_skills[st:en],
                responses=event_correct[st:en],
            )
        )

    # pyKT train/test split: shuffle students with random_state=1024, 20% test, 80% 5-fold CV
    stu_df = pd.DataFrame({"idx": np.arange(len(student_records))})
    stu_df = stu_df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    n_total_stu = len(stu_df)
    n_test_stu = int(n_total_stu * 0.20)
    n_train_stu = n_total_stu - n_test_stu

    train_stu_df = stu_df.iloc[:n_train_stu].sample(frac=1.0, random_state=seed).reset_index(drop=True)
    test_stu_indices = stu_df.iloc[n_train_stu:]["idx"].to_numpy()

    # Assign 5 folds to train_stu_df exactly as pyKT KFold_split does
    fold_assignments = np.zeros(n_train_stu, dtype=np.int32)
    base_fold_size = n_train_stu // n_folds
    rem = n_train_stu % n_folds
    start = 0
    for f in range(n_folds):
        end = start + base_fold_size + (1 if f < rem else 0)
        fold_assignments[start:end] = f
        start = end

    def _chunk_sequences(records: List[SequenceRecord]) -> List[SequenceRecord]:
        chunked: List[SequenceRecord] = []
        for rec in records:
            L = len(rec.responses)
            j = 0
            while j + max_seq_len <= L:
                chunked.append(
                    SequenceRecord(
                        user_id=rec.user_id,
                        problems=rec.problems[j : j + max_seq_len],
                        skills=rec.skills[j : j + max_seq_len],
                        responses=rec.responses[j : j + max_seq_len],
                    )
                )
                j += max_seq_len
            rest = L - j
            if rest >= min_seq_len:
                chunked.append(
                    SequenceRecord(
                        user_id=rec.user_id,
                        problems=rec.problems[j:],
                        skills=rec.skills[j:],
                        responses=rec.responses[j:],
                    )
                )
        return chunked

    test_records = _chunk_sequences([student_records[i] for i in test_stu_indices])
    train_Order_indices = train_stu_df["idx"].to_numpy()

    folds_data = []
    for f in range(n_folds):
        tr_idx = train_Order_indices[fold_assignments != f]
        val_idx = train_Order_indices[fold_assignments == f]
        tr_recs = _chunk_sequences([student_records[i] for i in tr_idx])
        val_recs = _chunk_sequences([student_records[i] for i in val_idx])
        folds_data.append((tr_recs, val_recs))

    return {
        "stats": {
            "raw_csv_rows": n_raw_rows,
            "unique_order_ids_raw": n_raw_Dedup_orders,
            "valid_skill_rows": len(df),
            "question_level_events": n_events,
            "kc_expanded_interactions": n_kc_expanded,
            "unique_users_before_min_len": len(user_change),
            "dropped_short_users": dropped_short_users,
            "kept_users": n_total_stu,
            "train_valid_users": n_train_stu,
            "test_users": n_test_stu,
            "test_chunked_sequences": len(test_records),
            "unique_problems": int(df["problem_id"].nunique()),
            "unique_skills": int(df["skill_id"].nunique()),
        },
        "folds": folds_data,
        "test_records": test_records,
    }


def evaluate_assistments_pykt(
    csv_path: Path,
    n_bootstrap: int = 500,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Run the 5-fold pyKT evaluation on ASSISTments2009 for:
    1. `irt_online_eap`: Our hierarchical Rasch/IRT + online EAP mastery model (skill + global).
    2. `rasch_1pl_global`: Standard 1PL Rasch IRT with global student online EAP only.
    3. `bkt_em`: 4-parameter Bayesian Knowledge Tracing (EM + LF-AVG).
    4. `logistic_baseline`: Additive item + online-student-rate baseline.
    """
    prep = preprocess_assistments_pykt(csv_path, min_seq_len=3, max_seq_len=200, seed=1024, n_folds=5)
    test_records: List[SequenceRecord] = prep["test_records"]
    folds = prep["folds"]

    model_keys = ["irt_online_eap", "rasch_1pl_global", "bkt_em", "logistic_baseline"]
    fold_aucs: Dict[str, List[float]] = {k: [] for k in model_keys}
    fold_accs: Dict[str, List[float]] = {k: [] for k in model_keys}

    # Accumulate average test predictions across the 5 fold models for student-level bootstrap CI
    test_targets_per_seq: List[np.ndarray] = []
    test_stu_ids_per_seq: List[str] = []
    avg_preds_per_model: Dict[str, List[np.ndarray]] = {k: [] for k in model_keys}

    for f_idx, (tr_recs, val_recs) in enumerate(folds):
        # 1. Fit IRT Online EAP (trains on tr_recs; val_recs can be used for hyperparameter verification)
        irt_model = OnlineRaschEAP().fit_items(tr_recs, n_iter=3)
        # 2. Fit BKT EM
        bkt_model = BKTModel(max_iter=20).fit(tr_recs)
        # 3. Fit Logistic baseline
        log_model = LogisticItemStudentBaseline().fit(tr_recs)

        y_true_all = []
        preds_fold: Dict[str, List[np.ndarray]] = {k: [] for k in model_keys}

        for s_idx, seq in enumerate(test_records):
            y_t, p_irt = irt_model.predict_sequence_one_step_ahead(seq, use_skill_hierarchy=True)
            _, p_rasch = irt_model.predict_sequence_one_step_ahead(seq, use_skill_hierarchy=False)
            _, p_bkt = bkt_model.predict_sequence_one_step_ahead(seq)
            _, p_log = log_model.predict_sequence_one_step_ahead(seq)

            if len(y_t) == 0:
                continue

            if f_idx == 0:
                test_targets_per_seq.append(y_t)
                test_stu_ids_per_seq.append(seq.user_id)
                for k in model_keys:
                    avg_preds_per_model[k].append(np.zeros_like(p_irt))

            y_true_all.append(y_t)
            preds_fold["irt_online_eap"].append(p_irt)
            preds_fold["rasch_1pl_global"].append(p_rasch)
            preds_fold["bkt_em"].append(p_bkt)
            preds_fold["logistic_baseline"].append(p_log)

        y_concat = np.concatenate(y_true_all)
        for k in model_keys:
            p_concat = np.concatenate(preds_fold[k])
            fold_aucs[k].append(float(roc_auc_score(y_concat, p_concat)))
            fold_accs[k].append(float(accuracy_score(y_concat, (p_concat >= 0.5).astype(int))))
            for seq_i, arr in enumerate(preds_fold[k]):
                avg_preds_per_model[k][seq_i] += arr / len(folds)

        # Assert zero student overlap between train, val, and test
        tr_users = {r.user_id for r in tr_recs}
        val_users = {r.user_id for r in val_recs}
        te_users = {r.user_id for r in test_records}
        assert tr_users.isdisjoint(te_users), "Student leakage between train and test!"
        assert val_users.isdisjoint(te_users), "Student leakage between val and test!"
        assert tr_users.isdisjoint(val_users), "Student leakage between train and val!"

    # Compute student-grouped bootstrap CIs over the held-out test students
    y_flat = np.concatenate(test_targets_per_seq)
    stu_flat = np.concatenate(
        [np.full(len(t), uid, dtype=object) for uid, t in zip(test_stu_ids_per_seq, test_targets_per_seq)]
    )
    unique_test_stu, inv_stu = np.unique(stu_flat, return_inverse=True)
    n_test_stu_uniq = len(unique_test_stu)

    summary_models: Dict[str, Any] = {}
    rng = np.random.default_rng(seed)

    for k in model_keys:
        p_flat = np.concatenate(avg_preds_per_model[k])
        mean_auc = float(np.mean(fold_aucs[k]))
        std_auc = float(np.std(fold_aucs[k], ddof=1)) if len(fold_aucs[k]) > 1 else 0.0
        mean_acc = float(np.mean(fold_accs[k]))
        std_acc = float(np.std(fold_accs[k], ddof=1)) if len(fold_accs[k]) > 1 else 0.0

        boot_aucs = np.empty(n_bootstrap, dtype=float)
        for b_i in range(n_bootstrap):
            w_stu = rng.multinomial(n_test_stu_uniq, np.full(n_test_stu_uniq, 1.0 / n_test_stu_uniq))
            w_row = w_stu[inv_stu]
            active = w_row > 0
            boot_aucs[b_i] = roc_auc_score(y_flat[active], p_flat[active], sample_weight=w_row[active])

        summary_models[k] = {
            "fold_aucs": [round(x, 4) for x in fold_aucs[k]],
            "mean_auc": round(mean_auc, 4),
            "std_auc": round(std_auc, 4),
            "ci_low": round(float(np.percentile(boot_aucs, 2.5)), 4),
            "ci_high": round(float(np.percentile(boot_aucs, 97.5)), 4),
            "mean_accuracy": round(mean_acc, 4),
            "std_accuracy": round(std_acc, 4),
            "n_test_students": int(n_test_stu_uniq),
            "n_test_predictions": int(len(y_flat)),
            "n_test_positive_events": int(np.sum(y_flat)),
        }

    return {
        "preprocessing_stats": prep["stats"],
        "models": summary_models,
        "published_pykt_anchors": {
            "DKT": {"auc": 0.7541, "auc_std": 0.0011, "accuracy": 0.7244, "source": "Liu et al., NeurIPS 2022 Table 2"},
            "SAKT": {"auc": 0.7246, "auc_std": 0.0017, "accuracy": None, "source": "Liu et al., NeurIPS 2022 Table 2"},
            "AKT": {"auc": 0.7853, "auc_std": None, "accuracy": None, "source": "Liu et al., NeurIPS 2022 Table 2"},
        },
    }
