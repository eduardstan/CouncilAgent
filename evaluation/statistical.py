"""Statistical estimators for CouncilAgent benchmark analysis.

All estimators require benchmark extras: uv pip install 'council-agent[benchmark]'
(scipy, statsmodels, numpy, scikit-learn).

Approved import: evaluation/ may import council/ (see architecture.md).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# bootstrap_ci
# ---------------------------------------------------------------------------


def bootstrap_ci(
    values: list[float],
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Paired bootstrap confidence interval for the mean.

    Returns (lower, upper) at (1 - alpha) confidence level.
    Raises ValueError if values is empty.
    """
    if not values:
        raise ValueError("bootstrap_ci: values must be non-empty")

    rng = random.Random(seed)
    n = len(values)
    boot_means: list[float] = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        boot_means.append(sum(sample) / n)

    boot_means.sort()
    lo_idx = int(alpha / 2 * n_boot)
    hi_idx = int((1 - alpha / 2) * n_boot) - 1
    return boot_means[lo_idx], boot_means[hi_idx]


# ---------------------------------------------------------------------------
# wilcoxon_test
# ---------------------------------------------------------------------------


def wilcoxon_test(a: list[float], b: list[float]) -> tuple[float, float]:
    """Wilcoxon signed-rank test: a vs b (paired).

    Returns (statistic, p_value).
    Requires scipy.

    Raises ImportError if scipy is not installed.
    Raises ValueError if a and b have different lengths or fewer than 2 elements.
    """
    try:
        from scipy.stats import wilcoxon  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError(
            "wilcoxon_test requires scipy. "
            "Install with: uv pip install 'council-agent[benchmark]'"
        ) from e

    if len(a) != len(b):
        raise ValueError(f"wilcoxon_test: a and b must have the same length ({len(a)} vs {len(b)})")
    if len(a) < 2:
        raise ValueError("wilcoxon_test: need at least 2 observations")

    # When all differences are zero (identical series), scipy raises RuntimeWarning
    # due to division by zero in the rank normalization. Handle this degenerate
    # case directly: no difference → statistic=0, p-value=1.0.
    if all(x == y for x, y in zip(a, b)):
        return 0.0, 1.0

    result = wilcoxon(a, b)
    return float(result.statistic), float(result.pvalue)


# ---------------------------------------------------------------------------
# AIPW estimator
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AIPWResult:
    """Output of AIPWEstimator.estimate().

    ate:       Average Treatment Effect estimate.
    se:        Standard error of the ATE.
    ci_lower:  Lower bound of 95% confidence interval.
    ci_upper:  Upper bound of 95% confidence interval.
    """

    ate: float
    se: float
    ci_lower: float
    ci_upper: float


class AIPWEstimator:
    """Augmented Inverse Propensity Weighting (AIPW) estimator.

    Models council configurations as "treatments" and task accuracy as the
    outcome. The propensity score is the probability of assigning a given
    configuration to a given task (uniform in a random sweep; non-uniform
    if configs are pre-filtered by task profile).

    Requires scikit-learn for propensity model fitting.

    Usage:
        est = AIPWEstimator()
        est.fit(configs, outcomes, propensities)
        result = est.estimate(treatment, outcomes, propensities)
    """

    def __init__(self) -> None:
        self._outcome_model: object = None
        self._fitted = False

    def fit(
        self,
        configs: list[dict[str, object]],
        outcomes: list[float],
        propensities: list[float],
    ) -> None:
        """Fit the outcome model on (config, outcome, propensity) triples.

        configs:      List of config dicts (one per observation). Numeric values
                      are used; string values are one-hot encoded.
        outcomes:     Observed accuracy scores in [0, 1].
        propensities: P(treatment | covariates), same length as outcomes.

        Requires scikit-learn.
        """
        try:
            from sklearn.linear_model import Ridge  # type: ignore[import-untyped]
            from sklearn.preprocessing import OneHotEncoder  # type: ignore[import-untyped]
            import numpy as np  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "AIPWEstimator.fit requires scikit-learn and numpy. "
                "Install with: uv pip install 'council-agent[benchmark]'"
            ) from e

        if len(configs) != len(outcomes):
            raise ValueError("configs and outcomes must have the same length")

        X = self._featurize(configs)
        y = np.array(outcomes)
        w = np.array(propensities)

        model = Ridge(alpha=1.0)
        model.fit(X, y, sample_weight=w)
        self._outcome_model = model
        self._fitted = True

    def estimate(
        self,
        treatment: list[int],
        outcomes: list[float],
        propensities: list[float],
    ) -> AIPWResult:
        """Compute the AIPW ATE estimate.

        treatment:    Binary treatment indicator (1 = council, 0 = baseline).
        outcomes:     Observed accuracy scores.
        propensities: P(treatment=1 | covariates).

        Returns AIPWResult with ATE and 95% CI.
        """
        if not (len(treatment) == len(outcomes) == len(propensities)):
            raise ValueError("treatment, outcomes, and propensities must have equal length")

        try:
            import numpy as np  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "AIPWEstimator.estimate requires numpy. "
                "Install with: uv pip install 'council-agent[benchmark]'"
            ) from e

        t = np.array(treatment, dtype=float)
        y = np.array(outcomes)
        e = np.clip(np.array(propensities), 1e-6, 1 - 1e-6)

        # If outcome model is fitted, use it for augmentation (AIPW).
        # Otherwise fall back to Horvitz-Thompson IPW.
        if self._fitted and self._outcome_model is not None:
            # Augmented IPW: use fitted model predictions as outcome mean mu.
            configs_dummy = [{"intercept": 1.0}] * len(treatment)
            X = self._featurize(configs_dummy)
            mu = self._outcome_model.predict(X)  # type: ignore[union-attr]
            scores = t * (y - mu) / e + mu - (1 - t) * (y - mu) / (1 - e)
        else:
            # Horvitz-Thompson IPW (no augmentation)
            scores = t * y / e - (1 - t) * y / (1 - e)

        ate = float(np.mean(scores))
        se = float(np.std(scores, ddof=1) / np.sqrt(len(scores)))
        z = 1.96
        return AIPWResult(ate=ate, se=se, ci_lower=ate - z * se, ci_upper=ate + z * se)

    @staticmethod
    def _featurize(configs: list[dict[str, object]]) -> object:
        """Convert list of config dicts to a numeric feature matrix."""
        try:
            import numpy as np  # type: ignore[import-untyped]
        except ImportError:
            return []

        rows = []
        for cfg in configs:
            row = [float(v) if isinstance(v, (int, float)) else 0.0 for v in cfg.values()]
            rows.append(row or [0.0])
        max_len = max(len(r) for r in rows) if rows else 1
        padded = [r + [0.0] * (max_len - len(r)) for r in rows]
        return np.array(padded)


# ---------------------------------------------------------------------------
# MixedEffectsModel
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ObservationRow:
    """Single observation for mixed-effects modelling.

    accuracy:    Task accuracy score in [0, 1].
    config_hash: Identifier for the council config (treatment).
    domain:      Task domain (random intercept in the model).
    difficulty:  Optional coarse difficulty label.
    """

    accuracy: float
    config_hash: str
    domain: str
    difficulty: str | None = None


@dataclass
class MixedEffectsResult:
    """Output of MixedEffectsModel.fit()."""

    fixed_effects: dict[str, float] = field(default_factory=dict)
    random_effects: dict[str, float] = field(default_factory=dict)
    aic: float = 0.0
    bic: float = 0.0
    log_likelihood: float = 0.0


class MixedEffectsModel:
    """Linear mixed-effects model with domain random intercepts.

    Formula: accuracy ~ config_hash + (1 | domain)

    Used in Phase 5 hypothesis testing to account for domain-level variance
    when comparing council configurations.

    Requires statsmodels and pandas.
    """

    def fit(self, data: list[ObservationRow]) -> MixedEffectsResult:
        """Fit the mixed-effects model.

        Raises ImportError if statsmodels or pandas are not installed.
        Raises ValueError if data is empty or has fewer than 2 distinct domains.
        """
        try:
            import numpy as np  # type: ignore[import-untyped]
            import pandas as pd  # type: ignore[import-untyped]
            import statsmodels.formula.api as smf  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "MixedEffectsModel requires statsmodels and pandas. "
                "Install with: uv pip install 'council-agent[benchmark]'"
            ) from e

        if not data:
            raise ValueError("MixedEffectsModel.fit: data must be non-empty")

        df = pd.DataFrame([
            {
                "accuracy": row.accuracy,
                "config_hash": row.config_hash,
                "domain": row.domain,
            }
            for row in data
        ])

        if df["domain"].nunique() < 2:
            raise ValueError("MixedEffectsModel requires at least 2 distinct domains")

        model = smf.mixedlm("accuracy ~ C(config_hash)", df, groups=df["domain"])
        result = model.fit(method="lbfgs", disp=False)

        fixed = {k: float(v) for k, v in result.fe_params.items()}
        random = {k: float(v.values[0]) for k, v in result.random_effects.items()}
        return MixedEffectsResult(
            fixed_effects=fixed,
            random_effects=random,
            aic=float(result.aic),
            bic=float(result.bic),
            log_likelihood=float(result.llf),
        )
