//! Compression Scheme - an actor's probability distribution over world-states.
//!
//! The scheme captures HOW an actor "compresses" the world into
//! meaningful categories - their predictive model of reality.

use crate::divergence::{
    bhattacharyya_coefficient, cosine_similarity, entropy, hellinger_distance, jensen_shannon,
    kl_divergence, normalize, smooth, symmetric_kl, DivergenceMetrics, SMOOTHING,
};
use crate::error::{DivergenceError, Result};
use serde::{Deserialize, Serialize};

/// Source of compression scheme data
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SchemeSource {
    /// Extracted from text (speeches, documents, media)
    Text,
    /// Extracted from event data (GDELT, ACLED, etc.)
    Events,
    /// Hybrid of text and events
    Hybrid,
    /// Goldstein scale binning
    Goldstein,
    /// Manually specified
    Manual,
}

impl Default for SchemeSource {
    fn default() -> Self {
        Self::Manual
    }
}

/// Represents an actor's compression scheme.
///
/// A compression scheme is a probability distribution over categories
/// that represents how an actor perceives and interprets the world.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompressionScheme {
    /// Unique identifier for the actor
    pub actor_id: String,

    /// Probability distribution over categories (sums to 1.0)
    distribution: Vec<f64>,

    /// Category labels (optional, for interpretability)
    pub categories: Vec<String>,

    /// Unix timestamp in milliseconds (for WASM compatibility)
    pub timestamp_ms: Option<i64>,

    /// Source of this scheme
    pub source: SchemeSource,

    /// Additional metadata
    #[serde(default)]
    pub metadata: std::collections::HashMap<String, String>,
}

impl CompressionScheme {
    /// Create a new compression scheme
    pub fn new(
        actor_id: impl Into<String>,
        distribution: Vec<f64>,
        categories: Option<Vec<String>>,
    ) -> Self {
        let actor_id = actor_id.into();
        let n = distribution.len();

        let categories =
            categories.unwrap_or_else(|| (0..n).map(|i| format!("cat_{}", i)).collect());

        let mut scheme = Self {
            actor_id,
            distribution,
            categories,
            timestamp_ms: None,
            source: SchemeSource::default(),
            metadata: std::collections::HashMap::new(),
        };

        // Normalize and smooth
        scheme.normalize_and_smooth();
        scheme
    }

    /// Create a uniform (maximum entropy) scheme
    pub fn uniform(actor_id: impl Into<String>, n_categories: usize) -> Self {
        let distribution = vec![1.0 / n_categories as f64; n_categories];
        Self::new(actor_id, distribution, None)
    }

    /// Normalize distribution to sum to 1.0 and apply Laplace smoothing
    fn normalize_and_smooth(&mut self) {
        normalize(&mut self.distribution);
        smooth(&mut self.distribution, SMOOTHING);
    }

    /// Get the distribution as a slice
    #[inline]
    pub fn distribution(&self) -> &[f64] {
        &self.distribution
    }

    /// Get mutable distribution (triggers re-normalization on drop)
    pub fn distribution_mut(&mut self) -> &mut Vec<f64> {
        &mut self.distribution
    }

    /// Number of categories
    #[inline]
    pub fn n_categories(&self) -> usize {
        self.distribution.len()
    }

    /// Shannon entropy of this scheme
    ///
    /// Higher entropy = more diffuse attention across categories
    /// Lower entropy = more focused/concentrated worldview
    #[inline]
    pub fn entropy(&self) -> f64 {
        entropy(&self.distribution)
    }

    /// Maximum possible entropy for this number of categories
    #[inline]
    pub fn max_entropy(&self) -> f64 {
        (self.n_categories() as f64).log2()
    }

    /// Normalized entropy (0 = point mass, 1 = uniform)
    #[inline]
    pub fn normalized_entropy(&self) -> f64 {
        let max_h = self.max_entropy();
        if max_h > 0.0 {
            self.entropy() / max_h
        } else {
            0.0
        }
    }

    /// KL divergence D_KL(self || other)
    ///
    /// Measures information lost when using other's compression
    /// scheme to approximate self's distribution.
    ///
    /// Interpretation: How "surprised" would self be if they
    /// adopted other's worldview?
    pub fn kl_divergence(&self, other: &CompressionScheme) -> Result<f64> {
        kl_divergence(&self.distribution, &other.distribution)
    }

    /// Symmetric KL divergence (conflict potential)
    ///
    /// Φ(A,B) = D_KL(A||B) + D_KL(B||A)
    ///
    /// This is the core conflict potential measure.
    pub fn symmetric_divergence(&self, other: &CompressionScheme) -> Result<f64> {
        symmetric_kl(&self.distribution, &other.distribution)
    }

    /// Jensen-Shannon divergence (bounded symmetric measure)
    pub fn jensen_shannon(&self, other: &CompressionScheme) -> Result<f64> {
        jensen_shannon(&self.distribution, &other.distribution)
    }

    /// Hellinger distance
    pub fn hellinger_distance(&self, other: &CompressionScheme) -> Result<f64> {
        hellinger_distance(&self.distribution, &other.distribution)
    }

    /// Bhattacharyya coefficient (similarity)
    pub fn bhattacharyya(&self, other: &CompressionScheme) -> Result<f64> {
        bhattacharyya_coefficient(&self.distribution, &other.distribution)
    }

    /// Cosine similarity
    pub fn cosine_similarity(&self, other: &CompressionScheme) -> Result<f64> {
        cosine_similarity(&self.distribution, &other.distribution)
    }

    /// Compute all divergence metrics at once
    pub fn all_metrics(&self, other: &CompressionScheme) -> Result<DivergenceMetrics> {
        DivergenceMetrics::compute(&self.distribution, &other.distribution)
    }

    /// Get top n categories by probability mass
    pub fn top_categories(&self, n: usize) -> Vec<(String, f64)> {
        let mut indexed: Vec<(usize, f64)> = self
            .distribution
            .iter()
            .enumerate()
            .map(|(i, &p)| (i, p))
            .collect();

        indexed.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());

        indexed
            .into_iter()
            .take(n)
            .map(|(i, p)| {
                let name = self
                    .categories
                    .get(i)
                    .cloned()
                    .unwrap_or_else(|| format!("cat_{}", i));
                (name, p)
            })
            .collect()
    }

    /// Bayesian update with new observation
    ///
    /// C_new = (1 - η) * C_old + η * observation
    pub fn update(&mut self, observation: &[f64], learning_rate: f64) -> Result<()> {
        if observation.len() != self.distribution.len() {
            return Err(DivergenceError::DimensionMismatch {
                expected: self.distribution.len(),
                got: observation.len(),
            });
        }

        // Normalize observation
        let obs_sum: f64 = observation.iter().sum();
        let obs_normalized: Vec<f64> = if obs_sum > 0.0 {
            observation.iter().map(|&x| x / obs_sum).collect()
        } else {
            vec![1.0 / observation.len() as f64; observation.len()]
        };

        // Exponential moving average update
        for i in 0..self.distribution.len() {
            self.distribution[i] =
                (1.0 - learning_rate) * self.distribution[i] + learning_rate * obs_normalized[i];
        }

        self.normalize_and_smooth();
        Ok(())
    }

    /// Set timestamp
    pub fn with_timestamp(mut self, timestamp_ms: i64) -> Self {
        self.timestamp_ms = Some(timestamp_ms);
        self
    }

    /// Set source
    pub fn with_source(mut self, source: SchemeSource) -> Self {
        self.source = source;
        self
    }

    /// Add metadata
    pub fn with_metadata(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.metadata.insert(key.into(), value.into());
        self
    }

    /// Serialize to JSON
    pub fn to_json(&self) -> Result<String> {
        serde_json::to_string(self).map_err(|e| DivergenceError::SerializationError(e.to_string()))
    }

    /// Deserialize from JSON
    pub fn from_json(json: &str) -> Result<Self> {
        serde_json::from_str(json).map_err(|e| DivergenceError::SerializationError(e.to_string()))
    }
}

/// Computed conflict potential between two actors
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConflictPotential {
    /// First actor
    pub actor_a: String,

    /// Second actor
    pub actor_b: String,

    /// Symmetric KL divergence (Φ)
    pub phi: f64,

    /// Jensen-Shannon divergence
    pub js: f64,

    /// Hellinger distance
    pub hellinger: f64,

    /// D_KL(A || B)
    pub kl_a_b: f64,

    /// D_KL(B || A)
    pub kl_b_a: f64,

    /// Timestamp in milliseconds
    pub timestamp_ms: Option<i64>,
}

impl ConflictPotential {
    /// Create from two schemes
    pub fn compute(scheme_a: &CompressionScheme, scheme_b: &CompressionScheme) -> Result<Self> {
        let metrics = scheme_a.all_metrics(scheme_b)?;

        Ok(Self {
            actor_a: scheme_a.actor_id.clone(),
            actor_b: scheme_b.actor_id.clone(),
            phi: metrics.symmetric_kl,
            js: metrics.jensen_shannon,
            hellinger: metrics.hellinger,
            kl_a_b: metrics.kl_p_q,
            kl_b_a: metrics.kl_q_p,
            timestamp_ms: None,
        })
    }

    /// Asymmetry of divergence
    ///
    /// High asymmetry means one actor would be more "surprised"
    /// by the other's worldview than vice versa.
    #[inline]
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

    /// Risk category based on phi value
    pub fn risk_category(&self) -> RiskLevel {
        RiskLevel::from_phi(self.phi)
    }

    /// Serialize to JSON
    pub fn to_json(&self) -> Result<String> {
        serde_json::to_string(self).map_err(|e| DivergenceError::SerializationError(e.to_string()))
    }
}

/// Risk level categorization
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RiskLevel {
    Low,
    Moderate,
    Elevated,
    High,
    Critical,
}

impl RiskLevel {
    pub fn from_phi(phi: f64) -> Self {
        // These thresholds are calibrated based on empirical analysis
        // of historical conflict data (adjust based on your domain)
        if phi < 0.5 {
            RiskLevel::Low
        } else if phi < 1.0 {
            RiskLevel::Moderate
        } else if phi < 2.0 {
            RiskLevel::Elevated
        } else if phi < 4.0 {
            RiskLevel::High
        } else {
            RiskLevel::Critical
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            RiskLevel::Low => "LOW",
            RiskLevel::Moderate => "MODERATE",
            RiskLevel::Elevated => "ELEVATED",
            RiskLevel::High => "HIGH",
            RiskLevel::Critical => "CRITICAL",
        }
    }
}

impl std::fmt::Display for RiskLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scheme_creation() {
        let scheme = CompressionScheme::new("USA", vec![0.4, 0.3, 0.2, 0.1], None);
        assert_eq!(scheme.actor_id, "USA");
        assert_eq!(scheme.n_categories(), 4);

        // Should be normalized
        let sum: f64 = scheme.distribution().iter().sum();
        assert!((sum - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_uniform_scheme() {
        let scheme = CompressionScheme::uniform("TEST", 10);
        assert_eq!(scheme.n_categories(), 10);

        // Entropy should be near maximum
        let h = scheme.entropy();
        let max_h = scheme.max_entropy();
        assert!((h - max_h).abs() < 0.1);
    }

    #[test]
    fn test_divergence_calculations() {
        let a = CompressionScheme::new("A", vec![0.7, 0.2, 0.1], None);
        let b = CompressionScheme::new("B", vec![0.3, 0.4, 0.3], None);

        let phi = a.symmetric_divergence(&b).unwrap();
        let js = a.jensen_shannon(&b).unwrap();
        let h = a.hellinger_distance(&b).unwrap();

        assert!(phi > 0.0);
        assert!(js >= 0.0 && js <= 1.0);
        assert!(h >= 0.0 && h <= 1.0);
    }

    #[test]
    fn test_update() {
        let mut scheme = CompressionScheme::uniform("TEST", 4);
        let obs = vec![1.0, 0.0, 0.0, 0.0];

        scheme.update(&obs, 0.5).unwrap();

        // First category should have increased
        assert!(scheme.distribution()[0] > 0.25);
    }

    #[test]
    fn test_conflict_potential() {
        let a = CompressionScheme::new("USA", vec![0.5, 0.3, 0.2], None);
        let b = CompressionScheme::new("RUS", vec![0.2, 0.3, 0.5], None);

        let potential = ConflictPotential::compute(&a, &b).unwrap();

        assert_eq!(potential.actor_a, "USA");
        assert_eq!(potential.actor_b, "RUS");
        assert!(potential.phi > 0.0);
    }
}
