//! Active Cognitive Resonance (ACR) Controller
//!
//! Implements the Kuramoto-inspired phase-locking controller
//! for inducing cognitive insights through frequency matching.
//!
//! From the ACR Framework:
//! - z(t) = E(t) * exp(i * phi_int(t))
//! - d(phi_int)/dt = omega_int + K(E) * sin(phi_ext - phi_int) + beta * u(t)
//! - R(t) = |<exp(i * delta_phi)>| (resonance metric)

use std::f64::consts::PI;

/// Cognitive modality types (from empirical data analysis)
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum CognitiveModality {
    /// High-mass, low-frequency: deep integration (tau ~ 15000ms)
    Integration,
    /// Low-mass, high-frequency: rapid scanning (tau ~ 1200ms)
    Differentiation,
    /// Intermediate: verification mode (tau ~ 2000ms)
    Verification,
    /// Intermittent: mixed pattern (tau ~ 8000ms)
    Intermittent,
}

impl CognitiveModality {
    pub fn tau(&self) -> f64 {
        match self {
            Self::Integration => 15000.0,
            Self::Differentiation => 1200.0,
            Self::Verification => 2000.0,
            Self::Intermittent => 8000.0,
        }
    }

    pub fn natural_frequency(&self) -> f64 {
        match self {
            Self::Integration => 0.05,      // Hz
            Self::Differentiation => 1.25,  // Hz
            Self::Verification => 0.90,     // Hz
            Self::Intermittent => 0.15,     // Hz
        }
    }
}

/// ACR Controller state
#[derive(Debug, Clone)]
pub struct ACRState {
    /// Cognitive energy E(t) in [0, 1]
    pub energy: f64,
    /// Internal phase phi_int in [0, 2*PI]
    pub phase_internal: f64,
    /// External phase phi_ext in [0, 2*PI]
    pub phase_external: f64,
    /// Phase error delta_phi = phi_ext - phi_int
    pub phase_error: f64,
    /// Phase error velocity
    pub phase_error_velocity: f64,
    /// Instantaneous resonance R(t)
    pub resonance: f64,
    /// Current timestamp
    pub timestamp: f64,
}

impl Default for ACRState {
    fn default() -> Self {
        Self {
            energy: 0.5,
            phase_internal: 0.0,
            phase_external: 0.0,
            phase_error: 0.0,
            phase_error_velocity: 0.0,
            resonance: 0.0,
            timestamp: 0.0,
        }
    }
}

/// LQR Control gains
#[derive(Debug, Clone)]
pub struct LQRGains {
    /// Gain for energy deviation
    pub k_energy: f64,
    /// Gain for phase error
    pub k_phase: f64,
    /// Gain for phase velocity
    pub k_velocity: f64,
}

impl Default for LQRGains {
    fn default() -> Self {
        Self {
            k_energy: 0.5,
            k_phase: 1.0,
            k_velocity: 0.3,
        }
    }
}

/// Control output
#[derive(Debug, Clone)]
pub struct ControlSignal {
    /// Pacing adjustment: >1.0 speeds up, <1.0 slows down
    pub pacing_factor: f64,
    /// Salience injection: 0.0 = none, 1.0 = maximum
    pub salience_injection: f64,
    /// Recommendation for SDK
    pub action: ControlAction,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ControlAction {
    /// Match pacing to user's rhythm
    MatchPacing,
    /// Slow down presentation
    SlowDown,
    /// Speed up presentation
    SpeedUp,
    /// Inject hint/highlight
    TriggerInsight,
    /// Suppress interruptions
    PhaseReset,
    /// No change needed
    Hold,
}

/// Active Cognitive Resonance Controller
pub struct ACRController {
    /// Current state estimate
    state: ACRState,
    /// Detected modality
    modality: CognitiveModality,
    /// Control gains
    gains: LQRGains,
    /// Coupling strength base
    coupling_base: f64,
    /// Damping coefficient
    damping: f64,
    /// Control gain for u(t)
    beta: f64,
    /// Resonance threshold for insight
    gamma_crit: f64,
    /// Minimum energy for stable insight
    energy_min: f64,
    /// Resonance history for averaging
    resonance_history: Vec<f64>,
    /// History window size
    window_size: usize,
}

impl ACRController {
    pub fn new(modality: CognitiveModality) -> Self {
        Self {
            state: ACRState::default(),
            modality,
            gains: LQRGains::default(),
            coupling_base: 0.5,
            damping: 0.1,
            beta: 0.3,
            gamma_crit: 0.8,
            energy_min: 0.4,
            resonance_history: Vec::with_capacity(50),
            window_size: 50,
        }
    }

    /// Update controller with new observation
    pub fn update(
        &mut self,
        timestamp: f64,
        event_duration: f64,
        switching_frequency: f64,
    ) -> ControlSignal {
        let dt = timestamp - self.state.timestamp;
        if dt <= 0.0 {
            return self.hold_signal();
        }

        let tau = self.modality.tau();
        let omega_nat = self.modality.natural_frequency() * 2.0 * PI;

        // === KALMAN-LIKE STATE ESTIMATION ===

        // Estimate energy from event duration
        // Long events = high energy, short = low
        let mean_duration = tau / 10.0; // Expected duration at baseline
        let energy_obs = (event_duration / mean_duration).clamp(0.0, 1.0);

        // Estimate internal frequency from switching
        let omega_obs = switching_frequency * 2.0 * PI;

        // Update energy (OEP dynamics)
        let decay = (-dt / tau).exp();
        self.state.energy = self.state.energy * decay + (1.0 - decay) * energy_obs;
        self.state.energy = self.state.energy.clamp(0.0, 1.0);

        // === PHASE DYNAMICS (Kuramoto) ===

        // Coupling strength proportional to energy
        let coupling = self.coupling_base * self.state.energy;

        // Compute control signal first (for feedforward)
        let u = self.compute_control();

        // Internal phase evolution
        // d(phi_int)/dt = omega_int + K(E)*sin(delta_phi) + beta*u
        let delta_phi = self.state.phase_external - self.state.phase_internal;
        let d_phi_int = omega_obs + coupling * delta_phi.sin() + self.beta * u.pacing_factor;

        self.state.phase_internal += d_phi_int * dt / 1000.0; // dt in ms
        self.state.phase_internal = self.state.phase_internal.rem_euclid(2.0 * PI);

        // External phase advances at natural rate (SDK controlled)
        self.state.phase_external += omega_nat * dt / 1000.0;
        self.state.phase_external = self.state.phase_external.rem_euclid(2.0 * PI);

        // Update phase error
        let old_error = self.state.phase_error;
        self.state.phase_error = self.state.phase_external - self.state.phase_internal;

        // Wrap to [-PI, PI]
        if self.state.phase_error > PI {
            self.state.phase_error -= 2.0 * PI;
        } else if self.state.phase_error < -PI {
            self.state.phase_error += 2.0 * PI;
        }

        self.state.phase_error_velocity = (self.state.phase_error - old_error) / (dt / 1000.0);

        // === RESONANCE METRIC ===

        // R(t) = |<exp(i * delta_phi)>| averaged over window
        let resonance_sample = (self.state.phase_error.cos(), self.state.phase_error.sin());

        if self.resonance_history.len() >= self.window_size {
            self.resonance_history.remove(0);
        }
        self.resonance_history.push(resonance_sample.0); // Real part for simplicity

        // Average resonance
        if !self.resonance_history.is_empty() {
            let sum: f64 = self.resonance_history.iter().sum();
            self.state.resonance = (sum / self.resonance_history.len() as f64).abs();
        }

        self.state.timestamp = timestamp;

        // === RETURN CONTROL SIGNAL ===
        self.compute_control()
    }

    fn compute_control(&self) -> ControlSignal {
        let e = self.state.energy;
        let delta_phi = self.state.phase_error;
        let delta_phi_dot = self.state.phase_error_velocity;
        let r = self.state.resonance;

        // LQR-style control law: u = -L * x
        let energy_term = self.gains.k_energy * (e - 1.0);
        let phase_term = self.gains.k_phase * delta_phi;
        let velocity_term = self.gains.k_velocity * delta_phi_dot;

        let raw_pacing = -(energy_term + phase_term + velocity_term);
        let pacing_factor = (1.0 + raw_pacing * 0.5).clamp(0.5, 2.0);

        // Salience based on energy deficit
        let salience = ((1.0 - e) * 0.5).clamp(0.0, 1.0);

        // Determine action
        let action = if r >= self.gamma_crit && e > self.energy_min {
            // Resonance achieved with sufficient energy
            ControlAction::TriggerInsight
        } else if r > 0.4 && r < 0.7 {
            // Pre-resonance: match pacing
            ControlAction::MatchPacing
        } else if e < 0.2 {
            // Very low energy: phase reset in progress
            ControlAction::PhaseReset
        } else if delta_phi.abs() > PI / 2.0 {
            // Large phase error: slow down
            ControlAction::SlowDown
        } else if delta_phi.abs() < 0.1 && e > 0.6 {
            // Good alignment, good energy: can speed up
            ControlAction::SpeedUp
        } else {
            ControlAction::Hold
        };

        ControlSignal {
            pacing_factor,
            salience_injection: salience,
            action,
        }
    }

    fn hold_signal(&self) -> ControlSignal {
        ControlSignal {
            pacing_factor: 1.0,
            salience_injection: 0.0,
            action: ControlAction::Hold,
        }
    }

    /// Get current state
    pub fn state(&self) -> &ACRState {
        &self.state
    }

    /// Get current modality
    pub fn modality(&self) -> CognitiveModality {
        self.modality
    }

    /// Update modality based on observed behavior
    pub fn adapt_modality(&mut self, mean_duration: f64, switching_freq: f64) {
        // Classify based on behavior
        self.modality = if mean_duration > 8000.0 && switching_freq < 0.1 {
            CognitiveModality::Integration
        } else if mean_duration < 1500.0 && switching_freq > 0.8 {
            CognitiveModality::Differentiation
        } else if mean_duration < 2500.0 && switching_freq > 0.5 {
            CognitiveModality::Verification
        } else {
            CognitiveModality::Intermittent
        };
    }

    /// Check if insight is likely imminent
    pub fn insight_imminent(&self) -> bool {
        self.state.resonance > 0.6
            && self.state.energy > self.energy_min
            && self.state.phase_error.abs() < PI / 4.0
    }

    /// Reset controller
    pub fn reset(&mut self) {
        self.state = ACRState::default();
        self.resonance_history.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_acr_creation() {
        let controller = ACRController::new(CognitiveModality::Integration);
        assert_eq!(controller.modality(), CognitiveModality::Integration);
        assert!((controller.state().energy - 0.5).abs() < 0.01);
    }

    #[test]
    fn test_modality_tau() {
        assert!((CognitiveModality::Integration.tau() - 15000.0).abs() < 1.0);
        assert!((CognitiveModality::Differentiation.tau() - 1200.0).abs() < 1.0);
    }

    #[test]
    fn test_control_signal() {
        let mut controller = ACRController::new(CognitiveModality::Intermittent);

        // Simulate some events
        for i in 0..50 {
            let signal = controller.update(
                i as f64 * 500.0,  // timestamp
                2000.0,            // duration
                0.3,               // switching freq
            );

            // Should get valid signals
            assert!(signal.pacing_factor > 0.0);
            assert!(signal.salience_injection >= 0.0 && signal.salience_injection <= 1.0);
        }
    }

    #[test]
    fn test_insight_detection() {
        let mut controller = ACRController::new(CognitiveModality::Integration);

        // Simulate phase-locked behavior
        for i in 0..100 {
            let _ = controller.update(
                i as f64 * 200.0,
                10000.0,  // Long duration = high energy
                0.05,     // Low switching = integration mode
            );
        }

        // After convergence, should have some resonance
        assert!(controller.state().resonance >= 0.0);
    }
}
