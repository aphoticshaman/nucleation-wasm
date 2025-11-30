//! Compression Dynamics Model - the main engine.
//!
//! Tracks compression schemes over time, computes conflict potentials,
//! and predicts escalation based on divergence dynamics.
//!
//! Core equations:
//!
//! Conflict Potential:
//!     Φ(A,B) = D_KL(C_A || C_B) + D_KL(C_B || C_A)
//!
//! Escalation Probability:
//!     P(escalation) = σ(α·Φ + β·dΦ/dt + γ·G - δ·comm)

use crate::error::{DivergenceError, Result};
use crate::scheme::{CompressionScheme, ConflictPotential, RiskLevel};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Accumulated grievance (prediction error integral)
///
/// G_A(t) = ∫₀ᵗ (y - ŷ_A)² dτ
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Grievance {
    pub actor_id: String,
    pub cumulative_error: f64,
    pub window_error: f64,
    pub error_history: Vec<f64>,
    pub timestamp_ms: Option<i64>,
}

impl Grievance {
    pub fn new(actor_id: impl Into<String>) -> Self {
        Self {
            actor_id: actor_id.into(),
            cumulative_error: 0.0,
            window_error: 0.0,
            error_history: Vec::new(),
            timestamp_ms: None,
        }
    }

    /// Update with new prediction error
    pub fn update(&mut self, prediction_error: f64, window_size: usize) {
        self.cumulative_error += prediction_error;
        self.error_history.push(prediction_error);

        // Windowed error
        let start = if self.error_history.len() > window_size {
            self.error_history.len() - window_size
        } else {
            0
        };

        let window = &self.error_history[start..];
        self.window_error = window.iter().sum::<f64>() / window.len() as f64;
    }
}

/// Historical scheme entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchemeHistoryEntry {
    pub timestamp_ms: i64,
    pub actor_id: String,
    pub scheme: CompressionScheme,
}

/// Escalation prediction result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EscalationPrediction {
    pub probability: f64,
    pub current_phi: f64,
    pub current_js: f64,
    pub d_phi_dt: f64,
    pub avg_grievance: f64,
    pub communication_level: f64,
    pub risk_category: RiskLevel,
    pub actor_a: String,
    pub actor_b: String,
}

impl EscalationPrediction {
    pub fn to_json(&self) -> Result<String> {
        serde_json::to_string(self).map_err(|e| DivergenceError::SerializationError(e.to_string()))
    }
}

/// Reconciliation path analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReconciliationPath {
    pub current_phi: f64,
    pub target_phi: f64,
    pub alignment_needed: f64,
    pub diverging_categories: Vec<CategoryDivergence>,
    pub recommendation: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CategoryDivergence {
    pub category: String,
    pub prob_a: f64,
    pub prob_b: f64,
    pub divergence_contribution: f64,
}

/// Model configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelConfig {
    /// Number of categories in compression space
    pub n_categories: usize,

    /// Learning rate η for scheme updates
    pub learning_rate: f64,

    /// Divergence feedback coefficient
    pub escalation_alpha: f64,

    /// Communication dampening coefficient
    pub escalation_beta: f64,

    /// Shock/grievance sensitivity coefficient
    pub escalation_gamma: f64,

    /// Window size for grievance calculation
    pub grievance_window: usize,
}

impl Default for ModelConfig {
    fn default() -> Self {
        Self {
            n_categories: 50,
            learning_rate: 0.1,
            escalation_alpha: 0.5,
            escalation_beta: 0.3,
            escalation_gamma: 0.8,
            grievance_window: 30,
        }
    }
}

/// Main model class for compression dynamics of conflict.
///
/// Tracks compression schemes over time, computes conflict potentials,
/// and predicts escalation based on divergence dynamics.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompressionDynamicsModel {
    config: ModelConfig,
    schemes: HashMap<String, CompressionScheme>,
    history: Vec<SchemeHistoryEntry>,
    potentials: Vec<ConflictPotential>,
    grievances: HashMap<String, Grievance>,
}

impl CompressionDynamicsModel {
    /// Create a new model with default configuration
    pub fn new(n_categories: usize) -> Self {
        Self::with_config(ModelConfig {
            n_categories,
            ..Default::default()
        })
    }

    /// Create with custom configuration
    pub fn with_config(config: ModelConfig) -> Self {
        Self {
            config,
            schemes: HashMap::new(),
            history: Vec::new(),
            potentials: Vec::new(),
            grievances: HashMap::new(),
        }
    }

    /// Get model configuration
    pub fn config(&self) -> &ModelConfig {
        &self.config
    }

    /// Get all registered actor IDs
    pub fn actors(&self) -> Vec<&str> {
        self.schemes.keys().map(|s| s.as_str()).collect()
    }

    /// Get a scheme by actor ID
    pub fn get_scheme(&self, actor_id: &str) -> Option<&CompressionScheme> {
        self.schemes.get(actor_id)
    }

    /// Register a new actor with initial compression scheme
    pub fn register_actor(
        &mut self,
        actor_id: impl Into<String>,
        initial_distribution: Option<Vec<f64>>,
        categories: Option<Vec<String>>,
    ) -> &CompressionScheme {
        let actor_id = actor_id.into();

        let distribution = initial_distribution.unwrap_or_else(|| {
            vec![1.0 / self.config.n_categories as f64; self.config.n_categories]
        });

        let scheme = CompressionScheme::new(actor_id.clone(), distribution, categories);

        self.schemes.insert(actor_id.clone(), scheme);
        self.grievances.insert(actor_id.clone(), Grievance::new(&actor_id));

        self.schemes.get(&actor_id).unwrap()
    }

    /// Update an actor's compression scheme based on new observation
    pub fn update_scheme(
        &mut self,
        actor_id: &str,
        observation: &[f64],
        timestamp_ms: Option<i64>,
    ) -> Result<&CompressionScheme> {
        // Get or register actor
        if !self.schemes.contains_key(actor_id) {
            self.register_actor(actor_id, None, None);
        }

        let scheme = self.schemes.get_mut(actor_id).unwrap();
        let old_distribution = scheme.distribution().to_vec();

        // Update scheme
        scheme.update(observation, self.config.learning_rate)?;

        if let Some(ts) = timestamp_ms {
            *scheme = scheme.clone().with_timestamp(ts);
        }

        // Record history
        let ts = timestamp_ms.unwrap_or_else(|| {
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_millis() as i64)
                .unwrap_or(0)
        });

        self.history.push(SchemeHistoryEntry {
            timestamp_ms: ts,
            actor_id: actor_id.to_string(),
            scheme: scheme.clone(),
        });

        // Update grievance (prediction error)
        let prediction_error: f64 = old_distribution
            .iter()
            .zip(observation.iter())
            .map(|(&p, &o)| (o - p).powi(2))
            .sum();

        if let Some(g) = self.grievances.get_mut(actor_id) {
            g.update(prediction_error, self.config.grievance_window);
        }

        Ok(self.schemes.get(actor_id).unwrap())
    }

    /// Compute conflict potential between two actors
    pub fn compute_conflict_potential(
        &mut self,
        actor_a: &str,
        actor_b: &str,
    ) -> Result<ConflictPotential> {
        let scheme_a = self
            .schemes
            .get(actor_a)
            .ok_or_else(|| DivergenceError::UnknownActor(actor_a.to_string()))?;

        let scheme_b = self
            .schemes
            .get(actor_b)
            .ok_or_else(|| DivergenceError::UnknownActor(actor_b.to_string()))?;

        let potential = ConflictPotential::compute(scheme_a, scheme_b)?;
        self.potentials.push(potential.clone());

        Ok(potential)
    }

    /// Compute pairwise conflict potentials for all registered actors
    pub fn compute_all_potentials(&mut self) -> Vec<ConflictPotential> {
        let actors: Vec<String> = self.schemes.keys().cloned().collect();
        let mut results = Vec::new();

        for i in 0..actors.len() {
            for j in (i + 1)..actors.len() {
                if let Ok(potential) = self.compute_conflict_potential(&actors[i], &actors[j]) {
                    results.push(potential);
                }
            }
        }

        results
    }

    /// Predict escalation probability between two actors
    ///
    /// Model: P(escalation) = σ(α·Φ + β·dΦ/dt + γ·G - δ·comm)
    pub fn predict_escalation(
        &mut self,
        actor_a: &str,
        actor_b: &str,
        communication_level: f64,
        shock_intensity: f64,
    ) -> Result<EscalationPrediction> {
        // Current potential
        let current = self.compute_conflict_potential(actor_a, actor_b)?;

        // Estimate dΦ/dt from history
        let dyad_history: Vec<&ConflictPotential> = self
            .potentials
            .iter()
            .filter(|p| {
                (p.actor_a == actor_a && p.actor_b == actor_b)
                    || (p.actor_a == actor_b && p.actor_b == actor_a)
            })
            .collect();

        let d_phi = if dyad_history.len() >= 2 {
            let n = dyad_history.len();
            dyad_history[n - 1].phi - dyad_history[n - 2].phi
        } else {
            0.0
        };

        // Get grievance levels
        let g_a = self.grievances.get(actor_a);
        let g_b = self.grievances.get(actor_b);

        let avg_grievance = match (g_a, g_b) {
            (Some(a), Some(b)) => (a.window_error + b.window_error) / 2.0,
            (Some(a), None) => a.window_error,
            (None, Some(b)) => b.window_error,
            (None, None) => 0.0,
        };

        // Escalation model (logistic)
        let logit = self.config.escalation_alpha * current.phi
            + self.config.escalation_gamma * d_phi.max(0.0) // Only positive changes escalate
            + 0.5 * avg_grievance
            - self.config.escalation_beta * communication_level
            + self.config.escalation_gamma * shock_intensity;

        // Sigmoid
        let prob_escalation = 1.0 / (1.0 + (-logit).exp());

        Ok(EscalationPrediction {
            probability: prob_escalation,
            current_phi: current.phi,
            current_js: current.js,
            d_phi_dt: d_phi,
            avg_grievance,
            communication_level,
            risk_category: RiskLevel::from_probability(prob_escalation),
            actor_a: actor_a.to_string(),
            actor_b: actor_b.to_string(),
        })
    }

    /// Find path to compression alignment (reconciliation)
    ///
    /// Key insight: Reconciliation doesn't require agreeing on PAST.
    /// Only requires FUTURE compression alignment.
    pub fn find_alignment_path(
        &self,
        actor_a: &str,
        actor_b: &str,
        target_phi: f64,
    ) -> Result<ReconciliationPath> {
        let scheme_a = self
            .schemes
            .get(actor_a)
            .ok_or_else(|| DivergenceError::UnknownActor(actor_a.to_string()))?;

        let scheme_b = self
            .schemes
            .get(actor_b)
            .ok_or_else(|| DivergenceError::UnknownActor(actor_b.to_string()))?;

        let current_phi = scheme_a.symmetric_divergence(scheme_b)?;
        let dist_a = scheme_a.distribution();
        let dist_b = scheme_b.distribution();

        // Find categories with largest divergence contribution
        let mut contributions: Vec<(usize, f64)> = Vec::new();

        for i in 0..dist_a.len() {
            let ratio_a_b = (dist_a[i] / (dist_b[i] + 1e-10)).ln().abs();
            let ratio_b_a = (dist_b[i] / (dist_a[i] + 1e-10)).ln().abs();

            let contrib = dist_a[i] * ratio_a_b + dist_b[i] * ratio_b_a;
            contributions.push((i, contrib));
        }

        contributions.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());

        let diverging_categories: Vec<CategoryDivergence> = contributions
            .into_iter()
            .take(5)
            .map(|(idx, contrib)| {
                let cat_name = scheme_a
                    .categories
                    .get(idx)
                    .cloned()
                    .unwrap_or_else(|| format!("cat_{}", idx));

                CategoryDivergence {
                    category: cat_name,
                    prob_a: dist_a[idx],
                    prob_b: dist_b[idx],
                    divergence_contribution: contrib,
                }
            })
            .collect();

        let top_categories: Vec<&str> = diverging_categories
            .iter()
            .take(3)
            .map(|c| c.category.as_str())
            .collect();

        let recommendation = format!(
            "Focus dialogue on shared interpretations of: {}",
            top_categories.join(", ")
        );

        Ok(ReconciliationPath {
            current_phi,
            target_phi,
            alignment_needed: current_phi - target_phi,
            diverging_categories,
            recommendation,
        })
    }

    /// Get historical potentials for a dyad
    pub fn get_dyad_history(&self, actor_a: &str, actor_b: &str) -> Vec<&ConflictPotential> {
        self.potentials
            .iter()
            .filter(|p| {
                (p.actor_a == actor_a && p.actor_b == actor_b)
                    || (p.actor_a == actor_b && p.actor_b == actor_a)
            })
            .collect()
    }

    /// Clear all history (useful for streaming scenarios)
    pub fn clear_history(&mut self) {
        self.history.clear();
        self.potentials.clear();
        for g in self.grievances.values_mut() {
            g.error_history.clear();
            g.cumulative_error = 0.0;
            g.window_error = 0.0;
        }
    }

    /// Serialize model state to JSON
    pub fn to_json(&self) -> Result<String> {
        serde_json::to_string(self).map_err(|e| DivergenceError::SerializationError(e.to_string()))
    }

    /// Deserialize model state from JSON
    pub fn from_json(json: &str) -> Result<Self> {
        serde_json::from_str(json).map_err(|e| DivergenceError::SerializationError(e.to_string()))
    }

    /// Export current state as a summary
    pub fn summary(&self) -> ModelSummary {
        ModelSummary {
            n_actors: self.schemes.len(),
            n_history_entries: self.history.len(),
            n_potentials: self.potentials.len(),
            actors: self.actors().into_iter().map(String::from).collect(),
            config: self.config.clone(),
        }
    }
}

/// Model state summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelSummary {
    pub n_actors: usize,
    pub n_history_entries: usize,
    pub n_potentials: usize,
    pub actors: Vec<String>,
    pub config: ModelConfig,
}

impl RiskLevel {
    /// Create from probability instead of phi
    pub fn from_probability(prob: f64) -> Self {
        if prob < 0.2 {
            RiskLevel::Low
        } else if prob < 0.4 {
            RiskLevel::Moderate
        } else if prob < 0.6 {
            RiskLevel::Elevated
        } else if prob < 0.8 {
            RiskLevel::High
        } else {
            RiskLevel::Critical
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_model_basic_workflow() {
        let mut model = CompressionDynamicsModel::new(10);

        // Register actors with different worldviews
        let dist_a = vec![0.4, 0.3, 0.15, 0.1, 0.03, 0.01, 0.005, 0.003, 0.001, 0.001];
        let dist_b = vec![0.15, 0.12, 0.11, 0.10, 0.10, 0.10, 0.10, 0.08, 0.07, 0.07];
        let dist_c = vec![0.35, 0.28, 0.18, 0.12, 0.04, 0.015, 0.008, 0.004, 0.002, 0.001];

        model.register_actor("USA", Some(dist_a), None);
        model.register_actor("RUS", Some(dist_b), None);
        model.register_actor("GBR", Some(dist_c), None);

        // Compute all potentials
        let potentials = model.compute_all_potentials();
        assert_eq!(potentials.len(), 3); // 3 pairs

        // USA-RUS should have higher divergence than USA-GBR (similar worldviews)
        let usa_rus = potentials.iter().find(|p| {
            (p.actor_a == "USA" && p.actor_b == "RUS")
                || (p.actor_a == "RUS" && p.actor_b == "USA")
        });
        let usa_gbr = potentials.iter().find(|p| {
            (p.actor_a == "USA" && p.actor_b == "GBR")
                || (p.actor_a == "GBR" && p.actor_b == "USA")
        });

        assert!(usa_rus.unwrap().phi > usa_gbr.unwrap().phi);
    }

    #[test]
    fn test_escalation_prediction() {
        let mut model = CompressionDynamicsModel::new(5);

        model.register_actor("A", Some(vec![0.8, 0.1, 0.05, 0.03, 0.02]), None);
        model.register_actor("B", Some(vec![0.1, 0.1, 0.3, 0.3, 0.2]), None);

        let pred = model.predict_escalation("A", "B", 0.5, 0.0).unwrap();

        assert!(pred.probability >= 0.0 && pred.probability <= 1.0);
        assert!(pred.current_phi > 0.0);
    }

    #[test]
    fn test_alignment_path() {
        let mut model = CompressionDynamicsModel::new(5);

        model.register_actor("X", Some(vec![0.6, 0.2, 0.1, 0.05, 0.05]), None);
        model.register_actor("Y", Some(vec![0.1, 0.1, 0.3, 0.3, 0.2]), None);

        let path = model.find_alignment_path("X", "Y", 0.1).unwrap();

        assert!(path.current_phi > path.target_phi);
        assert!(!path.diverging_categories.is_empty());
        assert!(!path.recommendation.is_empty());
    }

    #[test]
    fn test_serialization() {
        let mut model = CompressionDynamicsModel::new(5);
        model.register_actor("TEST", None, None);

        let json = model.to_json().unwrap();
        let restored = CompressionDynamicsModel::from_json(&json).unwrap();

        assert_eq!(model.actors().len(), restored.actors().len());
    }
}
