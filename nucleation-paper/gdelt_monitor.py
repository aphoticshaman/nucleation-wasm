#!/usr/bin/env python3
"""
GDELT Nucleation Monitor
Real-time conflict early warning using variance inflection detection.

Fetches actual GDELT data and identifies regions showing "calm before storm" patterns.

Usage:
    python gdelt_monitor.py                    # Last 30 days, top alerts
    python gdelt_monitor.py --days 60          # Custom lookback
    python gdelt_monitor.py --country SYR      # Focus on specific country
    python gdelt_monitor.py --historical 2022-02-01  # Backtest (e.g., Ukraine invasion)

Author: Ryan J Cardwell (Archer Phoenix)
"""
import argparse
import urllib.request
import zipfile
import io
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import numpy as np

# GDELT column indices (v2.0 format)
GDELT_COLS = {
    'date': 1,           # SQLDATE (YYYYMMDD)
    'actor1_country': 7, # Actor1CountryCode
    'actor2_country': 17,# Actor2CountryCode
    'goldstein': 30,     # GoldsteinScale (-10 to +10)
    'num_mentions': 31,  # NumMentions
    'num_sources': 32,   # NumSources
    'avg_tone': 34,      # AvgTone
}


def fetch_gdelt_day(date: datetime, cache_dir: Path) -> Optional[List[dict]]:
    """
    Fetch GDELT events for a single day.

    Downloads from: http://data.gdeltproject.org/events/YYYYMMDD.export.CSV.zip
    """
    date_str = date.strftime("%Y%m%d")
    cache_file = cache_dir / f"{date_str}.csv"

    # Check cache first
    if cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8', errors='ignore') as f:
            return parse_gdelt_csv(f.read())

    # Download
    url = f"http://data.gdeltproject.org/events/{date_str}.export.CSV.zip"

    try:
        print(f"  Fetching {date_str}...", end=" ", flush=True)
        with urllib.request.urlopen(url, timeout=30) as response:
            zip_data = response.read()

        # Extract CSV from zip
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            csv_name = zf.namelist()[0]
            csv_data = zf.read(csv_name).decode('utf-8', errors='ignore')

        # Cache it
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(csv_data)

        events = parse_gdelt_csv(csv_data)
        print(f"{len(events)} events")
        return events

    except Exception as e:
        print(f"failed ({e})")
        return None


def parse_gdelt_csv(csv_data: str) -> List[dict]:
    """Parse GDELT CSV into list of event dicts."""
    events = []

    for line in csv_data.strip().split('\n'):
        fields = line.split('\t')

        if len(fields) < 35:
            continue

        try:
            goldstein = float(fields[GDELT_COLS['goldstein']]) if fields[GDELT_COLS['goldstein']] else None

            if goldstein is None:
                continue

            event = {
                'date': fields[GDELT_COLS['date']],
                'actor1_country': fields[GDELT_COLS['actor1_country']][:3] if fields[GDELT_COLS['actor1_country']] else None,
                'actor2_country': fields[GDELT_COLS['actor2_country']][:3] if fields[GDELT_COLS['actor2_country']] else None,
                'goldstein': goldstein,
                'num_mentions': int(fields[GDELT_COLS['num_mentions']]) if fields[GDELT_COLS['num_mentions']] else 1,
                'avg_tone': float(fields[GDELT_COLS['avg_tone']]) if fields[GDELT_COLS['avg_tone']] else 0,
            }
            events.append(event)

        except (ValueError, IndexError):
            continue

    return events


def aggregate_by_country(events: List[dict]) -> Dict[str, Dict[str, List[float]]]:
    """
    Aggregate events by country and date.

    Returns: {country: {date: [goldstein_scores]}}
    """
    aggregated = {}

    for event in events:
        # Use both actor countries
        countries = [event['actor1_country'], event['actor2_country']]

        for country in countries:
            if not country or len(country) < 2:
                continue

            if country not in aggregated:
                aggregated[country] = {}

            date = event['date']
            if date not in aggregated[country]:
                aggregated[country][date] = []

            aggregated[country][date].append(event['goldstein'])

    return aggregated


def compute_daily_stats(country_data: Dict[str, List[float]], dates: List[str]) -> dict:
    """
    Compute daily statistics for a country.

    Returns dict with arrays: mean_goldstein, variance, event_count
    """
    n = len(dates)
    mean_goldstein = np.full(n, np.nan)
    variance = np.full(n, np.nan)
    event_count = np.zeros(n)

    for i, date in enumerate(dates):
        if date in country_data:
            scores = country_data[date]
            if len(scores) >= 3:  # Minimum events for meaningful stats
                mean_goldstein[i] = np.mean(scores)
                variance[i] = np.var(scores)
                event_count[i] = len(scores)

    return {
        'mean_goldstein': mean_goldstein,
        'variance': variance,
        'event_count': event_count,
    }


def detect_nucleation(variance_series: np.ndarray, window: int = 7) -> dict:
    """
    Apply variance inflection detector to a time series.

    Returns detection result with:
    - detected: bool
    - index: where nucleation detected
    - score: strength of signal
    - direction: 'reducing' or 'increasing'
    """
    n = len(variance_series)

    if n < window * 3:
        return {'detected': False, 'reason': 'insufficient_data'}

    # Fill NaN with interpolation for smoothing
    valid = ~np.isnan(variance_series)
    if np.sum(valid) < window:
        return {'detected': False, 'reason': 'too_sparse'}

    # Simple interpolation
    filled = variance_series.copy()
    for i in range(n):
        if np.isnan(filled[i]):
            # Find nearest valid values
            left = right = None
            for j in range(i-1, -1, -1):
                if not np.isnan(filled[j]):
                    left = filled[j]
                    break
            for j in range(i+1, n):
                if not np.isnan(filled[j]):
                    right = filled[j]
                    break
            if left is not None and right is not None:
                filled[i] = (left + right) / 2
            elif left is not None:
                filled[i] = left
            elif right is not None:
                filled[i] = right

    # Smooth
    kernel = np.ones(window) / window
    smoothed = np.convolve(filled, kernel, mode='same')

    # Second derivative (inflection)
    d1 = np.gradient(smoothed)
    d2 = np.gradient(d1)

    # Find max inflection in recent data (last 30%)
    recent_start = int(n * 0.7)
    recent_d2 = np.abs(d2[recent_start:])

    if len(recent_d2) == 0:
        return {'detected': False, 'reason': 'no_recent_data'}

    peak_local = np.argmax(recent_d2)
    peak_global = recent_start + peak_local
    peak_value = recent_d2[peak_local]

    # Compare to historical baseline
    baseline_d2 = np.abs(d2[:recent_start])
    if len(baseline_d2) > 0:
        baseline_mean = np.mean(baseline_d2)
        baseline_std = np.std(baseline_d2)
    else:
        baseline_mean = peak_value
        baseline_std = 1

    if baseline_std < 1e-10:
        baseline_std = 1

    z_score = (peak_value - baseline_mean) / baseline_std

    # Determine direction of change
    if peak_global > 0 and peak_global < n - 1:
        direction = 'reducing' if d1[peak_global] < 0 else 'increasing'
    else:
        direction = 'unknown'

    # Detection threshold
    detected = z_score > 1.5  # 1.5 std devs above normal

    return {
        'detected': detected,
        'index': peak_global,
        'z_score': float(z_score),
        'direction': direction,
        'recent_variance_trend': float(np.mean(d1[recent_start:])) if len(d1[recent_start:]) > 0 else 0,
    }


def analyze_countries(
    all_events: List[dict],
    dates: List[str],
    min_events: int = 50,
) -> List[dict]:
    """
    Analyze all countries and return nucleation alerts.
    """
    # Aggregate by country
    by_country = aggregate_by_country(all_events)

    alerts = []

    for country, country_data in by_country.items():
        # Compute daily stats
        stats = compute_daily_stats(country_data, dates)

        # Skip countries with too few events
        total_events = np.nansum(stats['event_count'])
        if total_events < min_events:
            continue

        # Run nucleation detector on variance
        result = detect_nucleation(stats['variance'])

        if result.get('detected'):
            # Compute additional context
            recent_goldstein = stats['mean_goldstein'][-7:]
            recent_goldstein = recent_goldstein[~np.isnan(recent_goldstein)]

            alerts.append({
                'country': country,
                'z_score': result['z_score'],
                'direction': result['direction'],
                'days_ago': len(dates) - result['index'] - 1,
                'recent_mean_goldstein': float(np.mean(recent_goldstein)) if len(recent_goldstein) > 0 else None,
                'total_events': int(total_events),
                'variance_trend': result['recent_variance_trend'],
            })

    # Sort by z-score (strongest signal first)
    alerts.sort(key=lambda x: x['z_score'], reverse=True)

    return alerts


# Country code to name mapping (subset)
COUNTRY_NAMES = {
    'USA': 'United States', 'RUS': 'Russia', 'CHN': 'China', 'UKR': 'Ukraine',
    'ISR': 'Israel', 'IRN': 'Iran', 'SYR': 'Syria', 'IRQ': 'Iraq',
    'AFG': 'Afghanistan', 'PAK': 'Pakistan', 'IND': 'India', 'GBR': 'United Kingdom',
    'FRA': 'France', 'DEU': 'Germany', 'TUR': 'Turkey', 'SAU': 'Saudi Arabia',
    'EGY': 'Egypt', 'NGA': 'Nigeria', 'ZAF': 'South Africa', 'BRA': 'Brazil',
    'MEX': 'Mexico', 'JPN': 'Japan', 'KOR': 'South Korea', 'PRK': 'North Korea',
    'TWN': 'Taiwan', 'PSE': 'Palestine', 'LBN': 'Lebanon', 'YEM': 'Yemen',
    'SDN': 'Sudan', 'SSD': 'South Sudan', 'ETH': 'Ethiopia', 'SOM': 'Somalia',
    'LBY': 'Libya', 'VEN': 'Venezuela', 'COL': 'Colombia', 'MMR': 'Myanmar',
}


def print_alerts(alerts: List[dict], dates: List[str], top_n: int = 15):
    """Print formatted alert report."""
    print("\n" + "=" * 70)
    print("GDELT NUCLEATION MONITOR - CONFLICT EARLY WARNING")
    print("=" * 70)
    print(f"Analysis period: {dates[0]} to {dates[-1]} ({len(dates)} days)")
    print(f"Showing top {min(top_n, len(alerts))} alerts by signal strength")
    print("-" * 70)

    if not alerts:
        print("\nNo nucleation signals detected in this period.")
        print("This could mean: stable conditions, or insufficient data.")
        return

    print(f"\n{'Country':<25} {'Signal':>8} {'Direction':>12} {'Days Ago':>10} {'Goldstein':>10}")
    print("-" * 70)

    for alert in alerts[:top_n]:
        country_code = alert['country']
        country_name = COUNTRY_NAMES.get(country_code, country_code)

        # Truncate long names
        if len(country_name) > 23:
            country_name = country_name[:20] + "..."

        z = alert['z_score']
        direction = alert['direction']
        days_ago = alert['days_ago']
        goldstein = alert['recent_mean_goldstein']

        # Color-code interpretation
        if direction == 'reducing':
            interp = "↓ CALM"  # Variance reducing = "calm before storm"
        else:
            interp = "↑ RISING"

        goldstein_str = f"{goldstein:+.1f}" if goldstein is not None else "N/A"

        print(f"{country_name:<25} {z:>8.2f} {interp:>12} {days_ago:>10} {goldstein_str:>10}")

    print("-" * 70)
    print("\nInterpretation:")
    print("  Signal: Z-score of variance inflection (higher = stronger anomaly)")
    print("  ↓ CALM: Variance reducing - possible 'calm before storm'")
    print("  ↑ RISING: Variance increasing - active destabilization")
    print("  Goldstein: Average conflict intensity (-10=hostile, +10=cooperative)")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="GDELT Nucleation Monitor")
    parser.add_argument("--days", type=int, default=30, help="Days to analyze")
    parser.add_argument("--country", type=str, help="Focus on specific country code")
    parser.add_argument("--historical", type=str, help="Historical date to center analysis (YYYY-MM-DD)")
    parser.add_argument("--cache-dir", type=str, default=".gdelt_cache", help="Cache directory")
    parser.add_argument("--top", type=int, default=15, help="Number of top alerts to show")

    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)

    # Determine date range
    if args.historical:
        center_date = datetime.strptime(args.historical, "%Y-%m-%d")
        start_date = center_date - timedelta(days=args.days // 2)
        end_date = center_date + timedelta(days=args.days // 2)
    else:
        end_date = datetime.now() - timedelta(days=1)  # Yesterday (today's data may be incomplete)
        start_date = end_date - timedelta(days=args.days)

    print(f"GDELT Nucleation Monitor")
    print(f"Fetching data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")

    # Fetch data for each day
    all_events = []
    dates = []

    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y%m%d")
        dates.append(date_str)

        events = fetch_gdelt_day(current, cache_dir)
        if events:
            all_events.extend(events)

        current += timedelta(days=1)

    print(f"\nTotal events fetched: {len(all_events):,}")

    if len(all_events) == 0:
        print("No events found. Check your internet connection or date range.")
        return

    # Filter by country if specified
    if args.country:
        all_events = [e for e in all_events
                     if e['actor1_country'] == args.country or e['actor2_country'] == args.country]
        print(f"Filtered to {len(all_events):,} events involving {args.country}")

    # Analyze
    print("\nAnalyzing variance patterns...")
    alerts = analyze_countries(all_events, dates)

    # Output
    print_alerts(alerts, dates, top_n=args.top)


if __name__ == "__main__":
    main()
