"""
Real-World Data Loaders for Nucleation Detection Validation

Loads and preprocesses data from:
1. GDELT conflict events (Goldstein scale time series)
2. Financial market data (volatility, returns)
3. Climate data (temperature anomalies)

Author: Ryan J Cardwell (Archer Phoenix)
Version: 1.0.0
"""
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import json


class DataSource(Enum):
    GDELT = "gdelt"
    FINANCIAL = "financial"
    CLIMATE = "climate"
    SYNTHETIC = "synthetic"


@dataclass
class RealWorldDataset:
    """Container for real-world time series with known transitions."""
    name: str
    source: DataSource
    time: np.ndarray  # Timestamps or indices
    values: np.ndarray  # The signal
    known_transitions: List[int]  # Indices of known regime changes
    metadata: Dict[str, Any]

    def __len__(self) -> int:
        return len(self.values)


def load_gdelt_conflicts(
    data_path: Path,
    country_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[RealWorldDataset]:
    """
    Load GDELT conflict data and identify known conflict transitions.

    GDELT data format expected (JSON):
    {
        "events": [
            {
                "date": "2023-01-15",
                "country": "SYR",
                "goldstein_scale": -7.5,
                "num_events": 145,
                "avg_tone": -3.2
            },
            ...
        ],
        "known_transitions": [
            {"date": "2023-03-01", "description": "Major escalation"},
            ...
        ]
    }
    """
    datasets = []

    if not data_path.exists():
        print(f"Warning: GDELT data not found at {data_path}")
        # Return synthetic proxy for testing
        return _generate_synthetic_gdelt()

    with open(data_path) as f:
        data = json.load(f)

    events = data.get("events", [])
    known = data.get("known_transitions", [])

    if not events:
        return datasets

    # Filter by country if specified
    if country_code:
        events = [e for e in events if e.get("country") == country_code]

    # Filter by date range
    if start_date or end_date:
        events = [
            e for e in events
            if (not start_date or e["date"] >= start_date) and
               (not end_date or e["date"] <= end_date)
        ]

    if not events:
        return datasets

    # Extract time series
    dates = [e["date"] for e in events]
    goldstein = np.array([e["goldstein_scale"] for e in events])
    num_events = np.array([e.get("num_events", 1) for e in events])

    # Find indices of known transitions
    transition_indices = []
    for trans in known:
        trans_date = trans["date"]
        try:
            idx = dates.index(trans_date)
            transition_indices.append(idx)
        except ValueError:
            # Find closest date
            for i, d in enumerate(dates):
                if d >= trans_date:
                    transition_indices.append(i)
                    break

    # Create dataset for Goldstein scale
    datasets.append(RealWorldDataset(
        name=f"gdelt_goldstein_{country_code or 'global'}",
        source=DataSource.GDELT,
        time=np.arange(len(goldstein)),
        values=goldstein,
        known_transitions=transition_indices,
        metadata={
            "country": country_code,
            "start_date": dates[0] if dates else None,
            "end_date": dates[-1] if dates else None,
            "n_events": len(events),
            "description": "GDELT Goldstein scale daily average",
        },
    ))

    # Create dataset for event intensity
    datasets.append(RealWorldDataset(
        name=f"gdelt_intensity_{country_code or 'global'}",
        source=DataSource.GDELT,
        time=np.arange(len(num_events)),
        values=num_events.astype(float),
        known_transitions=transition_indices,
        metadata={
            "country": country_code,
            "description": "GDELT daily event count",
        },
    ))

    return datasets


def _generate_synthetic_gdelt(n_series: int = 3, seed: int = 42) -> List[RealWorldDataset]:
    """Generate synthetic GDELT-like data for testing."""
    np.random.seed(seed)
    datasets = []

    for i in range(n_series):
        n_points = np.random.randint(300, 600)
        transition_point = np.random.randint(n_points // 3, 2 * n_points // 3)

        # Goldstein scale ranges from -10 to +10
        # Generate stable period then transition
        pre = np.random.normal(-2, 1.5, transition_point)
        # Before transition: variance reduction (key hypothesis)
        reduction_window = 30
        pre[-reduction_window:] = np.random.normal(-2, 0.5, reduction_window)
        # Post transition: new regime
        post = np.random.normal(-6, 2.0, n_points - transition_point)

        values = np.concatenate([pre, post])

        datasets.append(RealWorldDataset(
            name=f"synthetic_gdelt_{i}",
            source=DataSource.SYNTHETIC,
            time=np.arange(n_points),
            values=values,
            known_transitions=[transition_point],
            metadata={
                "synthetic": True,
                "description": f"Synthetic GDELT-like series {i}",
            },
        ))

    return datasets


def load_financial_data(
    data_path: Path,
    symbol: Optional[str] = None,
) -> List[RealWorldDataset]:
    """
    Load financial market data with known crash/rally transitions.

    Expected format (JSON):
    {
        "series": [
            {
                "symbol": "SPX",
                "dates": ["2020-01-02", ...],
                "prices": [3257.85, ...],
                "returns": [0.0012, ...],
                "volatility": [0.12, ...]
            }
        ],
        "known_transitions": [
            {"date": "2020-03-12", "symbol": "SPX", "type": "crash"},
            ...
        ]
    }
    """
    datasets = []

    if not data_path.exists():
        print(f"Warning: Financial data not found at {data_path}")
        return _generate_synthetic_financial()

    with open(data_path) as f:
        data = json.load(f)

    for series in data.get("series", []):
        if symbol and series["symbol"] != symbol:
            continue

        sym = series["symbol"]
        dates = series["dates"]
        prices = np.array(series.get("prices", []))
        returns = np.array(series.get("returns", []))
        volatility = np.array(series.get("volatility", []))

        # Find transitions for this symbol
        transitions = []
        for trans in data.get("known_transitions", []):
            if trans.get("symbol") == sym or not trans.get("symbol"):
                try:
                    idx = dates.index(trans["date"])
                    transitions.append(idx)
                except ValueError:
                    pass

        # Create datasets
        if len(prices) > 0:
            datasets.append(RealWorldDataset(
                name=f"financial_price_{sym}",
                source=DataSource.FINANCIAL,
                time=np.arange(len(prices)),
                values=prices,
                known_transitions=transitions,
                metadata={"symbol": sym, "type": "price"},
            ))

        if len(returns) > 0:
            datasets.append(RealWorldDataset(
                name=f"financial_returns_{sym}",
                source=DataSource.FINANCIAL,
                time=np.arange(len(returns)),
                values=returns,
                known_transitions=transitions,
                metadata={"symbol": sym, "type": "returns"},
            ))

        if len(volatility) > 0:
            datasets.append(RealWorldDataset(
                name=f"financial_volatility_{sym}",
                source=DataSource.FINANCIAL,
                time=np.arange(len(volatility)),
                values=volatility,
                known_transitions=transitions,
                metadata={"symbol": sym, "type": "volatility"},
            ))

    return datasets


def _generate_synthetic_financial(n_series: int = 2, seed: int = 123) -> List[RealWorldDataset]:
    """Generate synthetic financial data with crash patterns."""
    np.random.seed(seed)
    datasets = []

    for i in range(n_series):
        n_points = 500
        transition_point = np.random.randint(200, 350)

        # Generate log returns with regime change
        # Pre-crash: normal volatility
        pre_returns = np.random.normal(0.0005, 0.01, transition_point)
        # Variance reduction before crash (the squeeze)
        pre_returns[-20:] = np.random.normal(0.0002, 0.003, 20)
        # Crash
        post_returns = np.random.normal(-0.002, 0.025, n_points - transition_point)
        post_returns[:5] = np.random.normal(-0.05, 0.03, 5)  # Initial crash spike

        returns = np.concatenate([pre_returns, post_returns])

        # Convert to prices
        prices = 100 * np.exp(np.cumsum(returns))

        datasets.append(RealWorldDataset(
            name=f"synthetic_financial_{i}",
            source=DataSource.SYNTHETIC,
            time=np.arange(n_points),
            values=returns,
            known_transitions=[transition_point],
            metadata={
                "synthetic": True,
                "type": "returns",
                "description": f"Synthetic financial returns {i}",
            },
        ))

    return datasets


def load_climate_data(
    data_path: Path,
    region: Optional[str] = None,
) -> List[RealWorldDataset]:
    """
    Load climate data with known regime shifts.

    Expected format (JSON):
    {
        "series": [
            {
                "region": "arctic",
                "years": [1980, 1981, ...],
                "temperature_anomaly": [0.2, 0.15, ...]
            }
        ],
        "known_transitions": [
            {"year": 1998, "description": "El Nino regime shift"}
        ]
    }
    """
    datasets = []

    if not data_path.exists():
        print(f"Warning: Climate data not found at {data_path}")
        return _generate_synthetic_climate()

    with open(data_path) as f:
        data = json.load(f)

    for series in data.get("series", []):
        if region and series["region"] != region:
            continue

        reg = series["region"]
        years = series.get("years", [])
        temps = np.array(series.get("temperature_anomaly", []))

        # Find transitions
        transitions = []
        for trans in data.get("known_transitions", []):
            try:
                idx = years.index(trans["year"])
                transitions.append(idx)
            except ValueError:
                pass

        if len(temps) > 0:
            datasets.append(RealWorldDataset(
                name=f"climate_{reg}",
                source=DataSource.CLIMATE,
                time=np.array(years) if years else np.arange(len(temps)),
                values=temps,
                known_transitions=transitions,
                metadata={"region": reg, "type": "temperature_anomaly"},
            ))

    return datasets


def _generate_synthetic_climate(seed: int = 456) -> List[RealWorldDataset]:
    """Generate synthetic climate data with regime shifts."""
    np.random.seed(seed)

    n_points = 200
    transition_point = 120

    # Temperature anomalies with regime shift
    pre = np.random.normal(0.2, 0.3, transition_point)
    # Variance reduction before shift
    pre[-15:] = np.random.normal(0.25, 0.1, 15)
    # New regime
    post = np.random.normal(0.8, 0.35, n_points - transition_point)

    temps = np.concatenate([pre, post])
    # Add trend
    temps += np.linspace(0, 0.5, n_points)

    return [RealWorldDataset(
        name="synthetic_climate",
        source=DataSource.SYNTHETIC,
        time=np.arange(1900, 1900 + n_points),
        values=temps,
        known_transitions=[transition_point],
        metadata={
            "synthetic": True,
            "type": "temperature_anomaly",
            "description": "Synthetic climate series with regime shift",
        },
    )]


def prepare_dataset(
    source: DataSource,
    data_dir: Path,
    **kwargs,
) -> List[RealWorldDataset]:
    """
    Load and prepare datasets from specified source.

    Args:
        source: Which data source to load
        data_dir: Directory containing data files
        **kwargs: Additional arguments for specific loaders

    Returns:
        List of prepared datasets
    """
    loaders = {
        DataSource.GDELT: (load_gdelt_conflicts, "gdelt.json"),
        DataSource.FINANCIAL: (load_financial_data, "financial.json"),
        DataSource.CLIMATE: (load_climate_data, "climate.json"),
    }

    if source not in loaders:
        raise ValueError(f"Unknown data source: {source}")

    loader_fn, default_file = loaders[source]
    data_path = data_dir / default_file

    return loader_fn(data_path, **kwargs)


def evaluate_on_real_data(
    datasets: List[RealWorldDataset],
    detector,
    tolerance: int = 20,
) -> Dict[str, Any]:
    """
    Evaluate a detector on real-world datasets with known transitions.

    Returns:
        Dictionary with evaluation metrics
    """
    results = {
        "total_transitions": 0,
        "detected": 0,
        "false_alarms": 0,
        "detection_errors": [],
        "per_dataset": [],
    }

    for dataset in datasets:
        if len(dataset.known_transitions) == 0:
            continue

        detection = detector.detect(dataset.values)
        dataset_result = {
            "name": dataset.name,
            "n_transitions": len(dataset.known_transitions),
            "detected_indices": [],
            "true_indices": dataset.known_transitions,
            "hits": 0,
            "misses": 0,
        }

        results["total_transitions"] += len(dataset.known_transitions)

        if detection.detected and detection.detection_index is not None:
            det_idx = detection.detection_index

            # Check if detection is near any known transition
            min_error = float("inf")
            matched = False
            for true_idx in dataset.known_transitions:
                error = abs(det_idx - true_idx)
                if error < min_error:
                    min_error = error
                if error <= tolerance:
                    matched = True
                    dataset_result["hits"] += 1
                    results["detected"] += 1
                    results["detection_errors"].append(det_idx - true_idx)
                    break

            if not matched:
                results["false_alarms"] += 1

            dataset_result["detected_indices"].append(det_idx)
            dataset_result["misses"] = len(dataset.known_transitions) - dataset_result["hits"]
        else:
            dataset_result["misses"] = len(dataset.known_transitions)

        results["per_dataset"].append(dataset_result)

    # Compute summary stats
    if results["detected"] > 0:
        results["mean_error"] = float(np.mean(results["detection_errors"]))
        results["std_error"] = float(np.std(results["detection_errors"]))
    else:
        results["mean_error"] = None
        results["std_error"] = None

    results["recall"] = results["detected"] / results["total_transitions"] if results["total_transitions"] > 0 else 0

    return results


if __name__ == "__main__":
    # Test data loaders
    print("Testing real-world data loaders...")

    # Generate synthetic versions
    print("\n1. GDELT (synthetic):")
    gdelt_data = load_gdelt_conflicts(Path("nonexistent"))
    for d in gdelt_data:
        print(f"   {d.name}: {len(d.values)} points, {len(d.known_transitions)} transitions")

    print("\n2. Financial (synthetic):")
    fin_data = load_financial_data(Path("nonexistent"))
    for d in fin_data:
        print(f"   {d.name}: {len(d.values)} points, {len(d.known_transitions)} transitions")

    print("\n3. Climate (synthetic):")
    climate_data = load_climate_data(Path("nonexistent"))
    for d in climate_data:
        print(f"   {d.name}: {len(d.values)} points, {len(d.known_transitions)} transitions")

    # Test evaluation
    print("\n4. Testing detector on synthetic data:")
    from detectors.nucleation_detectors import create_detector, DetectorType

    detector = create_detector(DetectorType.VARIANCE_RATIO)
    all_data = gdelt_data + fin_data + climate_data

    results = evaluate_on_real_data(all_data, detector)
    print(f"   Total transitions: {results['total_transitions']}")
    print(f"   Detected: {results['detected']}")
    print(f"   False alarms: {results['false_alarms']}")
    print(f"   Recall: {results['recall']:.2%}")
    if results['mean_error'] is not None:
        print(f"   Mean error: {results['mean_error']:.1f} frames")
