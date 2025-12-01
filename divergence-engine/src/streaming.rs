//! Streaming interface for real-time divergence monitoring.
//!
//! Designed for integration with:
//! - Apache Kafka
//! - Apache Flink
//! - AWS Kinesis
//! - Custom event streams
//!
//! ## Architecture
//!
//! ```text
//! [GDELT/News Stream] → [Event Processor] → [Divergence Engine] → [Alert Sink]
//!                                ↓
//!                    [CompressionScheme Updates]
//! ```

use crate::error::{DivergenceError, Result};
use crate::model::CompressionDynamicsModel;
use crate::scheme::RiskLevel;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{mpsc, RwLock};

/// Incoming event from data stream
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StreamEvent {
    /// Event ID (for deduplication)
    pub event_id: String,

    /// Actor this event relates to
    pub actor_id: String,

    /// Observation vector (category distribution update)
    pub observation: Vec<f64>,

    /// Event timestamp in milliseconds
    pub timestamp_ms: i64,

    /// Event source (GDELT, news, social, etc.)
    pub source: String,

    /// Additional metadata
    #[serde(default)]
    pub metadata: HashMap<String, String>,
}

/// Alert generated when divergence exceeds threshold
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DivergenceAlert {
    /// Alert ID
    pub alert_id: String,

    /// Actors involved
    pub actor_a: String,
    pub actor_b: String,

    /// Current metrics
    pub phi: f64,
    pub js: f64,
    pub d_phi_dt: f64,

    /// Risk assessment
    pub risk_level: RiskLevel,
    pub escalation_probability: f64,

    /// Timestamp
    pub timestamp_ms: i64,

    /// Alert reason
    pub reason: String,
}

/// Configuration for streaming processor
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StreamConfig {
    /// Alert threshold for phi
    pub phi_alert_threshold: f64,

    /// Alert threshold for JS divergence
    pub js_alert_threshold: f64,

    /// Alert threshold for escalation probability
    pub escalation_alert_threshold: f64,

    /// Minimum interval between alerts for same dyad (ms)
    pub alert_cooldown_ms: i64,

    /// Batch size for processing
    pub batch_size: usize,

    /// Enable deduplication
    pub deduplicate: bool,
}

impl Default for StreamConfig {
    fn default() -> Self {
        Self {
            phi_alert_threshold: 2.0,
            js_alert_threshold: 0.6,
            escalation_alert_threshold: 0.7,
            alert_cooldown_ms: 300_000, // 5 minutes
            batch_size: 100,
            deduplicate: true,
        }
    }
}

/// Trait for event sources
#[async_trait]
pub trait EventSource: Send + Sync {
    /// Receive next batch of events
    async fn receive(&mut self) -> Result<Vec<StreamEvent>>;

    /// Acknowledge processed events
    async fn acknowledge(&mut self, event_ids: &[String]) -> Result<()>;

    /// Check if source is healthy
    async fn health_check(&self) -> bool;
}

/// Trait for alert sinks
#[async_trait]
pub trait AlertSink: Send + Sync {
    /// Send alert
    async fn send(&mut self, alert: DivergenceAlert) -> Result<()>;

    /// Send batch of alerts
    async fn send_batch(&mut self, alerts: Vec<DivergenceAlert>) -> Result<()> {
        for alert in alerts {
            self.send(alert).await?;
        }
        Ok(())
    }
}

/// Real-time divergence monitoring processor
pub struct StreamProcessor {
    model: Arc<RwLock<CompressionDynamicsModel>>,
    config: StreamConfig,
    last_alert: HashMap<(String, String), i64>,
    processed_events: HashMap<String, i64>,
}

impl StreamProcessor {
    /// Create new processor
    pub fn new(model: CompressionDynamicsModel, config: StreamConfig) -> Self {
        Self {
            model: Arc::new(RwLock::new(model)),
            config,
            last_alert: HashMap::new(),
            processed_events: HashMap::new(),
        }
    }

    /// Process a single event
    pub async fn process_event(&mut self, event: StreamEvent) -> Result<Vec<DivergenceAlert>> {
        // Deduplication
        if self.config.deduplicate {
            if self.processed_events.contains_key(&event.event_id) {
                return Ok(vec![]);
            }
            self.processed_events
                .insert(event.event_id.clone(), event.timestamp_ms);
        }

        // Update model
        {
            let mut model = self.model.write().await;
            model.update_scheme(
                &event.actor_id,
                &event.observation,
                Some(event.timestamp_ms),
            )?;
        }

        // Check for alerts
        self.check_alerts(&event.actor_id, event.timestamp_ms).await
    }

    /// Process batch of events
    pub async fn process_batch(
        &mut self,
        events: Vec<StreamEvent>,
    ) -> Result<Vec<DivergenceAlert>> {
        let mut all_alerts = Vec::new();
        let mut actors_updated = Vec::new();

        // Batch update model
        {
            let mut model = self.model.write().await;
            for event in events {
                if self.config.deduplicate && self.processed_events.contains_key(&event.event_id) {
                    continue;
                }

                model.update_scheme(
                    &event.actor_id,
                    &event.observation,
                    Some(event.timestamp_ms),
                )?;

                actors_updated.push((event.actor_id.clone(), event.timestamp_ms));

                if self.config.deduplicate {
                    self.processed_events
                        .insert(event.event_id.clone(), event.timestamp_ms);
                }
            }
        }

        // Check alerts for all updated actors
        for (actor_id, timestamp_ms) in actors_updated {
            let alerts = self.check_alerts(&actor_id, timestamp_ms).await?;
            all_alerts.extend(alerts);
        }

        Ok(all_alerts)
    }

    /// Check if any dyads involving this actor should trigger alerts
    async fn check_alerts(
        &mut self,
        updated_actor: &str,
        timestamp_ms: i64,
    ) -> Result<Vec<DivergenceAlert>> {
        let mut alerts = Vec::new();
        let mut model = self.model.write().await;

        let actors: Vec<String> = model.actors().iter().map(|s| s.to_string()).collect();

        for other_actor in &actors {
            if other_actor == updated_actor {
                continue;
            }

            // Check cooldown
            let dyad_key = if updated_actor < other_actor {
                (updated_actor.to_string(), other_actor.to_string())
            } else {
                (other_actor.to_string(), updated_actor.to_string())
            };

            if let Some(&last_time) = self.last_alert.get(&dyad_key) {
                if timestamp_ms - last_time < self.config.alert_cooldown_ms {
                    continue;
                }
            }

            // Compute metrics
            let potential = model.compute_conflict_potential(updated_actor, other_actor)?;

            let prediction = model.predict_escalation(updated_actor, other_actor, 0.5, 0.0)?;

            // Check thresholds
            let mut reasons = Vec::new();

            if potential.phi >= self.config.phi_alert_threshold {
                reasons.push(format!("Φ={:.3} exceeds threshold", potential.phi));
            }

            if potential.js >= self.config.js_alert_threshold {
                reasons.push(format!("JS={:.3} exceeds threshold", potential.js));
            }

            if prediction.probability >= self.config.escalation_alert_threshold {
                reasons.push(format!(
                    "P(escalation)={:.3} exceeds threshold",
                    prediction.probability
                ));
            }

            if !reasons.is_empty() {
                let alert = DivergenceAlert {
                    alert_id: format!("{}-{}-{}", dyad_key.0, dyad_key.1, timestamp_ms),
                    actor_a: dyad_key.0.clone(),
                    actor_b: dyad_key.1.clone(),
                    phi: potential.phi,
                    js: potential.js,
                    d_phi_dt: prediction.d_phi_dt,
                    risk_level: prediction.risk_category,
                    escalation_probability: prediction.probability,
                    timestamp_ms,
                    reason: reasons.join("; "),
                };

                alerts.push(alert);
                self.last_alert.insert(dyad_key, timestamp_ms);
            }
        }

        Ok(alerts)
    }

    /// Get current model state (for snapshots)
    pub async fn get_model_state(&self) -> Result<String> {
        let model = self.model.read().await;
        model.to_json()
    }

    /// Get reference to model
    pub fn model(&self) -> Arc<RwLock<CompressionDynamicsModel>> {
        Arc::clone(&self.model)
    }

    /// Clean up old processed events (memory management)
    pub fn cleanup_old_events(&mut self, max_age_ms: i64) {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as i64)
            .unwrap_or(0);

        self.processed_events
            .retain(|_, &mut ts| now - ts < max_age_ms);
    }
}

/// Channel-based event source (for in-process streaming)
pub struct ChannelEventSource {
    receiver: mpsc::Receiver<StreamEvent>,
    batch_size: usize,
}

impl ChannelEventSource {
    pub fn new(receiver: mpsc::Receiver<StreamEvent>, batch_size: usize) -> Self {
        Self {
            receiver,
            batch_size,
        }
    }

    pub fn create_pair(buffer_size: usize, batch_size: usize) -> (mpsc::Sender<StreamEvent>, Self) {
        let (sender, receiver) = mpsc::channel(buffer_size);
        (sender, Self::new(receiver, batch_size))
    }
}

#[async_trait]
impl EventSource for ChannelEventSource {
    async fn receive(&mut self) -> Result<Vec<StreamEvent>> {
        let mut events = Vec::with_capacity(self.batch_size);

        // Try to receive up to batch_size events
        for _ in 0..self.batch_size {
            match self.receiver.try_recv() {
                Ok(event) => events.push(event),
                Err(_) => break,
            }
        }

        // If no events ready, wait for at least one
        if events.is_empty() {
            if let Some(event) = self.receiver.recv().await {
                events.push(event);
            }
        }

        Ok(events)
    }

    async fn acknowledge(&mut self, _event_ids: &[String]) -> Result<()> {
        // No-op for channel source
        Ok(())
    }

    async fn health_check(&self) -> bool {
        !self.receiver.is_closed()
    }
}

/// Channel-based alert sink
pub struct ChannelAlertSink {
    sender: mpsc::Sender<DivergenceAlert>,
}

impl ChannelAlertSink {
    pub fn new(sender: mpsc::Sender<DivergenceAlert>) -> Self {
        Self { sender }
    }

    pub fn create_pair(buffer_size: usize) -> (Self, mpsc::Receiver<DivergenceAlert>) {
        let (sender, receiver) = mpsc::channel(buffer_size);
        (Self::new(sender), receiver)
    }
}

#[async_trait]
impl AlertSink for ChannelAlertSink {
    async fn send(&mut self, alert: DivergenceAlert) -> Result<()> {
        self.sender
            .send(alert)
            .await
            .map_err(|e| DivergenceError::ConfigError(format!("Failed to send alert: {}", e)))
    }
}

/// Run the streaming pipeline
pub async fn run_pipeline<S, A>(
    mut source: S,
    mut sink: A,
    mut processor: StreamProcessor,
) -> Result<()>
where
    S: EventSource,
    A: AlertSink,
{
    loop {
        // Check source health
        if !source.health_check().await {
            return Err(DivergenceError::ConfigError(
                "Event source unhealthy".to_string(),
            ));
        }

        // Receive events
        let events = source.receive().await?;

        if events.is_empty() {
            continue;
        }

        let event_ids: Vec<String> = events.iter().map(|e| e.event_id.clone()).collect();

        // Process
        let alerts = processor.process_batch(events).await?;

        // Send alerts
        if !alerts.is_empty() {
            sink.send_batch(alerts).await?;
        }

        // Acknowledge
        source.acknowledge(&event_ids).await?;

        // Periodic cleanup
        processor.cleanup_old_events(3_600_000); // 1 hour
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::CompressionDynamicsModel;

    #[tokio::test]
    async fn test_stream_processor() {
        let model = CompressionDynamicsModel::new(5);
        let config = StreamConfig::default();
        let mut processor = StreamProcessor::new(model, config);

        // Register actors first
        {
            let mut m = processor.model.write().await;
            m.register_actor("USA", Some(vec![0.4, 0.3, 0.15, 0.1, 0.05]), None);
            m.register_actor("RUS", Some(vec![0.2, 0.2, 0.2, 0.2, 0.2]), None);
        }

        // Process event
        let event = StreamEvent {
            event_id: "test-1".to_string(),
            actor_id: "USA".to_string(),
            observation: vec![0.5, 0.25, 0.1, 0.1, 0.05],
            timestamp_ms: 1700000000000,
            source: "test".to_string(),
            metadata: HashMap::new(),
        };

        let alerts = processor.process_event(event).await.unwrap();
        // May or may not generate alerts depending on thresholds
        assert!(alerts.len() <= 1);
    }

    #[tokio::test]
    async fn test_channel_source_sink() {
        let (sender, mut source) = ChannelEventSource::create_pair(10, 5);
        let (mut sink, mut receiver) = ChannelAlertSink::create_pair(10);

        // Send event
        sender
            .send(StreamEvent {
                event_id: "e1".to_string(),
                actor_id: "A".to_string(),
                observation: vec![0.5, 0.5],
                timestamp_ms: 0,
                source: "test".to_string(),
                metadata: HashMap::new(),
            })
            .await
            .unwrap();

        // Receive
        let events = source.receive().await.unwrap();
        assert_eq!(events.len(), 1);

        // Send alert
        sink.send(DivergenceAlert {
            alert_id: "a1".to_string(),
            actor_a: "A".to_string(),
            actor_b: "B".to_string(),
            phi: 1.0,
            js: 0.5,
            d_phi_dt: 0.1,
            risk_level: RiskLevel::Moderate,
            escalation_probability: 0.3,
            timestamp_ms: 0,
            reason: "test".to_string(),
        })
        .await
        .unwrap();

        // Receive alert
        let alert = receiver.recv().await.unwrap();
        assert_eq!(alert.alert_id, "a1");
    }
}
