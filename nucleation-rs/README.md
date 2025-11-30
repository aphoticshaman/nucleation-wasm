# nucleation-wasm

Phase transition detection and compression dynamics for early warning systems.

## Overview

`nucleation-wasm` provides tools for detecting phase transitions in complex systems and monitoring conflict potential between actors. Built in Rust, compiled to WebAssembly for browser and Node.js deployment.

### Core Features

- **Variance Inflection Detection**: Identify phase transitions via second derivative of rolling variance (d²V/dt²)
- **Compression Dynamics**: KL-divergence framework for modeling conflict potential between actors
- **Shepherd Dynamics**: Unified early warning combining both approaches

### Theoretical Foundation

From the Recursive Recursion Manifest (RRM) framework:

- **Conflict is compression divergence. Peace is alignment.**
- Conflict potential Φ(A,B) = D_KL(C_A || C_B) + D_KL(C_B || C_A)
- Transitions are preceded by **inflection points** in variance dynamics

## Installation

### npm (Browser/Node.js)

```bash
npm install nucleation-wasm
```

### Cargo (Rust)

```toml
[dependencies]
nucleation = "0.2"
```

## Quick Start

### Phase Transition Detection

Detect phase transitions in any numeric time series:

```typescript
import { NucleationDetector, DetectorConfig, Phase } from 'nucleation-wasm';

const config = new DetectorConfig();
config.threshold = 1.5;
config.window_size = 40;

const detector = new NucleationDetector(config);

for (const value of timeSeries) {
  const phase = detector.update(value);

  switch (phase) {
    case Phase.Critical:
      console.log("Transition imminent!");
      break;
  }
}
```

### Compression Dynamics (Conflict Potential)

Model conflict potential between actors based on worldview divergence:

```typescript
import { CompressionModel } from 'nucleation-wasm';

const model = new CompressionModel(50); // 50 category dimensions

// Register actors with their "compression schemes" (worldviews)
model.registerActor("USA", [0.3, 0.2, 0.15, /* ... */]);
model.registerActor("RUS", [0.1, 0.15, 0.2, /* ... */]);

// Compute conflict potential
const phi = model.conflictPotential("USA", "RUS");
console.log(`USA-RUS conflict potential: ${phi.toFixed(3)}`);
```

### Shepherd Dynamics (Unified Early Warning)

Combine compression dynamics with variance inflection for early warning:

```typescript
import { Shepherd, AlertLevel } from 'nucleation-wasm';

const shepherd = new Shepherd(50);

shepherd.registerActor("USA");
shepherd.registerActor("RUS");

// Update with observations over time
const alerts = shepherd.updateActor("USA", observation, timestamp);

for (const alert of alerts) {
  if (alert.alertLevel >= AlertLevel.Orange) {
    console.warn(`WARNING: ${alert.message}`);
  }
}
```

## Architecture

```
nucleation-rs/
├── src/
│   ├── lib.rs          # Crate root + re-exports
│   ├── variance.rs     # VarianceInflectionDetector (d²V/dt²)
│   ├── compression.rs  # CompressionScheme, ConflictPotential
│   ├── shepherd.rs     # ShepherdDynamics (unified EWS)
│   ├── entropy.rs      # Shannon, permutation, KL, entropy rate
│   ├── distance.rs     # Hellinger, JS, Fisher-Rao, Wasserstein
│   ├── signal.rs       # Rolling stats, gradients, phase tracking
│   ├── detector.rs     # CognitiveDetector (legacy entropy-based)
│   ├── acr.rs          # ACRController (Kuramoto phase-locking)
│   └── wasm.rs         # WASM bindings
└── Cargo.toml
```

## API Reference

### NucleationDetector

Variance inflection detector for phase transitions.

| Method | Description |
|--------|-------------|
| `update(value)` | Process single observation, returns Phase |
| `updateBatch(values)` | Process array of observations |
| `currentPhase()` | Get current phase classification |
| `confidence()` | Get confidence (0-1) in current assessment |
| `currentVariance()` | Get current rolling variance |
| `inflectionMagnitude()` | Get current inflection z-score |
| `reset()` | Reset detector state |

### CompressionModel

KL-divergence conflict potential model.

| Method | Description |
|--------|-------------|
| `registerActor(id, distribution?)` | Register actor with optional initial worldview |
| `updateActor(id, observation, timestamp)` | Update actor's compression scheme |
| `conflictPotential(a, b)` | Get Φ(A,B) between two actors |
| `conflictPotentialDetails(a, b)` | Get full breakdown including risk category |
| `actors()` | List all registered actors |

### Shepherd

Unified early warning system.

| Method | Description |
|--------|-------------|
| `registerActor(id, distribution?)` | Register actor |
| `updateActor(id, observation, timestamp)` | Update and check for nucleation |
| `checkDyad(a, b, timestamp)` | Check specific pair for nucleation |
| `checkAllDyads(timestamp)` | Check all pairs |
| `phiHistory(a, b)` | Get Φ time series for a dyad |

## Building from Source

```bash
# Run tests
cargo test

# Build WASM package
wasm-pack build --target web --features wasm

# Build for production
wasm-pack build --release --target web --features wasm
```

## Validation

The algorithms are validated against synthetic phase transitions:

- **Variance Inflection**: F1 = 0.769, 100% accuracy on commitment-type transitions
- **Compression Dynamics**: r = 0.33 correlation with conflict intensity, r = 0.67 temporal precedence

See `validation/` directories for experiment code and results.

## Key Equations

### Conflict Potential (Compression Dynamics)
```
Φ(A,B) = D_KL(C_A || C_B) + D_KL(C_B || C_A)
```

### Variance Inflection (Phase Detection)
```
Signal = |d²V/dt²| where V = rolling variance
Transition when z-score(Signal) > threshold
```

### Shepherd Dynamics (Unified)
```
Monitor Φ(t) trajectory with variance inflection detector
Alert when nucleation signature detected in divergence dynamics
```

## License

MIT OR Apache-2.0

## Author

Ryan J Cardwell (Archer Phoenix)
- GitHub: [@aphoticshaman](https://github.com/aphoticshaman)
