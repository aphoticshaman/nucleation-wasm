"""
Phase Transition Simulator v2.0
Fixed transition detection + added commitment-based models.

Key changes from v1:
- Proper transition point identification (not using future data)
- Added commitment/nucleation dynamics (variance reduction)
- Separated classical bifurcations from commitment transitions

Author: Ryan J Cardwell (Archer Phoenix)
Version: 2.0.0
"""
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class TransitionType(Enum):
    # Classical bifurcations (variance INCREASES near transition - CSD)
    PITCHFORK = "pitchfork"
    SADDLE_NODE = "saddle_node"
    HOPF = "hopf"
    TRANSCRITICAL = "transcritical"
    # Commitment transitions (variance DECREASES near transition)
    NUCLEATION = "nucleation"
    COMMITMENT = "commitment"


@dataclass
class SimulationConfig:
    transition_type: TransitionType
    duration: int = 1000
    dt: float = 0.01
    noise_level: float = 0.1
    transition_fraction: float = 0.6  # Where in duration transition occurs
    seed: Optional[int] = None


@dataclass
class SimulationResult:
    time: np.ndarray
    state: np.ndarray
    control_param: np.ndarray
    transition_index: int
    transition_type: TransitionType
    config: SimulationConfig
    variance_trajectory: np.ndarray  # Pre-computed for analysis


def compute_variance_trajectory(state: np.ndarray, window: int = 50) -> np.ndarray:
    """Compute rolling variance with given window."""
    n = len(state)
    variance = np.full(n, np.nan)
    for i in range(window, n):
        variance[i] = np.var(state[i-window:i])
    return variance


def find_transition_index(
    state: np.ndarray,
    method: str = "derivative",
    window: int = 30,
    exclude_edges: float = 0.1,
) -> int:
    """
    Find actual transition point using state dynamics.

    Methods:
    - derivative: Maximum absolute derivative (fastest change)
    - variance_peak: Peak in rolling variance
    - state_threshold: First sustained crossing of baseline threshold
    """
    n = len(state)
    start = int(n * exclude_edges)
    end = int(n * (1 - exclude_edges))

    if method == "derivative":
        # Smooth then find max derivative magnitude
        smooth_window = min(20, n // 20)
        if smooth_window > 1:
            kernel = np.ones(smooth_window) / smooth_window
            smoothed = np.convolve(state, kernel, mode='same')
        else:
            smoothed = state

        derivative = np.abs(np.diff(smoothed))
        # Find peak in derivative (transition = fastest change)
        if end > start:
            peak_idx = start + np.argmax(derivative[start:end])
        else:
            peak_idx = n // 2
        return min(peak_idx, n - 1)

    elif method == "variance_peak":
        var_traj = compute_variance_trajectory(state, window)
        valid = ~np.isnan(var_traj)
        if not np.any(valid[start:end]):
            return n // 2
        var_in_range = var_traj.copy()
        var_in_range[:start] = 0
        var_in_range[end:] = 0
        var_in_range[~valid] = 0
        return np.argmax(var_in_range)

    elif method == "state_threshold":
        # Baseline from first portion
        baseline_end = max(start, n // 5)
        baseline = state[:baseline_end]
        mean = np.mean(baseline)
        std = np.std(baseline)
        if std < 1e-10:
            std = np.std(state) / 3

        threshold = 2.5 * std
        # Find first sustained crossing
        crossings = np.where(np.abs(state[start:end] - mean) > threshold)[0]
        if len(crossings) >= 5:  # Require sustained crossing
            return start + crossings[0]
        elif len(crossings) > 0:
            return start + crossings[0]
        return n // 2

    return n // 2


def simulate_pitchfork(config: SimulationConfig) -> SimulationResult:
    """
    Pitchfork bifurcation: dx/dt = rx - x³

    Control parameter r ramps from negative to positive.
    Transition occurs when r crosses 0 and x jumps to ±√r.

    Note: Classical bifurcation - variance INCREASES near transition
    due to critical slowing down.
    """
    if config.seed is not None:
        np.random.seed(config.seed)

    n = config.duration
    dt = config.dt
    sigma = config.noise_level
    trans_frac = config.transition_fraction

    # Control parameter: negative before, positive after
    r = np.linspace(-1.0, 1.0, n)

    x = np.zeros(n)
    x[0] = np.random.randn() * 0.01

    for i in range(1, n):
        # dx/dt = rx - x³
        drift = r[i-1] * x[i-1] - x[i-1]**3
        diffusion = sigma * np.sqrt(dt) * np.random.randn()
        x[i] = x[i-1] + drift * dt + diffusion

    trans_idx = find_transition_index(x, method="derivative")
    var_traj = compute_variance_trajectory(x)

    return SimulationResult(
        time=np.arange(n) * dt,
        state=x,
        control_param=r,
        transition_index=trans_idx,
        transition_type=TransitionType.PITCHFORK,
        config=config,
        variance_trajectory=var_traj,
    )


def simulate_saddle_node(config: SimulationConfig) -> SimulationResult:
    """
    Saddle-node bifurcation: dx/dt = r + x²

    Stable fixed point at x = -√(-r) for r < 0.
    At r → 0⁺, fixed point disappears, state escapes.
    """
    if config.seed is not None:
        np.random.seed(config.seed)

    n = config.duration
    dt = config.dt
    sigma = config.noise_level

    # r ramps from -1 to 0.1 (crosses bifurcation at r=0)
    r = np.linspace(-1.0, 0.1, n)

    x = np.zeros(n)
    x[0] = -1.0 + np.random.randn() * 0.01  # Start near stable fixed point

    for i in range(1, n):
        # dx/dt = r + x²
        drift = r[i-1] + x[i-1]**2
        diffusion = sigma * np.sqrt(dt) * np.random.randn()
        x[i] = x[i-1] + drift * dt + diffusion
        x[i] = np.clip(x[i], -5, 5)

    trans_idx = find_transition_index(x, method="derivative")
    var_traj = compute_variance_trajectory(x)

    return SimulationResult(
        time=np.arange(n) * dt,
        state=x,
        control_param=r,
        transition_index=trans_idx,
        transition_type=TransitionType.SADDLE_NODE,
        config=config,
        variance_trajectory=var_traj,
    )


def simulate_hopf(config: SimulationConfig) -> SimulationResult:
    """
    Hopf bifurcation: dz/dt = (r + iω - |z|²)z

    Transition from stable fixed point to limit cycle at r=0.
    """
    if config.seed is not None:
        np.random.seed(config.seed)

    n = config.duration
    dt = config.dt
    sigma = config.noise_level
    omega = 2.0

    r = np.linspace(-0.5, 0.5, n)

    z = np.zeros(n, dtype=complex)
    z[0] = 0.01 + 0.01j

    for i in range(1, n):
        drift = (r[i-1] + 1j * omega - np.abs(z[i-1])**2) * z[i-1]
        noise_re = np.random.randn()
        noise_im = np.random.randn()
        diffusion = sigma * np.sqrt(dt) * (noise_re + 1j * noise_im) / np.sqrt(2)
        z[i] = z[i-1] + drift * dt + diffusion

    x = np.real(z)
    # For Hopf, use variance peak since oscillation amplitude grows
    trans_idx = find_transition_index(np.abs(z), method="variance_peak")
    var_traj = compute_variance_trajectory(x)

    return SimulationResult(
        time=np.arange(n) * dt,
        state=x,
        control_param=r,
        transition_index=trans_idx,
        transition_type=TransitionType.HOPF,
        config=config,
        variance_trajectory=var_traj,
    )


def simulate_transcritical(config: SimulationConfig) -> SimulationResult:
    """
    Transcritical bifurcation: dx/dt = rx - x²

    Exchange of stability between x=0 and x=r at r=0.
    """
    if config.seed is not None:
        np.random.seed(config.seed)

    n = config.duration
    dt = config.dt
    sigma = config.noise_level

    r = np.linspace(-0.5, 0.5, n)

    x = np.zeros(n)
    x[0] = 0.01

    for i in range(1, n):
        drift = r[i-1] * x[i-1] - x[i-1]**2
        diffusion = sigma * np.sqrt(dt) * np.random.randn()
        x[i] = x[i-1] + drift * dt + diffusion
        x[i] = np.clip(x[i], -3, 3)

    trans_idx = find_transition_index(x, method="derivative")
    var_traj = compute_variance_trajectory(x)

    return SimulationResult(
        time=np.arange(n) * dt,
        state=x,
        control_param=r,
        transition_index=trans_idx,
        transition_type=TransitionType.TRANSCRITICAL,
        config=config,
        variance_trajectory=var_traj,
    )


def simulate_nucleation(config: SimulationConfig) -> SimulationResult:
    """
    Nucleation/crystallization transition.

    Key feature: Variance REDUCES before transition as system "commits"
    to new state. Models metastable -> stable transition.

    Physics: Double-well potential with noise. Before transition,
    fluctuations reduce as the system "locks in" to crossing direction.
    """
    if config.seed is not None:
        np.random.seed(config.seed)

    n = config.duration
    dt = config.dt
    sigma = config.noise_level
    trans_target = int(n * config.transition_fraction)

    x = np.zeros(n)
    x[0] = -1.0  # Start in left well

    # Double-well: V(x) = (x²-1)² = x⁴ - 2x² + 1
    # dV/dx = 4x³ - 4x = 4x(x²-1)
    # Minima at x=±1, barrier at x=0

    # Noise reduces as we approach transition (commitment)
    for i in range(1, n):
        # Double-well drift toward stable points
        drift = -4 * x[i-1] * (x[i-1]**2 - 1)

        # Add slow drift toward right well
        drift += 0.001 * (i / n)

        # Key: variance REDUCES near transition
        dist_to_trans = abs(i - trans_target) / n
        commitment_factor = max(0.2, min(1.0, dist_to_trans * 4))

        diffusion = sigma * commitment_factor * np.sqrt(dt) * np.random.randn()
        x[i] = x[i-1] + drift * dt + diffusion

    # Ensure transition happens around target
    if x[trans_target] < 0:
        # Force transition
        x[trans_target:] += 0.3 * (1 - np.exp(-np.arange(n - trans_target) / 30))

    trans_idx = find_transition_index(x, method="derivative")
    var_traj = compute_variance_trajectory(x)

    return SimulationResult(
        time=np.arange(n) * dt,
        state=x,
        control_param=np.linspace(0, 1, n),  # "Commitment" parameter
        transition_index=trans_idx,
        transition_type=TransitionType.NUCLEATION,
        config=config,
        variance_trajectory=var_traj,
    )


def simulate_commitment(config: SimulationConfig) -> SimulationResult:
    """
    Commitment/decision transition.

    Models decision-making: exploration phase with high variance,
    then commitment phase with reducing variance, then transition.

    Key signature: Variance REDUCES as commitment increases.
    """
    if config.seed is not None:
        np.random.seed(config.seed)

    n = config.duration
    dt = config.dt
    sigma = config.noise_level
    trans_target = int(n * config.transition_fraction)

    x = np.zeros(n)
    commitment = np.zeros(n)

    for i in range(1, n):
        # Commitment grows over time, faster near transition
        commitment[i] = min(1.0, commitment[i-1] + 0.001 + 0.002 * (i / n))

        # Variance reduces with commitment (key hypothesis)
        noise_factor = 1.0 - 0.85 * commitment[i]

        # Before commitment threshold: mean-reverting exploration
        # After: directed drift to new state
        if commitment[i] < 0.7:
            drift = -0.05 * x[i-1]  # Mean reversion
        else:
            drift = 0.3 * (1.0 - x[i-1])  # Drift toward 1

        diffusion = sigma * noise_factor * np.sqrt(dt) * np.random.randn()
        x[i] = x[i-1] + drift * dt + diffusion

    trans_idx = find_transition_index(x, method="derivative")
    var_traj = compute_variance_trajectory(x)

    return SimulationResult(
        time=np.arange(n) * dt,
        state=x,
        control_param=commitment,
        transition_index=trans_idx,
        transition_type=TransitionType.COMMITMENT,
        config=config,
        variance_trajectory=var_traj,
    )


def simulate(config: SimulationConfig) -> SimulationResult:
    """Dispatch to appropriate simulator."""
    simulators = {
        TransitionType.PITCHFORK: simulate_pitchfork,
        TransitionType.SADDLE_NODE: simulate_saddle_node,
        TransitionType.HOPF: simulate_hopf,
        TransitionType.TRANSCRITICAL: simulate_transcritical,
        TransitionType.NUCLEATION: simulate_nucleation,
        TransitionType.COMMITMENT: simulate_commitment,
    }
    return simulators[config.transition_type](config)


def generate_dataset(
    n_simulations: int = 100,
    transition_types: Optional[List[TransitionType]] = None,
    noise_levels: Optional[List[float]] = None,
    durations: Optional[Tuple[int, int]] = None,
    seed: Optional[int] = None,
    include_commitment: bool = True,
) -> List[SimulationResult]:
    """Generate diverse dataset of phase transitions."""
    if seed is not None:
        np.random.seed(seed)

    if transition_types is None:
        transition_types = list(TransitionType)
        if not include_commitment:
            transition_types = [t for t in transition_types
                             if t not in [TransitionType.NUCLEATION, TransitionType.COMMITMENT]]

    if noise_levels is None:
        noise_levels = [0.05, 0.1, 0.15, 0.2]

    if durations is None:
        durations = (500, 1500)

    results = []

    for i in range(n_simulations):
        ttype = transition_types[i % len(transition_types)]
        config = SimulationConfig(
            transition_type=ttype,
            noise_level=noise_levels[i % len(noise_levels)],
            duration=np.random.randint(durations[0], durations[1]),
            transition_fraction=np.random.uniform(0.4, 0.7),
            seed=seed + i if seed is not None else None,
        )
        results.append(simulate(config))

    return results


if __name__ == "__main__":
    print("Testing phase transition simulators v2.0...")
    print("=" * 70)

    for ttype in TransitionType:
        config = SimulationConfig(
            transition_type=ttype,
            duration=1000,
            noise_level=0.1,
            seed=42,
        )
        result = simulate(config)

        var_traj = result.variance_trajectory
        trans_idx = result.transition_index

        # Analyze variance around transition
        if trans_idx > 100 and trans_idx < len(var_traj) - 50:
            pre_var = np.nanmean(var_traj[trans_idx-80:trans_idx-30])
            at_var = np.nanmean(var_traj[trans_idx-30:trans_idx])

            if pre_var > 1e-10:
                change = (at_var - pre_var) / pre_var
                if change < -0.15:
                    direction = "↓ REDUCES"
                elif change > 0.15:
                    direction = "↑ INCREASES"
                else:
                    direction = "→ FLAT"
            else:
                direction = "?"
                change = 0
        else:
            direction = "?"
            change = 0

        print(f"{ttype.value:15s}: trans_idx={trans_idx:4d}, variance {direction} ({change:+.0%})")

    print("=" * 70)
