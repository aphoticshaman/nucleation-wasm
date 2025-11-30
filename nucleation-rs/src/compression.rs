//! Compression Dynamics for Conflict Modeling
//!
//! Implements the KL-divergence framework for modeling conflict potential
//! between actors based on their "compression schemes" (worldviews).
//!
//! Core equation:
//!     Φ(A,B) = D_KL(C_A || C_B) + D_KL(C_B || C_A)
//!
//! Where C_A and C_B are probability distributions encoding how actors
//! compress world-states into meaningful categories.

use crate::distance::{hellinger_distance, jensen_shannon_divergence};
use crate::entropy::kl_divergence;
use std::collections::HashMap;

#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};

/// Source of compression scheme data
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub enum SchemeSource {
    Text,
    Events,
    Hybrid,
    Manual,
}

impl Default for SchemeSource {
    fn default() -> Self {
        Self::Manual
    }
}

/// An actor's compression scheme - their probability distribution over world-states.
///
/// The scheme captures HOW an actor "compresses" the world into meaningful
/// categories - their predictive model of reality.
#[derive(Debug, Clone)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct CompressionScheme {
    pub actor_id: String,
    distribution: Vec<f64>,
    pub categories: Vec<String>,
    pub timestamp: f64,
    pub source: SchemeSource,
}

impl CompressionScheme {
    /// Create a new compression scheme with automatic normalization and smoothing.
    pub fn new(
        actor_id: impl Into<String>,
        distribution: Vec<f64>,
        categories: Option<Vec<String>>,
    ) -> Self {
        let n = distribution.len();
        let cats = categories.unwrap_or_else(|| {
            (0..n).map(|i| format!("cat_{}", i)).collect()
        });

        let mut scheme = Self {
            actor_id: actor_id.into(),
            distribution,
            categories: cats,
            timestamp: 0.0,
            source: SchemeSource::default(),
        };
        scheme.normalize();
        scheme.smooth(1e-8);
        scheme
    }

    /// Create a uniform (maximum entropy) scheme.
    pub fn uniform(actor_id: impl Into<String>, n_categories: usize) -> Self {
        let dist = vec![1.0 / n_categories as f64; n_categories];
        Self::new(actor_id, dist, None)
    }

    /// Normalize distribution to sum to 1.
    fn normalize(&mut self) {
        let sum: f64 = self.distribution.iter().sum();
        if sum > 0.0 {
            for p in &mut self.distribution {
                *p /= sum;
            }
        } else {
            let n = self.distribution.len() as f64;
            for p in &mut self.distribution {
                *p = 1.0 / n;
            }
        }
    }

    /// Add Laplace smoothing to avoid log(0) in divergence calculations.
    fn smooth(&mut self, epsilon: f64) {
        for p in &mut self.distribution {
            *p += epsilon;
        }
        self.normalize();
    }

    /// Get the distribution as a slice.
    pub fn distribution(&self) -> &[f64] {
        &self.distribution
    }

    /// Number of categories.
    pub fn n_categories(&self) -> usize {
        self.distribution.len()
    }

    /// Shannon entropy of the compression scheme.
    /// Higher = more diffuse attention, Lower = more focused worldview.
    pub fn entropy(&self) -> f64 {
        let mut h = 0.0;
        for &p in &self.distribution {
            if p > 0.0 {
                h -= p * p.log2();
            }
        }
        h
    }

    /// Maximum possible entropy (uniform distribution).
    pub fn max_entropy(&self) -> f64 {
        (self.distribution.len() as f64).log2()
    }

    /// Normalized entropy in [0, 1].
    pub fn normalized_entropy(&self) -> f64 {
        let max_h = self.max_entropy();
        if max_h > 0.0 {
            self.entropy() / max_h
        } else {
            0.0
        }
    }

    /// KL divergence D_KL(self || other).
    /// Measures information lost when using other's scheme to approximate self's.
    pub fn kl_divergence(&self, other: &CompressionScheme) -> f64 {
        kl_divergence(&self.distribution, &other.distribution)
    }

    /// Symmetric divergence (conflict potential).
    /// Φ(A,B) = D_KL(A||B) + D_KL(B||A)
    pub fn symmetric_divergence(&self, other: &CompressionScheme) -> f64 {
        self.kl_divergence(other) + other.kl_divergence(self)
    }

    /// Jensen-Shannon divergence (bounded symmetric measure in [0, 1]).
    pub fn jensen_shannon(&self, other: &CompressionScheme) -> f64 {
        jensen_shannon_divergence(&self.distribution, &other.distribution)
    }

    /// Hellinger distance (satisfies triangle inequality).
    pub fn hellinger(&self, other: &CompressionScheme) -> f64 {
        hellinger_distance(&self.distribution, &other.distribution)
    }

    /// Update scheme with new observation using exponential moving average.
    /// new_scheme = (1 - learning_rate) * old + learning_rate * observation
    pub fn update(&mut self, observation: &[f64], learning_rate: f64) {
        if observation.len() != self.distribution.len() {
            return;
        }

        // Normalize observation
        let obs_sum: f64 = observation.iter().sum();
        let normalized: Vec<f64> = if obs_sum > 0.0 {
            observation.iter().map(|x| x / obs_sum).collect()
        } else {
            observation.to_vec()
        };

        // EMA update
        for (p, obs) in self.distribution.iter_mut().zip(normalized.iter()) {
            *p = (1.0 - learning_rate) * *p + learning_rate * obs;
        }

        self.normalize();
    }

    /// Get top N categories by probability mass.
    pub fn top_categories(&self, n: usize) -> Vec<(String, f64)> {
        let mut indexed: Vec<(usize, f64)> = self.distribution
            .iter()
            .enumerate()
            .map(|(i, &p)| (i, p))
            .collect();
        indexed.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        indexed.into_iter()
            .take(n)
            .map(|(i, p)| (self.categories.get(i).cloned().unwrap_or_default(), p))
            .collect()
    }
}

/// Computed conflict potential between two actors.
#[derive(Debug, Clone)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct ConflictPotential {
    pub actor_a: String,
    pub actor_b: String,
    /// Symmetric KL divergence Φ(A,B)
    pub phi: f64,
    /// Jensen-Shannon divergence (bounded)
    pub js: f64,
    /// Hellinger distance
    pub hellinger: f64,
    /// D_KL(A || B)
    pub kl_a_b: f64,
    /// D_KL(B || A)
    pub kl_b_a: f64,
    pub timestamp: f64,
}

impl ConflictPotential {
    /// Compute conflict potential between two schemes.
    pub fn compute(scheme_a: &CompressionScheme, scheme_b: &CompressionScheme) -> Self {
        let kl_a_b = scheme_a.kl_divergence(scheme_b);
        let kl_b_a = scheme_b.kl_divergence(scheme_a);

        Self {
            actor_a: scheme_a.actor_id.clone(),
            actor_b: scheme_b.actor_id.clone(),
            phi: kl_a_b + kl_b_a,
            js: scheme_a.jensen_shannon(scheme_b),
            hellinger: scheme_a.hellinger(scheme_b),
            kl_a_b,
            kl_b_a,
            timestamp: scheme_a.timestamp.max(scheme_b.timestamp),
        }
    }

    /// Asymmetry of divergence.
    /// High asymmetry = one actor more "surprised" by the other's worldview.
    pub fn asymmetry(&self) -> f64 {
        (self.kl_a_b - self.kl_b_a).abs()
    }

    /// Which actor has the more "extreme" compression scheme?
    pub fn dominant_diverger(&self) -> &str {
        if self.kl_b_a > self.kl_a_b {
            &self.actor_a
        } else {
            &self.actor_b
        }
    }

    /// Risk category based on phi.
    pub fn risk_category(&self) -> &'static str {
        if self.phi < 0.2 {
            "LOW"
        } else if self.phi < 0.5 {
            "MODERATE"
        } else if self.phi < 1.0 {
            "ELEVATED"
        } else if self.phi < 2.0 {
            "HIGH"
        } else {
            "CRITICAL"
        }
    }
}

/// Accumulated grievance = prediction error integral.
/// G_A(t) = ∫₀ᵗ (y - ŷ_A)² dτ
#[derive(Debug, Clone)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct Grievance {
    pub actor_id: String,
    pub cumulative_error: f64,
    pub window_error: f64,
    error_history: Vec<f64>,
    window_size: usize,
}

impl Grievance {
    pub fn new(actor_id: impl Into<String>, window_size: usize) -> Self {
        Self {
            actor_id: actor_id.into(),
            cumulative_error: 0.0,
            window_error: 0.0,
            error_history: Vec::with_capacity(window_size),
            window_size,
        }
    }

    /// Update grievance with new prediction error.
    pub fn update(&mut self, prediction_error: f64) {
        self.cumulative_error += prediction_error;
        self.error_history.push(prediction_error);

        // Maintain window
        if self.error_history.len() > self.window_size {
            self.error_history.remove(0);
        }

        // Compute windowed error
        if !self.error_history.is_empty() {
            self.window_error = self.error_history.iter().sum::<f64>()
                / self.error_history.len() as f64;
        }
    }

    pub fn reset(&mut self) {
        self.cumulative_error = 0.0;
        self.window_error = 0.0;
        self.error_history.clear();
    }
}

/// Main compression dynamics model.
/// Tracks actor schemes over time and computes conflict potentials.
#[derive(Debug)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct CompressionDynamicsModel {
    pub n_categories: usize,
    pub learning_rate: f64,
    schemes: HashMap<String, CompressionScheme>,
    grievances: HashMap<String, Grievance>,
    potential_history: Vec<ConflictPotential>,
    phi_history: HashMap<(String, String), Vec<(f64, f64)>>, // (timestamp, phi)
}

impl CompressionDynamicsModel {
    pub fn new(n_categories: usize) -> Self {
        Self {
            n_categories,
            learning_rate: 0.1,
            schemes: HashMap::new(),
            grievances: HashMap::new(),
            potential_history: Vec::new(),
            phi_history: HashMap::new(),
        }
    }

    pub fn with_learning_rate(mut self, rate: f64) -> Self {
        self.learning_rate = rate;
        self
    }

    /// Register a new actor with initial distribution.
    pub fn register_actor(
        &mut self,
        actor_id: impl Into<String>,
        distribution: Option<Vec<f64>>,
    ) -> &CompressionScheme {
        let id = actor_id.into();
        let dist = distribution.unwrap_or_else(|| {
            vec![1.0 / self.n_categories as f64; self.n_categories]
        });

        let scheme = CompressionScheme::new(id.clone(), dist, None);
        self.grievances.insert(id.clone(), Grievance::new(id.clone(), 30));
        self.schemes.insert(id.clone(), scheme);
        self.schemes.get(&id).unwrap()
    }

    /// Update actor's scheme with new observation.
    pub fn update_actor(
        &mut self,
        actor_id: &str,
        observation: &[f64],
        timestamp: f64,
    ) -> Option<&CompressionScheme> {
        if let Some(scheme) = self.schemes.get_mut(actor_id) {
            // Compute prediction error before update
            let error: f64 = scheme.distribution()
                .iter()
                .zip(observation.iter())
                .map(|(p, o)| (p - o).powi(2))
                .sum();

            // Update grievance
            if let Some(g) = self.grievances.get_mut(actor_id) {
                g.update(error);
            }

            // Update scheme
            scheme.update(observation, self.learning_rate);
            scheme.timestamp = timestamp;

            Some(scheme)
        } else {
            None
        }
    }

    /// Get actor's current scheme.
    pub fn get_scheme(&self, actor_id: &str) -> Option<&CompressionScheme> {
        self.schemes.get(actor_id)
    }

    /// Get actor's grievance.
    pub fn get_grievance(&self, actor_id: &str) -> Option<&Grievance> {
        self.grievances.get(actor_id)
    }

    /// Compute conflict potential between two actors.
    pub fn conflict_potential(&mut self, actor_a: &str, actor_b: &str) -> Option<ConflictPotential> {
        let scheme_a = self.schemes.get(actor_a)?;
        let scheme_b = self.schemes.get(actor_b)?;

        let potential = ConflictPotential::compute(scheme_a, scheme_b);

        // Store in history
        let key = Self::dyad_key(actor_a, actor_b);
        self.phi_history
            .entry(key)
            .or_insert_with(Vec::new)
            .push((potential.timestamp, potential.phi));

        self.potential_history.push(potential.clone());

        Some(potential)
    }

    /// Get phi history for a dyad.
    pub fn phi_history(&self, actor_a: &str, actor_b: &str) -> Option<&Vec<(f64, f64)>> {
        let key = Self::dyad_key(actor_a, actor_b);
        self.phi_history.get(&key)
    }

    /// Get all registered actor IDs.
    pub fn actors(&self) -> Vec<&str> {
        self.schemes.keys().map(|s| s.as_str()).collect()
    }

    /// Compute pairwise potentials for all actors.
    pub fn all_potentials(&mut self) -> Vec<ConflictPotential> {
        let actors: Vec<String> = self.schemes.keys().cloned().collect();
        let mut results = Vec::new();

        for i in 0..actors.len() {
            for j in (i + 1)..actors.len() {
                if let Some(p) = self.conflict_potential(&actors[i], &actors[j]) {
                    results.push(p);
                }
            }
        }

        results
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
    fn test_compression_scheme_creation() {
        let scheme = CompressionScheme::new("USA", vec![0.4, 0.3, 0.2, 0.1], None);
        assert_eq!(scheme.n_categories(), 4);
        assert!((scheme.distribution().iter().sum::<f64>() - 1.0).abs() < 1e-6);
    }

    #[test]
    fn test_symmetric_divergence() {
        let a = CompressionScheme::new("A", vec![0.7, 0.2, 0.1], None);
        let b = CompressionScheme::new("B", vec![0.1, 0.2, 0.7], None);

        let phi = a.symmetric_divergence(&b);
        assert!(phi > 0.0);

        // Symmetric
        let phi_rev = b.symmetric_divergence(&a);
        assert!((phi - phi_rev).abs() < 1e-10);
    }

    #[test]
    fn test_identical_schemes_zero_divergence() {
        let a = CompressionScheme::new("A", vec![0.5, 0.3, 0.2], None);
        let b = CompressionScheme::new("B", vec![0.5, 0.3, 0.2], None);

        let phi = a.symmetric_divergence(&b);
        assert!(phi < 0.01); // Near zero (smoothing adds tiny divergence)
    }

    #[test]
    fn test_conflict_potential() {
        let a = CompressionScheme::new("USA", vec![0.4, 0.3, 0.2, 0.1], None);
        let b = CompressionScheme::new("RUS", vec![0.1, 0.2, 0.3, 0.4], None);

        let potential = ConflictPotential::compute(&a, &b);
        assert_eq!(potential.actor_a, "USA");
        assert_eq!(potential.actor_b, "RUS");
        assert!(potential.phi > 0.0);
        assert!(potential.js >= 0.0 && potential.js <= 1.0);
    }

    #[test]
    fn test_model_basic_workflow() {
        let mut model = CompressionDynamicsModel::new(10);

        model.register_actor("USA", Some(vec![0.3, 0.2, 0.15, 0.1, 0.08, 0.07, 0.05, 0.03, 0.01, 0.01]));
        model.register_actor("RUS", Some(vec![0.1, 0.1, 0.1, 0.1, 0.15, 0.15, 0.1, 0.1, 0.05, 0.05]));

        let potential = model.conflict_potential("USA", "RUS").unwrap();
        assert!(potential.phi > 0.0);
    }

    #[test]
    fn test_scheme_update() {
        let mut scheme = CompressionScheme::new("A", vec![0.5, 0.5], None);
        scheme.update(&[0.9, 0.1], 0.5);

        // Should have moved toward observation
        assert!(scheme.distribution()[0] > 0.5);
        assert!(scheme.distribution()[1] < 0.5);
    }
}
