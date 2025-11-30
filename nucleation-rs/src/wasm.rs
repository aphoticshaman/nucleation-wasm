//! WebAssembly bindings for nucleation
//!
//! Provides JavaScript-friendly wrappers for:
//! - VarianceInflectionDetector (phase transition detection)
//! - CompressionDynamicsModel (conflict potential)
//! - ShepherdDynamics (unified early warning)

use wasm_bindgen::prelude::*;
use js_sys::{Array, Float64Array, Object, Reflect};

use crate::variance::{
    VarianceInflectionDetector as RustVarianceDetector,
    VarianceConfig as RustVarianceConfig,
    Phase as RustPhase,
    SmoothingKernel,
};
use crate::compression::CompressionDynamicsModel as RustCompressionModel;
use crate::shepherd::{
    ShepherdDynamics as RustShepherd,
    AlertLevel as RustAlertLevel,
};

// ============================================================================
// Phase enum for JS
// ============================================================================

#[wasm_bindgen]
#[derive(Clone, Copy)]
pub enum Phase {
    Stable = 0,
    Approaching = 1,
    Critical = 2,
    Transitioning = 3,
}

impl From<RustPhase> for Phase {
    fn from(p: RustPhase) -> Self {
        match p {
            RustPhase::Stable => Phase::Stable,
            RustPhase::Approaching => Phase::Approaching,
            RustPhase::Critical => Phase::Critical,
            RustPhase::Transitioning => Phase::Transitioning,
        }
    }
}

// ============================================================================
// Alert Level for JS
// ============================================================================

#[wasm_bindgen]
#[derive(Clone, Copy)]
pub enum AlertLevel {
    Green = 0,
    Yellow = 1,
    Orange = 2,
    Red = 3,
}

impl From<RustAlertLevel> for AlertLevel {
    fn from(a: RustAlertLevel) -> Self {
        match a {
            RustAlertLevel::Green => AlertLevel::Green,
            RustAlertLevel::Yellow => AlertLevel::Yellow,
            RustAlertLevel::Orange => AlertLevel::Orange,
            RustAlertLevel::Red => AlertLevel::Red,
        }
    }
}

// ============================================================================
// Variance Inflection Detector
// ============================================================================

/// Configuration for the variance inflection detector.
#[wasm_bindgen]
pub struct DetectorConfig {
    window_size: usize,
    smoothing_window: usize,
    threshold: f64,
    min_peak_distance: usize,
    kernel: String,
}

#[wasm_bindgen]
impl DetectorConfig {
    #[wasm_bindgen(constructor)]
    pub fn new() -> Self {
        Self {
            window_size: 40,
            smoothing_window: 15,
            threshold: 1.5,
            min_peak_distance: 20,
            kernel: "uniform".to_string(),
        }
    }

    #[wasm_bindgen(getter)]
    pub fn window_size(&self) -> usize {
        self.window_size
    }

    #[wasm_bindgen(setter)]
    pub fn set_window_size(&mut self, v: usize) {
        self.window_size = v;
    }

    #[wasm_bindgen(getter)]
    pub fn smoothing_window(&self) -> usize {
        self.smoothing_window
    }

    #[wasm_bindgen(setter)]
    pub fn set_smoothing_window(&mut self, v: usize) {
        self.smoothing_window = v;
    }

    #[wasm_bindgen(getter)]
    pub fn threshold(&self) -> f64 {
        self.threshold
    }

    #[wasm_bindgen(setter)]
    pub fn set_threshold(&mut self, v: f64) {
        self.threshold = v;
    }

    #[wasm_bindgen(getter)]
    pub fn min_peak_distance(&self) -> usize {
        self.min_peak_distance
    }

    #[wasm_bindgen(setter)]
    pub fn set_min_peak_distance(&mut self, v: usize) {
        self.min_peak_distance = v;
    }

    #[wasm_bindgen(getter)]
    pub fn kernel(&self) -> String {
        self.kernel.clone()
    }

    #[wasm_bindgen(setter)]
    pub fn set_kernel(&mut self, v: String) {
        self.kernel = v;
    }

    /// Create a sensitive configuration.
    pub fn sensitive() -> Self {
        Self {
            window_size: 40,
            smoothing_window: 15,
            threshold: 1.0,
            min_peak_distance: 10,
            kernel: "uniform".to_string(),
        }
    }

    /// Create a conservative configuration.
    pub fn conservative() -> Self {
        Self {
            window_size: 40,
            smoothing_window: 15,
            threshold: 2.5,
            min_peak_distance: 30,
            kernel: "uniform".to_string(),
        }
    }
}

impl From<&DetectorConfig> for RustVarianceConfig {
    fn from(c: &DetectorConfig) -> Self {
        RustVarianceConfig {
            window_size: c.window_size,
            smoothing_window: c.smoothing_window,
            threshold: c.threshold,
            min_peak_distance: c.min_peak_distance,
            kernel: match c.kernel.as_str() {
                "gaussian" => SmoothingKernel::Gaussian,
                _ => SmoothingKernel::Uniform,
            },
        }
    }
}

/// Variance Inflection Detector for phase transition detection.
///
/// Detects phase transitions by finding peaks in the second derivative
/// of rolling variance.
#[wasm_bindgen]
pub struct NucleationDetector {
    inner: RustVarianceDetector,
}

#[wasm_bindgen]
impl NucleationDetector {
    /// Create a new detector with the given configuration.
    #[wasm_bindgen(constructor)]
    pub fn new(config: &DetectorConfig) -> Self {
        Self {
            inner: RustVarianceDetector::new(config.into()),
        }
    }

    /// Create a detector with default configuration.
    pub fn with_defaults() -> Self {
        Self {
            inner: RustVarianceDetector::with_default_config(),
        }
    }

    /// Process a single observation.
    pub fn update(&mut self, value: f64) -> Phase {
        let result = self.inner.update(value);
        result.phase.into()
    }

    /// Process multiple observations.
    pub fn update_batch(&mut self, values: &[f64]) -> Phase {
        let result = self.inner.update_batch(values);
        result.phase.into()
    }

    /// Get the current phase.
    #[wasm_bindgen(js_name = currentPhase)]
    pub fn current_phase(&self) -> Phase {
        self.inner.current_phase().into()
    }

    /// Get confidence in the current assessment (0-1).
    pub fn confidence(&self) -> f64 {
        self.inner.confidence()
    }

    /// Get the current rolling variance.
    #[wasm_bindgen(js_name = currentVariance)]
    pub fn current_variance(&self) -> f64 {
        self.inner.current_variance()
    }

    /// Get the current inflection magnitude (z-score).
    #[wasm_bindgen(js_name = inflectionMagnitude)]
    pub fn inflection_magnitude(&self) -> f64 {
        self.inner.inflection_magnitude()
    }

    /// Get the total number of observations processed.
    pub fn count(&self) -> usize {
        self.inner.count()
    }

    /// Reset the detector state.
    pub fn reset(&mut self) {
        self.inner.reset();
    }

    /// Serialize state to JSON string.
    #[cfg(feature = "serde")]
    pub fn serialize(&self) -> Result<String, JsValue> {
        serde_json::to_string(&self.inner)
            .map_err(|e| JsValue::from_str(&e.to_string()))
    }

    /// Deserialize state from JSON string.
    #[cfg(feature = "serde")]
    pub fn deserialize(json: &str) -> Result<NucleationDetector, JsValue> {
        let inner: RustVarianceDetector = serde_json::from_str(json)
            .map_err(|e| JsValue::from_str(&e.to_string()))?;
        Ok(Self { inner })
    }
}

// ============================================================================
// Compression Dynamics Model
// ============================================================================

/// Compression Dynamics Model for conflict potential calculation.
///
/// Tracks actor "compression schemes" (worldviews) and computes
/// KL-divergence based conflict potential.
#[wasm_bindgen]
pub struct CompressionModel {
    inner: RustCompressionModel,
}

#[wasm_bindgen]
impl CompressionModel {
    /// Create a new model with the specified number of categories.
    #[wasm_bindgen(constructor)]
    pub fn new(n_categories: usize) -> Self {
        Self {
            inner: RustCompressionModel::new(n_categories),
        }
    }

    /// Set the learning rate for scheme updates.
    #[wasm_bindgen(js_name = setLearningRate)]
    pub fn set_learning_rate(&mut self, rate: f64) {
        self.inner.learning_rate = rate;
    }

    /// Register a new actor with optional initial distribution.
    #[wasm_bindgen(js_name = registerActor)]
    pub fn register_actor(&mut self, actor_id: &str, distribution: Option<Vec<f64>>) {
        self.inner.register_actor(actor_id, distribution);
    }

    /// Update an actor's scheme with a new observation.
    #[wasm_bindgen(js_name = updateActor)]
    pub fn update_actor(&mut self, actor_id: &str, observation: &[f64], timestamp: f64) -> bool {
        self.inner.update_actor(actor_id, observation, timestamp).is_some()
    }

    /// Compute conflict potential between two actors.
    #[wasm_bindgen(js_name = conflictPotential)]
    pub fn conflict_potential(&mut self, actor_a: &str, actor_b: &str) -> Option<f64> {
        self.inner.conflict_potential(actor_a, actor_b).map(|p| p.phi)
    }

    /// Get full conflict potential details as JSON.
    #[wasm_bindgen(js_name = conflictPotentialDetails)]
    pub fn conflict_potential_details(&mut self, actor_a: &str, actor_b: &str) -> JsValue {
        if let Some(p) = self.inner.conflict_potential(actor_a, actor_b) {
            let obj = Object::new();
            let _ = Reflect::set(&obj, &"actorA".into(), &JsValue::from_str(&p.actor_a));
            let _ = Reflect::set(&obj, &"actorB".into(), &JsValue::from_str(&p.actor_b));
            let _ = Reflect::set(&obj, &"phi".into(), &JsValue::from_f64(p.phi));
            let _ = Reflect::set(&obj, &"js".into(), &JsValue::from_f64(p.js));
            let _ = Reflect::set(&obj, &"hellinger".into(), &JsValue::from_f64(p.hellinger));
            let _ = Reflect::set(&obj, &"klAB".into(), &JsValue::from_f64(p.kl_a_b));
            let _ = Reflect::set(&obj, &"klBA".into(), &JsValue::from_f64(p.kl_b_a));
            let _ = Reflect::set(&obj, &"riskCategory".into(), &JsValue::from_str(p.risk_category()));
            JsValue::from(obj)
        } else {
            JsValue::NULL
        }
    }

    /// Get list of registered actors.
    pub fn actors(&self) -> Array {
        self.inner.actors()
            .iter()
            .map(|s| JsValue::from_str(s))
            .collect()
    }

    /// Get an actor's current entropy.
    #[wasm_bindgen(js_name = actorEntropy)]
    pub fn actor_entropy(&self, actor_id: &str) -> Option<f64> {
        self.inner.get_scheme(actor_id).map(|s| s.entropy())
    }
}

// ============================================================================
// Shepherd Dynamics (Unified)
// ============================================================================

/// Shepherd Dynamics: Unified early warning system.
///
/// Combines compression dynamics with variance inflection detection
/// to identify "nucleation moments" before conflict escalation.
#[wasm_bindgen]
pub struct Shepherd {
    inner: RustShepherd,
}

#[wasm_bindgen]
impl Shepherd {
    /// Create a new Shepherd system.
    #[wasm_bindgen(constructor)]
    pub fn new(n_categories: usize) -> Self {
        Self {
            inner: RustShepherd::new(n_categories),
        }
    }

    /// Register a new actor.
    #[wasm_bindgen(js_name = registerActor)]
    pub fn register_actor(&mut self, actor_id: &str, distribution: Option<Vec<f64>>) {
        self.inner.register_actor(actor_id, distribution);
    }

    /// Update an actor and check for nucleation alerts.
    /// Returns array of alert objects.
    #[wasm_bindgen(js_name = updateActor)]
    pub fn update_actor(&mut self, actor_id: &str, observation: &[f64], timestamp: f64) -> Array {
        let alerts = self.inner.update_actor(actor_id, observation, timestamp);

        alerts.into_iter().map(|a| {
            let obj = Object::new();
            let _ = Reflect::set(&obj, &"actorA".into(), &JsValue::from_str(&a.actor_a));
            let _ = Reflect::set(&obj, &"actorB".into(), &JsValue::from_str(&a.actor_b));
            let _ = Reflect::set(&obj, &"alertLevel".into(), &JsValue::from_f64(AlertLevel::from(a.alert_level) as u32 as f64));
            let _ = Reflect::set(&obj, &"phi".into(), &JsValue::from_f64(a.phi));
            let _ = Reflect::set(&obj, &"phiTrend".into(), &JsValue::from_f64(a.phi_trend));
            let _ = Reflect::set(&obj, &"confidence".into(), &JsValue::from_f64(a.confidence));
            let _ = Reflect::set(&obj, &"timestamp".into(), &JsValue::from_f64(a.timestamp));
            let _ = Reflect::set(&obj, &"message".into(), &JsValue::from_str(&a.message));
            JsValue::from(obj)
        }).collect()
    }

    /// Check a specific dyad for nucleation.
    #[wasm_bindgen(js_name = checkDyad)]
    pub fn check_dyad(&mut self, actor_a: &str, actor_b: &str, timestamp: f64) -> JsValue {
        if let Some(a) = self.inner.check_dyad(actor_a, actor_b, timestamp) {
            let obj = Object::new();
            let _ = Reflect::set(&obj, &"actorA".into(), &JsValue::from_str(&a.actor_a));
            let _ = Reflect::set(&obj, &"actorB".into(), &JsValue::from_str(&a.actor_b));
            let _ = Reflect::set(&obj, &"alertLevel".into(), &JsValue::from_f64(AlertLevel::from(a.alert_level) as u32 as f64));
            let _ = Reflect::set(&obj, &"phi".into(), &JsValue::from_f64(a.phi));
            let _ = Reflect::set(&obj, &"phiTrend".into(), &JsValue::from_f64(a.phi_trend));
            let _ = Reflect::set(&obj, &"confidence".into(), &JsValue::from_f64(a.confidence));
            let _ = Reflect::set(&obj, &"message".into(), &JsValue::from_str(&a.message));
            JsValue::from(obj)
        } else {
            JsValue::NULL
        }
    }

    /// Check all dyads for nucleation.
    #[wasm_bindgen(js_name = checkAllDyads)]
    pub fn check_all_dyads(&mut self, timestamp: f64) -> Array {
        let alerts = self.inner.check_all_dyads(timestamp);

        alerts.into_iter().map(|a| {
            let obj = Object::new();
            let _ = Reflect::set(&obj, &"actorA".into(), &JsValue::from_str(&a.actor_a));
            let _ = Reflect::set(&obj, &"actorB".into(), &JsValue::from_str(&a.actor_b));
            let _ = Reflect::set(&obj, &"alertLevel".into(), &JsValue::from_f64(AlertLevel::from(a.alert_level) as u32 as f64));
            let _ = Reflect::set(&obj, &"phi".into(), &JsValue::from_f64(a.phi));
            let _ = Reflect::set(&obj, &"message".into(), &JsValue::from_str(&a.message));
            JsValue::from(obj)
        }).collect()
    }

    /// Get conflict potential between two actors.
    #[wasm_bindgen(js_name = conflictPotential)]
    pub fn conflict_potential(&mut self, actor_a: &str, actor_b: &str) -> Option<f64> {
        self.inner.conflict_potential(actor_a, actor_b).map(|p| p.phi)
    }

    /// Get list of registered actors.
    pub fn actors(&self) -> Array {
        self.inner.actors()
            .iter()
            .map(|s| JsValue::from_str(s))
            .collect()
    }

    /// Get phi history for a dyad as Float64Array pairs [timestamp, phi, ...].
    #[wasm_bindgen(js_name = phiHistory)]
    pub fn phi_history(&self, actor_a: &str, actor_b: &str) -> Float64Array {
        if let Some(history) = self.inner.phi_history(actor_a, actor_b) {
            let flat: Vec<f64> = history.iter()
                .flat_map(|(t, p)| vec![*t, *p])
                .collect();
            Float64Array::from(&flat[..])
        } else {
            Float64Array::new_with_length(0)
        }
    }
}

// ============================================================================
// Utility functions
// ============================================================================

/// Get the library version.
#[wasm_bindgen]
pub fn version() -> String {
    crate::VERSION.to_string()
}

/// Compute KL divergence between two distributions.
#[wasm_bindgen(js_name = klDivergence)]
pub fn kl_divergence_wasm(p: &[f64], q: &[f64]) -> f64 {
    crate::entropy::kl_divergence(p, q)
}

/// Compute Hellinger distance between two distributions.
#[wasm_bindgen(js_name = hellingerDistance)]
pub fn hellinger_distance_wasm(p: &[f64], q: &[f64]) -> f64 {
    crate::distance::hellinger_distance(p, q)
}

/// Compute Jensen-Shannon divergence between two distributions.
#[wasm_bindgen(js_name = jensenShannonDivergence)]
pub fn jensen_shannon_wasm(p: &[f64], q: &[f64]) -> f64 {
    crate::distance::jensen_shannon_divergence(p, q)
}

/// Compute Shannon entropy of a distribution.
#[wasm_bindgen(js_name = shannonEntropy)]
pub fn shannon_entropy_wasm(counts: &[u32]) -> f64 {
    crate::entropy::shannon_entropy(counts)
}
