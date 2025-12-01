//! WebAssembly bindings for the divergence engine.
//!
//! Provides a JavaScript-friendly API for browser and Node.js environments.
//!
//! ## Usage (JavaScript/TypeScript)
//!
//! ```javascript
//! import init, { WasmDivergenceEngine } from 'divergence-engine';
//!
//! await init();
//!
//! const engine = new WasmDivergenceEngine(10);
//!
//! engine.registerActor('USA', [0.4, 0.3, 0.15, 0.1, 0.03, 0.01, 0.005]);
//! engine.registerActor('RUS', [0.15, 0.12, 0.11, 0.10, 0.10, 0.10, 0.32]);
//!
//! const potential = engine.computeConflictPotential('USA', 'RUS');
//! console.log(`Φ(USA, RUS) = ${potential.phi}`);
//!
//! const prediction = engine.predictEscalation('USA', 'RUS', 0.5, 0.0);
//! console.log(`P(escalation) = ${prediction.probability}`);
//! ```

use crate::model::{CompressionDynamicsModel, ModelConfig};
use crate::scheme::{CompressionScheme, ConflictPotential};
use wasm_bindgen::prelude::*;

/// Initialize the WASM module (call once at startup)
#[wasm_bindgen(start)]
pub fn wasm_init() {
    console_error_panic_hook::set_once();
}

/// WASM-compatible divergence engine
#[wasm_bindgen]
pub struct WasmDivergenceEngine {
    model: CompressionDynamicsModel,
}

#[wasm_bindgen]
impl WasmDivergenceEngine {
    /// Create a new engine with the specified number of categories
    #[wasm_bindgen(constructor)]
    pub fn new(n_categories: usize) -> Self {
        Self {
            model: CompressionDynamicsModel::new(n_categories),
        }
    }

    /// Create with custom configuration (JSON)
    #[wasm_bindgen(js_name = "withConfig")]
    pub fn with_config(config_json: &str) -> Result<WasmDivergenceEngine, JsValue> {
        let config: ModelConfig = serde_json::from_str(config_json)
            .map_err(|e| JsValue::from_str(&format!("Invalid config: {}", e)))?;

        Ok(Self {
            model: CompressionDynamicsModel::with_config(config),
        })
    }

    /// Register an actor with initial distribution
    #[wasm_bindgen(js_name = "registerActor")]
    pub fn register_actor(
        &mut self,
        actor_id: &str,
        distribution: Option<Vec<f64>>,
    ) -> Result<JsValue, JsValue> {
        let scheme = self.model.register_actor(actor_id, distribution, None);
        let json = scheme
            .to_json()
            .map_err(|e| JsValue::from_str(&e.to_string()))?;
        Ok(JsValue::from_str(&json))
    }

    /// Update an actor's scheme with new observation
    #[wasm_bindgen(js_name = "updateScheme")]
    pub fn update_scheme(
        &mut self,
        actor_id: &str,
        observation: Vec<f64>,
        timestamp_ms: Option<i64>,
    ) -> Result<JsValue, JsValue> {
        let scheme = self
            .model
            .update_scheme(actor_id, &observation, timestamp_ms)
            .map_err(|e| JsValue::from_str(&e.to_string()))?;

        let json = scheme
            .to_json()
            .map_err(|e| JsValue::from_str(&e.to_string()))?;
        Ok(JsValue::from_str(&json))
    }

    /// Compute conflict potential between two actors
    #[wasm_bindgen(js_name = "computeConflictPotential")]
    pub fn compute_conflict_potential(
        &mut self,
        actor_a: &str,
        actor_b: &str,
    ) -> Result<JsValue, JsValue> {
        let potential = self
            .model
            .compute_conflict_potential(actor_a, actor_b)
            .map_err(|e| JsValue::from_str(&e.to_string()))?;

        let json = potential
            .to_json()
            .map_err(|e| JsValue::from_str(&e.to_string()))?;
        Ok(JsValue::from_str(&json))
    }

    /// Compute all pairwise potentials
    #[wasm_bindgen(js_name = "computeAllPotentials")]
    pub fn compute_all_potentials(&mut self) -> Result<JsValue, JsValue> {
        let potentials = self.model.compute_all_potentials();
        let json = serde_json::to_string(&potentials)
            .map_err(|e| JsValue::from_str(&format!("Serialization error: {}", e)))?;
        Ok(JsValue::from_str(&json))
    }

    /// Predict escalation probability
    #[wasm_bindgen(js_name = "predictEscalation")]
    pub fn predict_escalation(
        &mut self,
        actor_a: &str,
        actor_b: &str,
        communication_level: f64,
        shock_intensity: f64,
    ) -> Result<JsValue, JsValue> {
        let prediction = self
            .model
            .predict_escalation(actor_a, actor_b, communication_level, shock_intensity)
            .map_err(|e| JsValue::from_str(&e.to_string()))?;

        let json = prediction
            .to_json()
            .map_err(|e| JsValue::from_str(&e.to_string()))?;
        Ok(JsValue::from_str(&json))
    }

    /// Find reconciliation path
    #[wasm_bindgen(js_name = "findAlignmentPath")]
    pub fn find_alignment_path(
        &self,
        actor_a: &str,
        actor_b: &str,
        target_phi: f64,
    ) -> Result<JsValue, JsValue> {
        let path = self
            .model
            .find_alignment_path(actor_a, actor_b, target_phi)
            .map_err(|e| JsValue::from_str(&e.to_string()))?;

        let json = serde_json::to_string(&path)
            .map_err(|e| JsValue::from_str(&format!("Serialization error: {}", e)))?;
        Ok(JsValue::from_str(&json))
    }

    /// Get list of registered actors
    #[wasm_bindgen(js_name = "getActors")]
    pub fn get_actors(&self) -> Vec<JsValue> {
        self.model
            .actors()
            .into_iter()
            .map(|s| JsValue::from_str(s))
            .collect()
    }

    /// Get model summary
    #[wasm_bindgen(js_name = "getSummary")]
    pub fn get_summary(&self) -> Result<JsValue, JsValue> {
        let summary = self.model.summary();
        let json = serde_json::to_string(&summary)
            .map_err(|e| JsValue::from_str(&format!("Serialization error: {}", e)))?;
        Ok(JsValue::from_str(&json))
    }

    /// Export model state as JSON
    #[wasm_bindgen(js_name = "exportState")]
    pub fn export_state(&self) -> Result<String, JsValue> {
        self.model
            .to_json()
            .map_err(|e| JsValue::from_str(&e.to_string()))
    }

    /// Import model state from JSON
    #[wasm_bindgen(js_name = "importState")]
    pub fn import_state(json: &str) -> Result<WasmDivergenceEngine, JsValue> {
        let model = CompressionDynamicsModel::from_json(json)
            .map_err(|e| JsValue::from_str(&e.to_string()))?;
        Ok(Self { model })
    }

    /// Clear all history
    #[wasm_bindgen(js_name = "clearHistory")]
    pub fn clear_history(&mut self) {
        self.model.clear_history();
    }

    /// Get engine version
    #[wasm_bindgen(js_name = "version")]
    pub fn version() -> String {
        crate::VERSION.to_string()
    }
}

/// Standalone divergence calculation (no model state needed)
#[wasm_bindgen(js_name = "computeDivergence")]
pub fn compute_divergence(p: Vec<f64>, q: Vec<f64>) -> Result<JsValue, JsValue> {
    use crate::divergence::DivergenceMetrics;

    let metrics =
        DivergenceMetrics::compute(&p, &q).map_err(|e| JsValue::from_str(&e.to_string()))?;

    let json = serde_json::to_string(&metrics)
        .map_err(|e| JsValue::from_str(&format!("Serialization error: {}", e)))?;
    Ok(JsValue::from_str(&json))
}

/// Batch compute divergences for multiple pairs
#[wasm_bindgen(js_name = "batchComputeDivergence")]
pub fn batch_compute_divergence(pairs_json: &str) -> Result<JsValue, JsValue> {
    use crate::divergence::DivergenceMetrics;

    #[derive(serde::Deserialize)]
    struct Pair {
        p: Vec<f64>,
        q: Vec<f64>,
    }

    let pairs: Vec<Pair> = serde_json::from_str(pairs_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid input: {}", e)))?;

    let results: Vec<Result<DivergenceMetrics, String>> = pairs
        .iter()
        .map(|pair| DivergenceMetrics::compute(&pair.p, &pair.q).map_err(|e| e.to_string()))
        .collect();

    let json = serde_json::to_string(&results)
        .map_err(|e| JsValue::from_str(&format!("Serialization error: {}", e)))?;
    Ok(JsValue::from_str(&json))
}

/// Create a compression scheme directly (without model)
#[wasm_bindgen(js_name = "createScheme")]
pub fn create_scheme(actor_id: &str, distribution: Vec<f64>) -> Result<JsValue, JsValue> {
    let scheme = CompressionScheme::new(actor_id, distribution, None);
    let json = scheme
        .to_json()
        .map_err(|e| JsValue::from_str(&e.to_string()))?;
    Ok(JsValue::from_str(&json))
}

/// Compute conflict potential between two schemes directly
#[wasm_bindgen(js_name = "computePotential")]
pub fn compute_potential(scheme_a_json: &str, scheme_b_json: &str) -> Result<JsValue, JsValue> {
    let scheme_a = CompressionScheme::from_json(scheme_a_json)
        .map_err(|e| JsValue::from_str(&e.to_string()))?;
    let scheme_b = CompressionScheme::from_json(scheme_b_json)
        .map_err(|e| JsValue::from_str(&e.to_string()))?;

    let potential = ConflictPotential::compute(&scheme_a, &scheme_b)
        .map_err(|e| JsValue::from_str(&e.to_string()))?;

    let json = potential
        .to_json()
        .map_err(|e| JsValue::from_str(&e.to_string()))?;
    Ok(JsValue::from_str(&json))
}

#[cfg(test)]
mod tests {
    use super::*;
    use wasm_bindgen_test::*;

    wasm_bindgen_test_configure!(run_in_browser);

    #[wasm_bindgen_test]
    fn test_wasm_engine_basic() {
        let mut engine = WasmDivergenceEngine::new(5);

        engine
            .register_actor("A", Some(vec![0.5, 0.3, 0.1, 0.05, 0.05]))
            .unwrap();
        engine
            .register_actor("B", Some(vec![0.1, 0.2, 0.3, 0.25, 0.15]))
            .unwrap();

        let potential = engine.compute_conflict_potential("A", "B").unwrap();
        assert!(!potential.is_null());
    }

    #[wasm_bindgen_test]
    fn test_standalone_divergence() {
        let p = vec![0.5, 0.3, 0.2];
        let q = vec![0.3, 0.4, 0.3];

        let result = compute_divergence(p, q).unwrap();
        assert!(!result.is_null());
    }
}
