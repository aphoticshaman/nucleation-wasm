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

1. **Early Warning Systems** - Monitor divergence trajectories
2. **Intelligence Analysis** - Track worldview drift
3. **Diplomatic Support** - Identify alignment points
4. **Risk Assessment** - Geopolitical scoring for investment/supply chain
5. **Research** - Quantitative conflict studies

## Research

The theoretical foundation is published on Zenodo:

- [Compression Dynamics of Conflict](https://zenodo.org/records/17766946)

## License

MIT

---

[@Benthic_Shadow](https://twitter.com/Benthic_Shadow)
