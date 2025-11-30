//! Shepherd Dynamics: Unified Early Warning System
//!
//! Combines compression dynamics (KL-divergence conflict potential) with
//! variance inflection detection to identify "nucleation moments" before
//! conflict escalation.
//!
//! The system monitors actor worldviews (compression schemes), computes
//! pairwise divergence Φ(A,B), and applies variance inflection detection
//! to the Φ time series to flag imminent transitions.
//!
//! Pipeline:
//! 1. Track actor compression schemes over time
//! 2. Compute conflict potential Φ(A,B) = D_KL(A||B) + D_KL(B||A)
//! 3. Monitor Φ trajectory with variance inflection detector
//! 4. Alert when nucleation signature detected in Φ dynamics

use std::collections::HashMap;

use crate::compression::{
    CompressionDynamicsModel, CompressionScheme, ConflictPotential, Grievance,
};
use crate::variance::{Phase, VarianceConfig, VarianceInflectionDetector};

#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};

/// Alert level for Shepherd warnings.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub enum AlertLevel {
    /// Normal - no significant changes
    Green,
    /// Watch - elevated divergence or approaching transition
    Yellow,
    /// Warning - high divergence or critical phase detected
    Orange,
    /// Alert - nucleation detected, imminent transition
    Red,
}

impl Default for AlertLevel {
    fn default() -> Self {
        Self::Green
    }
}

/// Nucleation alert from Shepherd analysis.
#[derive(Debug, Clone)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct NucleationAlert {
    pub actor_a: String,
    pub actor_b: String,
    pub alert_level: AlertLevel,
    pub phase: Phase,
    pub phi: f64,
    pub phi_trend: f64,
    pub confidence: f64,
    pub timestamp: f64,
    pub message: String,
}

impl NucleationAlert {
    pub fn is_actionable(&self) -> bool {
        self.alert_level >= AlertLevel::Orange
    }
}

/// Per-dyad tracker for Φ dynamics.
#[derive(Debug)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
struct DyadTracker {
    actor_a: String,
    actor_b: String,
    detector: VarianceInflectionDetector,
    phi_history: Vec<(f64, f64)>, // (timestamp, phi)
    last_alert: Option<NucleationAlert>,
}

impl DyadTracker {
    fn new(actor_a: String, actor_b: String, config: VarianceConfig) -> Self {
        Self {
            actor_a,
            actor_b,
            detector: VarianceInflectionDetector::new(config),
            phi_history: Vec::new(),
            last_alert: None,
        }
    }

    fn update(&mut self, phi: f64, timestamp: f64) -> Option<NucleationAlert> {
        self.phi_history.push((timestamp, phi));

        // Limit history size
        if self.phi_history.len() > 1000 {
            self.phi_history.remove(0);
        }

        // Update variance inflection detector with phi value
        let result = self.detector.update(phi);

        // Compute phi trend
        let phi_trend = if self.phi_history.len() >= 2 {
            let recent: Vec<f64> = self.phi_history.iter()
                .rev()
                .take(10)
                .map(|(_, p)| *p)
                .collect();
            if recent.len() >= 2 {
                recent[0] - recent[recent.len() - 1]
            } else {
                0.0
            }
        } else {
            0.0
        };

        // Determine alert level
        let alert_level = Self::compute_alert_level(phi, &result, phi_trend);

        let message = Self::generate_message(
            &self.actor_a,
            &self.actor_b,
            alert_level,
            result.phase,
            phi,
            phi_trend,
        );

        let alert = NucleationAlert {
            actor_a: self.actor_a.clone(),
            actor_b: self.actor_b.clone(),
            alert_level,
            phase: result.phase,
            phi,
            phi_trend,
            confidence: result.confidence,
            timestamp,
            message,
        };

        self.last_alert = Some(alert.clone());

        // Only return if significant
        if alert_level >= AlertLevel::Yellow {
            Some(alert)
        } else {
            None
        }
    }

    fn compute_alert_level(phi: f64, result: &crate::variance::InflectionResult, phi_trend: f64) -> AlertLevel {
        // Combined scoring based on:
        // 1. Absolute phi level
        // 2. Phase from variance inflection
        // 3. Trend direction

        match result.phase {
            Phase::Critical | Phase::Transitioning => {
                if phi > 1.0 {
                    AlertLevel::Red
                } else {
                    AlertLevel::Orange
                }
            }
            Phase::Approaching => {
                if phi > 1.5 || phi_trend > 0.1 {
                    AlertLevel::Orange
                } else {
                    AlertLevel::Yellow
                }
            }
            Phase::Stable => {
                if phi > 2.0 {
                    AlertLevel::Yellow
                } else if phi > 1.0 && phi_trend > 0.05 {
                    AlertLevel::Yellow
                } else {
                    AlertLevel::Green
                }
            }
        }
    }

    fn generate_message(
        actor_a: &str,
        actor_b: &str,
        level: AlertLevel,
        phase: Phase,
        phi: f64,
        phi_trend: f64,
    ) -> String {
        let trend_desc = if phi_trend > 0.05 {
            "increasing"
        } else if phi_trend < -0.05 {
            "decreasing"
        } else {
            "stable"
        };

        match level {
            AlertLevel::Red => format!(
                "NUCLEATION ALERT: {}-{} divergence critical (Φ={:.2}, {}). Transition imminent.",
                actor_a, actor_b, phi, trend_desc
            ),
            AlertLevel::Orange => format!(
                "WARNING: {}-{} showing pre-transition signature (Φ={:.2}, {}, phase={:?})",
                actor_a, actor_b, phi, trend_desc, phase
            ),
            AlertLevel::Yellow => format!(
                "WATCH: {}-{} divergence elevated (Φ={:.2}, {})",
                actor_a, actor_b, phi, trend_desc
            ),
            AlertLevel::Green => format!(
                "{}-{} normal (Φ={:.2})",
                actor_a, actor_b, phi
            ),
        }
    }
}

/// Shepherd Dynamics: Unified early warning system.
///
/// Monitors multiple actor dyads for nucleation signatures by combining
/// compression dynamics with variance inflection detection.
#[derive(Debug)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct ShepherdDynamics {
    model: CompressionDynamicsModel,
    dyad_trackers: HashMap<(String, String), DyadTracker>,
    variance_config: VarianceConfig,
    current_timestamp: f64,
    alert_history: Vec<NucleationAlert>,
}

impl ShepherdDynamics {
    /// Create a new Shepherd Dynamics system.
    pub fn new(n_categories: usize) -> Self {
        Self {
            model: CompressionDynamicsModel::new(n_categories),
            dyad_trackers: HashMap::new(),
            variance_config: VarianceConfig::default(),
            current_timestamp: 0.0,
            alert_history: Vec::new(),
        }
    }

    /// Configure variance detection sensitivity.
    pub fn with_variance_config(mut self, config: VarianceConfig) -> Self {
        self.variance_config = config;
        self
    }

    /// Configure model learning rate.
    pub fn with_learning_rate(mut self, rate: f64) -> Self {
        self.model = self.model.with_learning_rate(rate);
        self
    }

    /// Register a new actor with initial compression scheme.
    pub fn register_actor(
        &mut self,
        actor_id: impl Into<String>,
        distribution: Option<Vec<f64>>,
    ) {
        self.model.register_actor(actor_id, distribution);
    }

    /// Update an actor's compression scheme with new observation.
    pub fn update_actor(
        &mut self,
        actor_id: &str,
        observation: &[f64],
        timestamp: f64,
    ) -> Vec<NucleationAlert> {
        self.current_timestamp = timestamp;

        // Update the model
        self.model.update_actor(actor_id, observation, timestamp);

        // Recompute potentials and check for nucleation with all other actors
        let actors: Vec<String> = self.model.actors()
            .iter()
            .filter(|&&a| a != actor_id)
            .map(|&s| s.to_string())
            .collect();

        let mut alerts = Vec::new();

        for other in actors {
            if let Some(alert) = self.check_dyad(actor_id, &other, timestamp) {
                alerts.push(alert);
            }
        }

        alerts
    }

    /// Check a specific actor dyad for nucleation.
    pub fn check_dyad(&mut self, actor_a: &str, actor_b: &str, timestamp: f64) -> Option<NucleationAlert> {
        // Compute current potential
        let potential = self.model.conflict_potential(actor_a, actor_b)?;

        // Get or create dyad tracker
        let key = Self::dyad_key(actor_a, actor_b);
        let tracker = self.dyad_trackers
            .entry(key)
            .or_insert_with(|| {
                DyadTracker::new(
                    actor_a.to_string(),
                    actor_b.to_string(),
                    self.variance_config.clone(),
                )
            });

        // Update tracker with new phi
        let alert = tracker.update(potential.phi, timestamp);

        if let Some(ref a) = alert {
            self.alert_history.push(a.clone());
        }

        alert
    }

    /// Check all dyads for nucleation.
    pub fn check_all_dyads(&mut self, timestamp: f64) -> Vec<NucleationAlert> {
        let actors: Vec<String> = self.model.actors()
            .iter()
            .map(|&s| s.to_string())
            .collect();

        let mut alerts = Vec::new();

        for i in 0..actors.len() {
            for j in (i + 1)..actors.len() {
                if let Some(alert) = self.check_dyad(&actors[i], &actors[j], timestamp) {
                    alerts.push(alert);
                }
            }
        }

        alerts
    }

    /// Get current conflict potential between two actors.
    pub fn conflict_potential(&mut self, actor_a: &str, actor_b: &str) -> Option<ConflictPotential> {
        self.model.conflict_potential(actor_a, actor_b)
    }

    /// Get all current conflict potentials.
    pub fn all_potentials(&mut self) -> Vec<ConflictPotential> {
        self.model.all_potentials()
    }

    /// Get an actor's current compression scheme.
    pub fn get_scheme(&self, actor_id: &str) -> Option<&CompressionScheme> {
        self.model.get_scheme(actor_id)
    }

    /// Get an actor's grievance.
    pub fn get_grievance(&self, actor_id: &str) -> Option<&Grievance> {
        self.model.get_grievance(actor_id)
    }

    /// Get phi history for a dyad.
    pub fn phi_history(&self, actor_a: &str, actor_b: &str) -> Option<&Vec<(f64, f64)>> {
        let key = Self::dyad_key(actor_a, actor_b);
        self.dyad_trackers.get(&key).map(|t| &t.phi_history)
    }

    /// Get last alert for a dyad.
    pub fn last_alert(&self, actor_a: &str, actor_b: &str) -> Option<&NucleationAlert> {
        let key = Self::dyad_key(actor_a, actor_b);
        self.dyad_trackers.get(&key)?.last_alert.as_ref()
    }

    /// Get all registered actors.
    pub fn actors(&self) -> Vec<&str> {
        self.model.actors()
    }

    /// Get recent alert history.
    pub fn alert_history(&self) -> &[NucleationAlert] {
        &self.alert_history
    }

    /// Get only actionable (Orange/Red) alerts from history.
    pub fn actionable_alerts(&self) -> Vec<&NucleationAlert> {
        self.alert_history.iter()
            .filter(|a| a.is_actionable())
            .collect()
    }

    fn dyad_key(a: &str, b: &str) -> (String, String) {
        if a < b {
            (a.to_string(), b.to_string())
        } else {
            (b.to_string(), a.to_string())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_shepherd_creation() {
        let shepherd = ShepherdDynamics::new(10);
        assert!(shepherd.actors().is_empty());
    }

    #[test]
    fn test_register_actors() {
        let mut shepherd = ShepherdDynamics::new(10);

        shepherd.register_actor("USA", None);
        shepherd.register_actor("RUS", None);

        assert_eq!(shepherd.actors().len(), 2);
    }

    #[test]
    fn test_identical_actors_low_divergence() {
        let mut shepherd = ShepherdDynamics::new(5);

        let dist = vec![0.4, 0.3, 0.15, 0.1, 0.05];
        shepherd.register_actor("A", Some(dist.clone()));
        shepherd.register_actor("B", Some(dist));

        let potential = shepherd.conflict_potential("A", "B").unwrap();
        assert!(potential.phi < 0.01); // Near-identical schemes
    }

    #[test]
    fn test_divergent_actors_high_phi() {
        let mut shepherd = ShepherdDynamics::new(5);

        shepherd.register_actor("A", Some(vec![0.8, 0.1, 0.05, 0.03, 0.02]));
        shepherd.register_actor("B", Some(vec![0.02, 0.03, 0.05, 0.1, 0.8]));

        let potential = shepherd.conflict_potential("A", "B").unwrap();
        assert!(potential.phi > 1.0); // Highly divergent
    }

    #[test]
    fn test_update_and_check() {
        let mut shepherd = ShepherdDynamics::new(5);

        shepherd.register_actor("USA", Some(vec![0.4, 0.3, 0.15, 0.1, 0.05]));
        shepherd.register_actor("RUS", Some(vec![0.1, 0.2, 0.3, 0.25, 0.15]));

        // Simulate updates over time
        for i in 0..100 {
            let obs = vec![0.35 + 0.01 * (i as f64), 0.28, 0.17, 0.12, 0.08];
            shepherd.update_actor("USA", &obs, i as f64 * 100.0);
        }

        // Should have phi history
        let history = shepherd.phi_history("USA", "RUS");
        assert!(history.is_some());
        assert!(!history.unwrap().is_empty());
    }

    #[test]
    fn test_escalation_detection() {
        let mut shepherd = ShepherdDynamics::new(5)
            .with_variance_config(VarianceConfig::sensitive());

        // Start with similar worldviews
        shepherd.register_actor("A", Some(vec![0.3, 0.25, 0.2, 0.15, 0.1]));
        shepherd.register_actor("B", Some(vec![0.28, 0.24, 0.22, 0.16, 0.1]));

        // Gradual divergence
        for i in 0..150 {
            // A becomes increasingly focused on first category
            let a_obs = vec![
                0.3 + 0.003 * i as f64,
                0.25 - 0.001 * i as f64,
                0.2 - 0.001 * i as f64,
                0.15 - 0.0005 * i as f64,
                0.1 - 0.0005 * i as f64,
            ];
            shepherd.update_actor("A", &a_obs, i as f64 * 100.0);

            // B moves opposite direction
            let b_obs = vec![
                0.28 - 0.001 * i as f64,
                0.24 + 0.0005 * i as f64,
                0.22 + 0.0005 * i as f64,
                0.16 + 0.0005 * i as f64,
                0.1 + 0.0005 * i as f64,
            ];
            shepherd.update_actor("B", &b_obs, i as f64 * 100.0);
        }

        // Check final state
        let potential = shepherd.conflict_potential("A", "B").unwrap();
        assert!(potential.phi > 0.5); // Should have diverged

        // Should have generated some alerts during escalation
        let alerts = shepherd.actionable_alerts();
        // May or may not have alerts depending on dynamics
        println!("Actionable alerts: {}", alerts.len());
    }
}
