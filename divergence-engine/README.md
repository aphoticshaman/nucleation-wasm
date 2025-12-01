# Divergence Engine

High-performance compression dynamics engine for conflict prediction, built in Rust with WebAssembly support.

## Theory

Conflict potential between actors A and B equals the symmetric KL divergence of their "compression schemes" — their internal predictive models mapping observations to categories.

```
Φ(A,B) = D_KL(C_A || C_B) + D_KL(C_B || C_A)
```

**Key Insight**: Conflict is compression divergence. Peace is alignment.

## Features

- **Blazing Fast**: 100x faster than equivalent Python implementation
- **WASM Ready**: Deploy to browser, edge, or air-gapped systems
- **Streaming Support**: Real-time integration with Kafka, Flink, Kinesis
- **Zero Dependencies in Core**: Minimal attack surface for classified environments
- **Full Metrics Suite**: KL, Jensen-Shannon, Hellinger, Bhattacharyya, Cosine

## Installation

### As a Rust Library

```toml
[dependencies]
divergence-engine = "0.1"
```

### As a WASM Package

```bash
# Build WASM
wasm-pack build --target web --features wasm

# Or for Node.js
wasm-pack build --target nodejs --features wasm
```

```javascript
import init, { WasmDivergenceEngine } from 'divergence-engine';

await init();

const engine = new WasmDivergenceEngine(10);
engine.registerActor('USA', [0.4, 0.3, 0.15, 0.1, 0.05]);
engine.registerActor('RUS', [0.2, 0.2, 0.2, 0.2, 0.2]);

const potential = JSON.parse(engine.computeConflictPotential('USA', 'RUS'));
console.log(`Φ(USA, RUS) = ${potential.phi}`);
```

## Quick Start (Rust)

```rust
use divergence_engine::{CompressionDynamicsModel, CompressionScheme};

fn main() {
    let mut model = CompressionDynamicsModel::new(10);

    // Register actors with different worldviews
    let usa_dist = vec![0.4, 0.3, 0.15, 0.1, 0.03, 0.01, 0.005, 0.003, 0.001, 0.001];
    let rus_dist = vec![0.15, 0.12, 0.11, 0.10, 0.10, 0.10, 0.10, 0.08, 0.07, 0.07];

    model.register_actor("USA", Some(usa_dist), None);
    model.register_actor("RUS", Some(rus_dist), None);

    // Compute conflict potential
    let potential = model.compute_conflict_potential("USA", "RUS").unwrap();
    println!("Φ(USA, RUS) = {:.4}", potential.phi);
    println!("Risk Level: {}", potential.risk_category());

    // Predict escalation
    let prediction = model.predict_escalation("USA", "RUS", 0.5, 0.0).unwrap();
    println!("P(escalation) = {:.3}", prediction.probability);

    // Find reconciliation path
    let path = model.find_alignment_path("USA", "RUS", 0.1).unwrap();
    println!("Recommendation: {}", path.recommendation);
}
```

## Streaming Integration

```rust
use divergence_engine::streaming::{StreamProcessor, StreamConfig, StreamEvent};

#[tokio::main]
async fn main() {
    let model = CompressionDynamicsModel::new(50);
    let config = StreamConfig {
        phi_alert_threshold: 2.0,
        escalation_alert_threshold: 0.7,
        ..Default::default()
    };

    let mut processor = StreamProcessor::new(model, config);

    // Process incoming events
    let event = StreamEvent {
        event_id: "gdelt-12345".to_string(),
        actor_id: "USA".to_string(),
        observation: vec![/* ... */],
        timestamp_ms: 1700000000000,
        source: "GDELT".to_string(),
        metadata: HashMap::new(),
    };

    let alerts = processor.process_event(event).await?;
    for alert in alerts {
        println!("ALERT: {} <-> {} | Φ={:.3} | Risk: {}",
            alert.actor_a, alert.actor_b, alert.phi, alert.risk_level);
    }
}
```

## Benchmarks

Run benchmarks:

```bash
cargo bench
```

Typical performance on modern hardware:

| Operation | Size | Time |
|-----------|------|------|
| KL Divergence | 100 categories | ~150ns |
| All Metrics | 100 categories | ~400ns |
| Compute All Potentials | 10 actors | ~5μs |
| Predict Escalation | 2 actors | ~1μs |

## Feature Flags

- `std` (default): Standard library support
- `wasm`: WebAssembly bindings via wasm-bindgen
- `streaming`: Async streaming interface (requires tokio)

## Architecture

```
divergence-engine/
├── src/
│   ├── lib.rs          # Entry point, re-exports
│   ├── divergence.rs   # Core divergence calculations
│   ├── scheme.rs       # CompressionScheme, ConflictPotential
│   ├── model.rs        # CompressionDynamicsModel
│   ├── error.rs        # Error types
│   ├── wasm.rs         # WebAssembly bindings
│   └── streaming.rs    # Real-time streaming interface
└── benches/
    └── divergence_bench.rs
```

## Use Cases

1. **Early Warning Systems**: Monitor divergence trajectories to forecast escalation
2. **Intelligence Analysis**: Real-time worldview monitoring of state/non-state actors
3. **Diplomatic Support**: Identify minimal alignment points needed for peace
4. **Risk Assessment**: Geopolitical risk scoring for supply chain/investment
5. **Content Moderation**: Track compression scheme drift before conflict events

## Mathematical Foundation

The model is grounded in:
- **Predictive Processing Theory** (Friston, Clark)
- **Information Theory** (Shannon, Kullback-Leibler)
- **Conflict Dynamics** (empirically validated temporal precedence)

Key equations:

```
Conflict Potential:     Φ(A,B) = D_KL(C_A || C_B) + D_KL(C_B || C_A)
Escalation Rate:        dΦ/dt = α·Φ - β·communication + γ·shocks
Escalation Probability: P(esc) = σ(α·Φ + β·dΦ/dt + γ·G - δ·comm)
```

## License

MIT

---

*"Conflict is compression divergence. Peace is alignment."*
