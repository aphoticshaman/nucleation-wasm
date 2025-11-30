/* tslint:disable */
/* eslint-disable */
/**
 * Nucleation WASM - Phase transition detection and compression dynamics
 *
 * @packageDocumentation
 */

/**
 * Phase classification for detector state.
 */
export enum Phase {
  Stable = 0,
  Approaching = 1,
  Critical = 2,
  Transitioning = 3,
}

/**
 * Alert level for Shepherd warnings.
 */
export enum AlertLevel {
  Green = 0,
  Yellow = 1,
  Orange = 2,
  Red = 3,
}

/**
 * Configuration for the variance inflection detector.
 */
export class DetectorConfig {
  constructor();

  /** Create a sensitive configuration (lower thresholds). */
  static sensitive(): DetectorConfig;

  /** Create a conservative configuration (higher thresholds). */
  static conservative(): DetectorConfig;

  /** Window size for rolling variance calculation. */
  window_size: number;

  /** Window size for smoothing the variance trajectory. */
  smoothing_window: number;

  /** Threshold for inflection magnitude (z-score). */
  threshold: number;

  /** Minimum observations between detected transitions. */
  min_peak_distance: number;

  /** Smoothing kernel type: "uniform" or "gaussian". */
  kernel: string;
}

/**
 * Variance Inflection Detector for phase transition detection.
 *
 * Detects phase transitions by finding peaks in the second derivative
 * of rolling variance. Works on any numeric time series.
 *
 * @example
 * ```typescript
 * const config = new DetectorConfig();
 * config.threshold = 1.5;
 *
 * const detector = new NucleationDetector(config);
 *
 * for (const value of timeSeries) {
 *   const phase = detector.update(value);
 *   if (phase === Phase.Critical) {
 *     console.log("Transition imminent!");
 *   }
 * }
 * ```
 */
export class NucleationDetector {
  /**
   * Create a new detector with the given configuration.
   */
  constructor(config: DetectorConfig);

  /**
   * Create a detector with default configuration.
   */
  static with_defaults(): NucleationDetector;

  /**
   * Process a single observation.
   * @returns Current phase classification.
   */
  update(value: number): Phase;

  /**
   * Process multiple observations.
   * @returns Phase after processing all values.
   */
  update_batch(values: Float64Array | number[]): Phase;

  /**
   * Get the current phase.
   */
  currentPhase(): Phase;

  /**
   * Get confidence in the current assessment (0-1).
   */
  confidence(): number;

  /**
   * Get the current rolling variance.
   */
  currentVariance(): number;

  /**
   * Get the current inflection magnitude (z-score).
   */
  inflectionMagnitude(): number;

  /**
   * Get the total number of observations processed.
   */
  count(): number;

  /**
   * Reset the detector state.
   */
  reset(): void;

  /**
   * Serialize state to JSON string.
   */
  serialize(): string;

  /**
   * Deserialize state from JSON string.
   */
  static deserialize(json: string): NucleationDetector;
}

/**
 * Conflict potential details between two actors.
 */
export interface ConflictPotentialDetails {
  actorA: string;
  actorB: string;
  /** Symmetric KL divergence (conflict potential). */
  phi: number;
  /** Jensen-Shannon divergence (bounded [0,1]). */
  js: number;
  /** Hellinger distance. */
  hellinger: number;
  /** D_KL(A || B). */
  klAB: number;
  /** D_KL(B || A). */
  klBA: number;
  /** Risk category: "LOW" | "MODERATE" | "ELEVATED" | "HIGH" | "CRITICAL". */
  riskCategory: string;
}

/**
 * Compression Dynamics Model for conflict potential calculation.
 *
 * Tracks actor "compression schemes" (worldviews) and computes
 * KL-divergence based conflict potential.
 *
 * @example
 * ```typescript
 * const model = new CompressionModel(50); // 50 categories
 *
 * model.registerActor("USA", [0.3, 0.2, ...]); // 50 probabilities
 * model.registerActor("RUS", [0.1, 0.15, ...]);
 *
 * const phi = model.conflictPotential("USA", "RUS");
 * console.log(`Conflict potential: ${phi}`);
 * ```
 */
export class CompressionModel {
  /**
   * Create a new model with the specified number of categories.
   */
  constructor(n_categories: number);

  /**
   * Set the learning rate for scheme updates.
   */
  setLearningRate(rate: number): void;

  /**
   * Register a new actor with optional initial distribution.
   */
  registerActor(actor_id: string, distribution?: Float64Array | number[]): void;

  /**
   * Update an actor's scheme with a new observation.
   * @returns True if actor exists and was updated.
   */
  updateActor(actor_id: string, observation: Float64Array | number[], timestamp: number): boolean;

  /**
   * Compute conflict potential (phi) between two actors.
   * @returns Phi value or undefined if actors not found.
   */
  conflictPotential(actor_a: string, actor_b: string): number | undefined;

  /**
   * Get full conflict potential details.
   */
  conflictPotentialDetails(actor_a: string, actor_b: string): ConflictPotentialDetails | null;

  /**
   * Get list of registered actors.
   */
  actors(): string[];

  /**
   * Get an actor's current entropy.
   */
  actorEntropy(actor_id: string): number | undefined;
}

/**
 * Nucleation alert from Shepherd analysis.
 */
export interface NucleationAlertData {
  actorA: string;
  actorB: string;
  alertLevel: AlertLevel;
  phi: number;
  phiTrend: number;
  confidence: number;
  timestamp: number;
  message: string;
}

/**
 * Shepherd Dynamics: Unified early warning system.
 *
 * Combines compression dynamics with variance inflection detection
 * to identify "nucleation moments" before conflict escalation.
 *
 * @example
 * ```typescript
 * const shepherd = new Shepherd(50);
 *
 * shepherd.registerActor("USA");
 * shepherd.registerActor("RUS");
 *
 * // Update over time
 * const alerts = shepherd.updateActor("USA", observation, timestamp);
 *
 * for (const alert of alerts) {
 *   if (alert.alertLevel >= AlertLevel.Orange) {
 *     console.warn(alert.message);
 *   }
 * }
 * ```
 */
export class Shepherd {
  /**
   * Create a new Shepherd system.
   */
  constructor(n_categories: number);

  /**
   * Register a new actor.
   */
  registerActor(actor_id: string, distribution?: Float64Array | number[]): void;

  /**
   * Update an actor and check for nucleation alerts.
   * @returns Array of alert objects for any triggered warnings.
   */
  updateActor(actor_id: string, observation: Float64Array | number[], timestamp: number): NucleationAlertData[];

  /**
   * Check a specific dyad for nucleation.
   */
  checkDyad(actor_a: string, actor_b: string, timestamp: number): NucleationAlertData | null;

  /**
   * Check all dyads for nucleation.
   */
  checkAllDyads(timestamp: number): NucleationAlertData[];

  /**
   * Get conflict potential between two actors.
   */
  conflictPotential(actor_a: string, actor_b: string): number | undefined;

  /**
   * Get list of registered actors.
   */
  actors(): string[];

  /**
   * Get phi history for a dyad as flat array [t1, phi1, t2, phi2, ...].
   */
  phiHistory(actor_a: string, actor_b: string): Float64Array;
}

/**
 * Get the library version.
 */
export function version(): string;

/**
 * Compute KL divergence between two distributions.
 */
export function klDivergence(p: Float64Array | number[], q: Float64Array | number[]): number;

/**
 * Compute Hellinger distance between two distributions.
 */
export function hellingerDistance(p: Float64Array | number[], q: Float64Array | number[]): number;

/**
 * Compute Jensen-Shannon divergence between two distributions.
 */
export function jensenShannonDivergence(p: Float64Array | number[], q: Float64Array | number[]): number;

/**
 * Compute Shannon entropy of a distribution (from counts).
 */
export function shannonEntropy(counts: Uint32Array | number[]): number;
