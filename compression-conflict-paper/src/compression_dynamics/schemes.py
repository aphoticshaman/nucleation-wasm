"""
Compression Dynamics Model
Core implementation of the KL-divergence conflict framework.

Theory: Conflict potential between actors A and B equals the symmetric
KL divergence of their "compression schemes" - their internal predictive
models mapping observations to categories.

Φ(A,B) = D_KL(C_A || C_B) + D_KL(C_B || C_A)

Author: Ryan J Cardwell (Archer Phoenix)
Version: 1.0.0
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from scipy.stats import entropy
from scipy.special import rel_entr
import pandas as pd
from enum import Enum


class SchemeSource(Enum):
    """Source of compression scheme data."""
    TEXT = "text"
    EVENTS = "events"
    HYBRID = "hybrid"


@dataclass
class CompressionScheme:
    """
    Represents an actor's compression scheme - their probability
    distribution over world-states/categories.

    The scheme captures HOW an actor "compresses" the world into
    meaningful categories - their predictive model of reality.
    """
    actor_id: str
    distribution: np.ndarray  # Shape: (n_categories,)
    categories: List[str] = field(default_factory=list)
    timestamp: Optional[pd.Timestamp] = None
    source: SchemeSource = SchemeSource.TEXT
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        # Normalize to valid probability distribution
        total = self.distribution.sum()
        if total > 0:
            self.distribution = self.distribution / total
        else:
            self.distribution = np.ones_like(self.distribution) / len(self.distribution)

        # Add smoothing to avoid log(0) in KL divergence
        self.distribution = self._smooth(self.distribution)

    @staticmethod
    def _smooth(dist: np.ndarray, epsilon: float = 1e-8) -> np.ndarray:
        """Add Laplace smoothing to avoid zero probabilities."""
        smoothed = dist + epsilon
        return smoothed / smoothed.sum()

    @property
    def entropy(self) -> float:
        """
        Shannon entropy of compression scheme.

        Higher entropy = more diffuse attention across categories
        Lower entropy = more focused/concentrated worldview
        """
        return entropy(self.distribution, base=2)

    @property
    def n_categories(self) -> int:
        return len(self.distribution)

    def kl_divergence(self, other: 'CompressionScheme') -> float:
        """
        KL divergence D_KL(self || other).

        Measures information lost when using other's compression
        scheme to approximate self's distribution.

        Interpretation: How "surprised" would self be if they
        adopted other's worldview?
        """
        if len(self.distribution) != len(other.distribution):
            raise ValueError(
                f"Scheme dimensions mismatch: {len(self.distribution)} vs {len(other.distribution)}"
            )
        return entropy(self.distribution, other.distribution, base=2)

    def symmetric_divergence(self, other: 'CompressionScheme') -> float:
        """
        Symmetric divergence (conflict potential).

        Φ(A,B) = D_KL(A||B) + D_KL(B||A)

        This is the core conflict potential measure.
        Higher Φ = more divergent worldviews = higher conflict risk.
        """
        return self.kl_divergence(other) + other.kl_divergence(self)

    def jensen_shannon(self, other: 'CompressionScheme') -> float:
        """
        Jensen-Shannon divergence (bounded symmetric measure).

        JS(A,B) = 0.5 * D_KL(A||M) + 0.5 * D_KL(B||M)
        where M = 0.5 * (A + B)

        Bounded between 0 and 1 (with log base 2).
        More numerically stable than raw KL.
        """
        m = 0.5 * (self.distribution + other.distribution)
        return 0.5 * entropy(self.distribution, m, base=2) + \
               0.5 * entropy(other.distribution, m, base=2)

    def hellinger_distance(self, other: 'CompressionScheme') -> float:
        """
        Hellinger distance - another symmetric divergence measure.

        H(A,B) = (1/√2) * ||√A - √B||₂

        Bounded between 0 and 1, satisfies triangle inequality.
        """
        sqrt_diff = np.sqrt(self.distribution) - np.sqrt(other.distribution)
        return np.sqrt(0.5 * np.sum(sqrt_diff ** 2))

    def top_categories(self, n: int = 5) -> List[Tuple[str, float]]:
        """Get top n categories by probability mass."""
        if not self.categories:
            return [(f"cat_{i}", p) for i, p in enumerate(
                sorted(enumerate(self.distribution), key=lambda x: -x[1])[:n]
            )]

        indices = np.argsort(self.distribution)[::-1][:n]
        return [(self.categories[i], self.distribution[i]) for i in indices]

    def similarity(self, other: 'CompressionScheme', method: str = 'cosine') -> float:
        """
        Compute similarity (inverse of divergence).

        Methods:
        - cosine: Cosine similarity
        - dot: Dot product
        - overlap: Bhattacharyya coefficient
        """
        if method == 'cosine':
            norm_a = np.linalg.norm(self.distribution)
            norm_b = np.linalg.norm(other.distribution)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return np.dot(self.distribution, other.distribution) / (norm_a * norm_b)

        elif method == 'dot':
            return np.dot(self.distribution, other.distribution)

        elif method == 'overlap':
            # Bhattacharyya coefficient
            return np.sum(np.sqrt(self.distribution * other.distribution))

        else:
            raise ValueError(f"Unknown similarity method: {method}")


@dataclass
class ConflictPotential:
    """Computed conflict potential between two actors."""
    actor_a: str
    actor_b: str
    phi: float              # Symmetric KL divergence
    js: float               # Jensen-Shannon divergence
    hellinger: float        # Hellinger distance
    kl_a_b: float           # D_KL(A || B)
    kl_b_a: float           # D_KL(B || A)
    timestamp: Optional[pd.Timestamp] = None

    @property
    def asymmetry(self) -> float:
        """
        Asymmetry of divergence.

        High asymmetry means one actor would be more "surprised"
        by the other's worldview than vice versa.
        """
        return abs(self.kl_a_b - self.kl_b_a)

    @property
    def dominant_diverger(self) -> str:
        """Which actor has the more "extreme" compression scheme?"""
        return self.actor_a if self.kl_b_a > self.kl_a_b else self.actor_b


@dataclass
class Grievance:
    """
    Accumulated grievance = prediction error integral.

    G_A(t) = ∫₀ᵗ (y - ŷ_A)² dτ

    Where y = actual world-state, ŷ_A = A's prediction.

    Key insight: Grievance accumulates when PREDICTIONS fail,
    not just when outcomes are bad.
    """
    actor_id: str
    cumulative_error: float
    window_error: float  # Recent window
    error_history: List[float] = field(default_factory=list)
    timestamp: Optional[pd.Timestamp] = None


class CompressionDynamicsModel:
    """
    Main model class for compression dynamics of conflict.

    Tracks compression schemes over time, computes conflict potentials,
    and predicts escalation based on divergence dynamics.

    Core equations:

    Conflict Potential:
        Φ(A,B) = D_KL(C_A || C_B) + D_KL(C_B || C_A)

    Compression Evolution:
        dC/dt = η·∇_C Q(C) + ξ(t)

    Escalation Rate:
        dΦ/dt = α·Φ - β·communication + γ·shocks
    """

    def __init__(
        self,
        n_categories: int = 50,
        learning_rate: float = 0.1,
        smoothing: float = 1e-8,
        escalation_alpha: float = 0.5,
        escalation_beta: float = 0.3,
        escalation_gamma: float = 0.8,
    ):
        """
        Initialize model.

        Args:
            n_categories: Number of categories in compression space
            learning_rate: η in dC/dt equation
            smoothing: Laplace smoothing for probabilities
            escalation_alpha: Divergence feedback coefficient
            escalation_beta: Communication dampening coefficient
            escalation_gamma: Shock sensitivity coefficient
        """
        self.n_categories = n_categories
        self.learning_rate = learning_rate
        self.smoothing = smoothing

        # Escalation dynamics parameters
        self.alpha = escalation_alpha
        self.beta = escalation_beta
        self.gamma = escalation_gamma

        # State
        self.schemes: Dict[str, CompressionScheme] = {}
        self.history: List[Tuple[pd.Timestamp, str, CompressionScheme]] = []
        self.potentials: List[ConflictPotential] = []
        self.grievances: Dict[str, Grievance] = {}

    def register_actor(
        self,
        actor_id: str,
        initial_distribution: Optional[np.ndarray] = None,
        categories: Optional[List[str]] = None,
    ) -> CompressionScheme:
        """Register a new actor with initial compression scheme."""
        if initial_distribution is None:
            # Uniform prior - no bias toward any category
            initial_distribution = np.ones(self.n_categories) / self.n_categories

        scheme = CompressionScheme(
            actor_id=actor_id,
            distribution=initial_distribution,
            categories=categories or [f"cat_{i}" for i in range(self.n_categories)],
            timestamp=pd.Timestamp.now(),
        )
        self.schemes[actor_id] = scheme
        self.grievances[actor_id] = Grievance(
            actor_id=actor_id,
            cumulative_error=0.0,
            window_error=0.0,
        )
        return scheme

    def update_scheme(
        self,
        actor_id: str,
        observation: np.ndarray,
        timestamp: Optional[pd.Timestamp] = None,
    ) -> CompressionScheme:
        """
        Update actor's compression scheme based on new observation.

        Implements belief update:
            C_new = (1 - η) * C_old + η * observation

        Args:
            actor_id: Actor to update
            observation: New observation distribution over categories
            timestamp: Time of update

        Returns:
            Updated compression scheme
        """
        if actor_id not in self.schemes:
            self.register_actor(actor_id)

        current = self.schemes[actor_id]

        # Normalize observation
        observation = observation / (observation.sum() + 1e-10)

        # Bayesian update (exponential moving average)
        new_distribution = (
            (1 - self.learning_rate) * current.distribution +
            self.learning_rate * observation
        )

        new_scheme = CompressionScheme(
            actor_id=actor_id,
            distribution=new_distribution,
            categories=current.categories,
            timestamp=timestamp or pd.Timestamp.now(),
            source=current.source,
            metadata=current.metadata,
        )

        self.schemes[actor_id] = new_scheme
        self.history.append((new_scheme.timestamp, actor_id, new_scheme))

        # Update grievance (prediction error)
        prediction = current.distribution
        prediction_error = np.sum((observation - prediction) ** 2)
        self._update_grievance(actor_id, prediction_error)

        return new_scheme

    def _update_grievance(
        self,
        actor_id: str,
        prediction_error: float,
        window_size: int = 30,
    ) -> None:
        """Update accumulated grievance for actor."""
        if actor_id not in self.grievances:
            self.grievances[actor_id] = Grievance(
                actor_id=actor_id,
                cumulative_error=0.0,
                window_error=0.0,
            )

        g = self.grievances[actor_id]
        g.cumulative_error += prediction_error
        g.error_history.append(prediction_error)

        # Windowed error
        if len(g.error_history) > window_size:
            g.window_error = np.mean(g.error_history[-window_size:])
        else:
            g.window_error = np.mean(g.error_history)

        g.timestamp = pd.Timestamp.now()

    def compute_conflict_potential(
        self,
        actor_a: str,
        actor_b: str,
    ) -> ConflictPotential:
        """
        Compute conflict potential between two actors.

        Returns ConflictPotential with multiple divergence measures.
        """
        scheme_a = self.schemes.get(actor_a)
        scheme_b = self.schemes.get(actor_b)

        if scheme_a is None:
            raise ValueError(f"Unknown actor: {actor_a}")
        if scheme_b is None:
            raise ValueError(f"Unknown actor: {actor_b}")

        potential = ConflictPotential(
            actor_a=actor_a,
            actor_b=actor_b,
            phi=scheme_a.symmetric_divergence(scheme_b),
            js=scheme_a.jensen_shannon(scheme_b),
            hellinger=scheme_a.hellinger_distance(scheme_b),
            kl_a_b=scheme_a.kl_divergence(scheme_b),
            kl_b_a=scheme_b.kl_divergence(scheme_a),
            timestamp=pd.Timestamp.now(),
        )

        self.potentials.append(potential)
        return potential

    def compute_all_potentials(self) -> pd.DataFrame:
        """Compute pairwise conflict potentials for all registered actors."""
        actors = list(self.schemes.keys())
        results = []

        for i, a in enumerate(actors):
            for b in actors[i+1:]:
                potential = self.compute_conflict_potential(a, b)
                results.append({
                    'actor_a': a,
                    'actor_b': b,
                    'phi': potential.phi,
                    'js': potential.js,
                    'hellinger': potential.hellinger,
                    'kl_a_b': potential.kl_a_b,
                    'kl_b_a': potential.kl_b_a,
                    'asymmetry': potential.asymmetry,
                })

        return pd.DataFrame(results)

    def compute_divergence_trajectory(
        self,
        actor_a: str,
        actor_b: str,
    ) -> pd.DataFrame:
        """
        Compute historical divergence trajectory between two actors.

        Uses scheme history to reconstruct Φ(t).
        """
        # Get history for both actors
        history_a = [(t, s) for t, aid, s in self.history if aid == actor_a]
        history_b = [(t, s) for t, aid, s in self.history if aid == actor_b]

        if not history_a or not history_b:
            return pd.DataFrame()

        # Align timestamps
        results = []
        for t_a, s_a in history_a:
            # Find closest scheme for actor_b
            closest_b = min(history_b, key=lambda x: abs((x[0] - t_a).total_seconds()))
            t_b, s_b = closest_b

            results.append({
                'timestamp': t_a,
                'phi': s_a.symmetric_divergence(s_b),
                'js': s_a.jensen_shannon(s_b),
            })

        return pd.DataFrame(results)

    def predict_escalation(
        self,
        actor_a: str,
        actor_b: str,
        horizon_days: int = 30,
        communication_level: float = 0.5,
        shock_intensity: float = 0.0,
    ) -> Dict:
        """
        Predict escalation probability based on divergence dynamics.

        Model: P(escalation) = σ(α·Φ + β·dΦ/dt + γ·G - δ·comm)

        Where:
            Φ = current conflict potential
            dΦ/dt = rate of divergence change
            G = grievance level
            comm = communication level

        Args:
            actor_a: First actor
            actor_b: Second actor
            horizon_days: Prediction horizon
            communication_level: 0-1, how much communication exists
            shock_intensity: External shock (news event, etc.)

        Returns:
            Dict with probability and contributing factors
        """
        # Current potential
        current = self.compute_conflict_potential(actor_a, actor_b)

        # Estimate dΦ/dt from history
        history = [p for p in self.potentials
                   if {p.actor_a, p.actor_b} == {actor_a, actor_b}]

        if len(history) >= 2:
            # Simple derivative estimate
            d_phi = history[-1].phi - history[-2].phi
        else:
            d_phi = 0

        # Get grievance levels
        g_a = self.grievances.get(actor_a)
        g_b = self.grievances.get(actor_b)
        avg_grievance = 0.0
        if g_a and g_b:
            avg_grievance = (g_a.window_error + g_b.window_error) / 2

        # Escalation model (logistic)
        # Higher Φ, higher dΦ/dt, higher grievance → more escalation
        # Higher communication → less escalation
        logit = (
            self.alpha * current.phi +
            self.gamma * max(0, d_phi) +  # Only positive changes escalate
            0.5 * avg_grievance -
            self.beta * communication_level +
            self.gamma * shock_intensity
        )

        # Sigmoid
        prob_escalation = 1 / (1 + np.exp(-logit))

        return {
            'probability': prob_escalation,
            'current_phi': current.phi,
            'current_js': current.js,
            'd_phi_dt': d_phi,
            'avg_grievance': avg_grievance,
            'communication_level': communication_level,
            'horizon_days': horizon_days,
            'risk_category': self._categorize_risk(prob_escalation),
        }

    @staticmethod
    def _categorize_risk(prob: float) -> str:
        """Categorize risk level."""
        if prob < 0.2:
            return 'LOW'
        elif prob < 0.4:
            return 'MODERATE'
        elif prob < 0.6:
            return 'ELEVATED'
        elif prob < 0.8:
            return 'HIGH'
        else:
            return 'CRITICAL'

    def find_alignment_path(
        self,
        actor_a: str,
        actor_b: str,
        target_phi: float = 0.1,
    ) -> Dict:
        """
        Find path to compression alignment (reconciliation).

        Key insight: Reconciliation doesn't require agreeing on PAST.
        Only requires FUTURE compression alignment.

        Returns recommended "moves" to reduce divergence.
        """
        current = self.compute_conflict_potential(actor_a, actor_b)
        scheme_a = self.schemes[actor_a]
        scheme_b = self.schemes[actor_b]

        # Find categories with largest divergence
        ratio_a_b = np.log(scheme_a.distribution / scheme_b.distribution + 1e-10)
        ratio_b_a = np.log(scheme_b.distribution / scheme_a.distribution + 1e-10)

        # Weighted by probability mass
        contrib_a = scheme_a.distribution * np.abs(ratio_a_b)
        contrib_b = scheme_b.distribution * np.abs(ratio_b_a)

        top_diverging = np.argsort(contrib_a + contrib_b)[::-1][:5]

        diverging_categories = []
        for idx in top_diverging:
            cat_name = scheme_a.categories[idx] if scheme_a.categories else f"cat_{idx}"
            diverging_categories.append({
                'category': cat_name,
                'prob_a': float(scheme_a.distribution[idx]),
                'prob_b': float(scheme_b.distribution[idx]),
                'divergence_contribution': float(contrib_a[idx] + contrib_b[idx]),
            })

        # Compute alignment distance
        alignment_needed = current.phi - target_phi

        return {
            'current_phi': current.phi,
            'target_phi': target_phi,
            'alignment_needed': alignment_needed,
            'diverging_categories': diverging_categories,
            'recommendation': (
                "Focus dialogue on shared interpretations of: " +
                ", ".join([d['category'] for d in diverging_categories[:3]])
            ),
        }


def compute_dyad_divergence_timeseries(
    scheme_history_a: List[Tuple[pd.Timestamp, CompressionScheme]],
    scheme_history_b: List[Tuple[pd.Timestamp, CompressionScheme]],
    resample_freq: str = 'D',
) -> pd.DataFrame:
    """
    Compute divergence time series for an actor dyad.

    Aligns timestamps and computes Φ(t) trajectory.
    """
    # Convert to DataFrames
    df_a = pd.DataFrame([
        {'timestamp': t, 'distribution': s.distribution}
        for t, s in scheme_history_a
    ])
    df_b = pd.DataFrame([
        {'timestamp': t, 'distribution': s.distribution}
        for t, s in scheme_history_b
    ])

    if df_a.empty or df_b.empty:
        return pd.DataFrame()

    # Set index
    df_a.set_index('timestamp', inplace=True)
    df_b.set_index('timestamp', inplace=True)

    # Resample to common frequency (forward fill)
    df_a = df_a.resample(resample_freq).ffill()
    df_b = df_b.resample(resample_freq).ffill()

    # Align
    common_idx = df_a.index.intersection(df_b.index)

    results = []
    for t in common_idx:
        dist_a = df_a.loc[t, 'distribution']
        dist_b = df_b.loc[t, 'distribution']

        if dist_a is None or dist_b is None:
            continue

        # Smooth
        dist_a = (dist_a + 1e-8) / (dist_a.sum() + 1e-8 * len(dist_a))
        dist_b = (dist_b + 1e-8) / (dist_b.sum() + 1e-8 * len(dist_b))

        phi = entropy(dist_a, dist_b, base=2) + entropy(dist_b, dist_a, base=2)
        m = 0.5 * (dist_a + dist_b)
        js = 0.5 * entropy(dist_a, m, base=2) + 0.5 * entropy(dist_b, m, base=2)

        results.append({
            'timestamp': t,
            'phi': phi,
            'js': js,
        })

    return pd.DataFrame(results)


if __name__ == "__main__":
    print("Testing Compression Dynamics Model...")
    print("=" * 70)

    # Create model
    model = CompressionDynamicsModel(n_categories=10)

    # Register actors with different "worldviews"
    # Actor A: Focused on first few categories (narrow worldview)
    dist_a = np.array([0.4, 0.3, 0.15, 0.1, 0.03, 0.01, 0.005, 0.003, 0.001, 0.001])
    model.register_actor("USA", dist_a)

    # Actor B: More uniform distribution (broad worldview)
    dist_b = np.array([0.15, 0.12, 0.11, 0.10, 0.10, 0.10, 0.10, 0.08, 0.07, 0.07])
    model.register_actor("RUS", dist_b)

    # Actor C: Similar to A (should have low divergence)
    dist_c = np.array([0.35, 0.28, 0.18, 0.12, 0.04, 0.015, 0.008, 0.004, 0.002, 0.001])
    model.register_actor("GBR", dist_c)

    # Compute potentials
    print("\nConflict Potentials:")
    print("-" * 70)

    potentials = model.compute_all_potentials()
    print(potentials.to_string(index=False))

    # Predict escalation
    print("\n\nEscalation Predictions:")
    print("-" * 70)

    for pair in [("USA", "RUS"), ("USA", "GBR"), ("RUS", "GBR")]:
        pred = model.predict_escalation(pair[0], pair[1])
        print(f"{pair[0]}-{pair[1]}: P(escalation)={pred['probability']:.3f} [{pred['risk_category']}]")

    # Find alignment path
    print("\n\nReconciliation Path (USA-RUS):")
    print("-" * 70)

    path = model.find_alignment_path("USA", "RUS")
    print(f"Current Φ: {path['current_phi']:.3f}")
    print(f"Target Φ: {path['target_phi']:.3f}")
    print(f"Alignment needed: {path['alignment_needed']:.3f}")
    print(f"\n{path['recommendation']}")

    print("\n" + "=" * 70)
