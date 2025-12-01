# Divergence Engine

[![CI](https://github.com/aphoticshaman/nucleation-wasm/actions/workflows/ci.yml/badge.svg)](https://github.com/aphoticshaman/nucleation-wasm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

High-performance conflict prediction engine using information theory. Built in Rust with WebAssembly support.

```
Φ(A,B) = D_KL(C_A || C_B) + D_KL(C_B || C_A)
```

**Conflict is compression divergence. Peace is alignment.**

## What It Does

Predicts conflict potential between actors by measuring how differently they "compress" reality into worldviews. Uses KL divergence to quantify worldview gaps.

- **100x faster** than Python equivalent
- **WASM-ready** for browser, edge, and air-gapped deployment
- **Streaming support** for real-time monitoring (Kafka, Flink)
- **Minimal dependencies** for classified environment deployment

## The Theory (Plain English)

Every entity—nation, company, market, person—has a **mental model** of how the world works. They assign probabilities to outcomes, prioritize certain categories over others, and use this model to predict what happens next.

When two entities' models diverge significantly, they make incompatible predictions. This creates friction, conflict, and risk.

**KL Divergence** (Kullback-Leibler) measures exactly this: "How surprised would Entity A be if the world actually worked the way Entity B thinks it does?"

```
D_KL(P || Q) = Σ P(x) · log(P(x) / Q(x))
```

In practical terms:
- If both entities assign similar probabilities → low divergence → low conflict potential
- If Entity A thinks X is 80% likely and Entity B thinks X is 5% likely → high divergence → high conflict potential

**Symmetric KL (Φ)** measures this both ways—how surprised A would be by B's world, AND how surprised B would be by A's world:

```
Φ(A,B) = D_KL(A || B) + D_KL(B || A)
```

**Interpreting Φ:**
| Φ Value | Interpretation |
|---------|----------------|
| 0.0 - 0.5 | Low divergence. Normal operating friction. |
| 0.5 - 1.5 | Moderate divergence. Watch for escalation. |
| 1.5 - 2.5 | High divergence. Active management required. |
| > 2.5 | Critical divergence. Conflict likely without intervention. |

## Why Not Just Use ML?

Most risk models are neural network black boxes. You feed in data, magic happens, you get a number. Good luck explaining why to your board, regulator, or client.

**Divergence Engine is mathematically transparent:**

| Feature | Black Box ML | Divergence Engine |
|---------|--------------|-------------------|
| Explainability | "The model says..." | "Entity A assigns 40% to X, Entity B assigns 5%. This 8x gap drives Φ." |
| Auditability | Retrain entire model | Inspect probability distributions directly |
| Regulatory | "Trust the algorithm" | "Here's the math, here's the data, here's the calculation" |
| Data Requirements | Millions of samples | Works with small, interpretable distributions |

The math is 70+ years old (Shannon, Kullback, Leibler). Same foundation as compression algorithms, ML loss functions, and statistical hypothesis testing.

**Every output traces back to inputs. Every score is auditable.**

## Full Metrics Suite

Beyond symmetric KL divergence (Φ), the engine computes:

| Metric | Formula | When to Use |
|--------|---------|-------------|
| **Symmetric KL (Φ)** | D_KL(P\|\|Q) + D_KL(Q\|\|P) | Primary conflict potential. Sensitive to tail differences. |
| **Jensen-Shannon (JS)** | ½D_KL(P\|\|M) + ½D_KL(Q\|\|M) | Bounded [0,1], always defined. Good for visualization. |
| **Hellinger** | √(½Σ(√P - √Q)²) | Robust to outliers. Geometric interpretation. |
| **Bhattacharyya** | -ln(Σ√(P·Q)) | Related to classification error. Statistical hypothesis testing. |
| **Cosine Similarity** | (P·Q)/(‖P‖·‖Q‖) | Direction comparison, ignoring magnitude. |

**All metrics computed in single pass for efficiency (~400ns for 100 categories).**

## Quick Start

### Rust

```toml
[dependencies]
divergence-engine = { path = "./divergence-engine" }
```

```rust
use divergence_engine::CompressionDynamicsModel;

let mut model = CompressionDynamicsModel::new(10);

model.register_actor("USA", Some(vec![0.4, 0.3, 0.2, 0.1]), None);
model.register_actor("CHN", Some(vec![0.3, 0.3, 0.2, 0.2]), None);

let potential = model.compute_conflict_potential("USA", "CHN").unwrap();
println!("Φ = {:.4}, Risk: {}", potential.phi, potential.risk_category());
```

### WASM

```bash
cd divergence-engine
wasm-pack build --target web --features wasm
```

```javascript
import init, { WasmDivergenceEngine } from './pkg/divergence_engine.js';

await init();
const engine = new WasmDivergenceEngine(10);
engine.registerActor('USA', [0.4, 0.3, 0.2, 0.1]);
engine.registerActor('CHN', [0.3, 0.3, 0.2, 0.2]);

const result = JSON.parse(engine.computeConflictPotential('USA', 'CHN'));
console.log(result);
```

### API

Deploy the Cloudflare Worker:

```bash
cd api
wrangler deploy
```

```bash
curl -X POST https://your-api.workers.dev/predict \
  -H "Content-Type: application/json" \
  -d '{"actor_a": "USA", "actor_b": "CHN"}'
```

## Project Structure

```
nucleation-wasm/
├── divergence-engine/     # Rust core library
│   ├── src/
│   │   ├── lib.rs         # Entry point
│   │   ├── divergence.rs  # KL, JS, Hellinger calculations
│   │   ├── scheme.rs      # CompressionScheme, ConflictPotential
│   │   ├── model.rs       # CompressionDynamicsModel
│   │   ├── streaming.rs   # Real-time interface
│   │   └── wasm.rs        # WASM bindings
│   └── Cargo.toml
├── api/                   # Cloudflare Worker API
│   ├── worker.js
│   └── index.html         # Landing page
├── docs/
│   ├── research/          # Academic foundation
│   └── content/           # Blog/newsletter drafts
└── .github/
    └── workflows/         # CI/CD with security scanning
```

## Security

- Dependency auditing via `cargo audit`
- License compliance via `cargo deny`
- Static analysis via Semgrep
- Automated dependency updates via Dependabot

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Use Cases

**See [Industry Applications](docs/INDUSTRY-USE-CASES.md) for detailed integration guides.**

| Industry | Application | Value |
|----------|-------------|-------|
| **Finance** | Portfolio regime detection, counterparty risk, sentiment divergence | Catch correlation breakdown before crisis |
| **Defense** | Adversary modeling, coalition stability, early warning | 6-12 month lead on traditional indicators |
| **Healthcare** | Trial design, resource allocation, epidemiology | Identify population heterogeneity |
| **Manufacturing** | Supplier risk, quality control, vendor health | Early stockout/drift detection |
| **Geopolitics** | Conflict forecasting, negotiation support, scenario planning | Quantify worldview gaps |
| **Cybersecurity** | Threat actor profiling, insider detection, posture drift | Explainable behavioral baselines |
| **Data Science** | Anomaly detection, model drift, clustering validation | Distribution-aware analytics |
| **Logistics** | Network stability, route risk, demand forecasting | Predict system fragility |

### Integration Options

- **Rust library**: Maximum performance, embed in existing systems
- **WebAssembly**: Browser, edge, air-gapped (no runtime required)
- **REST API**: Quick integration via Cloudflare Workers
- **Streaming**: Real-time Kafka/Flink/Kinesis pipelines

**MIT Licensed. Fork it. Extend it. Build on it.**

## Research

The theoretical foundation is published on Zenodo:

- [Compression Dynamics of Conflict](https://zenodo.org/records/17766946)

## License

MIT

---

[@Benthic_Shadow](https://twitter.com/Benthic_Shadow)
