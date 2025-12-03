"""
Rate Limit Monitoring Component
Tracks API usage, errors, retries and calculates risk levels
"""

import csv
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from collections import defaultdict
import threading
from pathlib import Path
from .logging import log_debug, log_info, log_warning, log_error


class RateLimitMonitor:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        self.csv_file = self.log_dir / "api_usage.csv"
        self.event_log = self.log_dir / "events.log"
        
        # Initialize CSV if not exists
        if not self.csv_file.exists():
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'api', 'endpoint', 'status', 'retry_count'])
        
        # Log service start
        self.log_event("SERVICE_START", "Service started")
    
    def log_request(self, api: str, endpoint: str, status: str = 'success', retry_count: int = 0):
        """Log an API request"""
        timestamp = datetime.now().isoformat()
        
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, api, endpoint, status, retry_count])
    
    def log_event(self, event_type: str, message: str):
        """Log a system event"""
        timestamp = datetime.now().isoformat()
        
        with open(self.event_log, 'a') as f:
            f.write(f"[{timestamp}] {event_type}: {message}\n")
    
    def get_stats(self, time_range: str = '10min') -> Dict:
        """
        Get statistics for a time range
        time_range: '10min', '1hour', '1day', '1week', '1month', '1year'
        """
        now = datetime.now()
        
        # Define time ranges
        ranges = {
            '10min': timedelta(minutes=10),
            '1hour': timedelta(hours=1),
            '1day': timedelta(days=1),
            '1week': timedelta(weeks=1),
            '1month': timedelta(days=30),
            '1year': timedelta(days=365)
        }
        
        cutoff = now - ranges.get(time_range, timedelta(minutes=10))
        
        # Read CSV and filter by time
        requests = []
        errors = []
        retries = []
        
        if self.csv_file.exists():
            with open(self.csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ts = datetime.fromisoformat(row['timestamp'])
                        if ts >= cutoff:
                            requests.append(row)
                            if row['status'] == 'error':
                                errors.append(row)
                            if int(row['retry_count']) > 0:
                                retries.append(row)
                    except Exception as e:
                        from retrieval_service.infrastructure.logging import log_error
                        log_error(f"Error parsing monitoring row: {e}")
                        continue
        
        # Calculate stats by API
        api_stats = defaultdict(lambda: {'total': 0, 'errors': 0, 'retries': 0})
        
        for req in requests:
            api = req['api']
            api_stats[api]['total'] += 1
            if req['status'] == 'error':
                api_stats[api]['errors'] += 1
            if int(req['retry_count']) > 0:
                api_stats[api]['retries'] += int(req['retry_count'])
        
        return {
            'time_range': time_range,
            'total_requests': len(requests),
            'total_errors': len(errors),
            'total_retries': sum(int(r['retry_count']) for r in retries),
            'api_breakdown': dict(api_stats),
            'requests': requests,
            'errors': errors,
            'retries': retries
        }
    
    def get_timeline_data(self, time_range: str = '1hour', buckets: int = 20) -> List[Dict]:
        """
        Get timeline data for graphing
        Returns list of time buckets with counts
        """
        now = datetime.now()
        
        ranges = {
            '10min': timedelta(minutes=10),
            '1hour': timedelta(hours=1),
            '1day': timedelta(days=1),
            '1week': timedelta(weeks=1),
            '1month': timedelta(days=30),
            '1year': timedelta(days=365)
        }
        
        total_duration = ranges.get(time_range, timedelta(hours=1))
        cutoff = now - total_duration
        bucket_size = total_duration / buckets
        
        # Initialize buckets
        timeline = []
        for i in range(buckets):
            bucket_start = cutoff + (bucket_size * i)
            timeline.append({
                'timestamp': bucket_start.isoformat(),
                'requests': 0,
                'errors': 0,
                'retries': 0
            })
        
        # Read and categorize requests
        if self.csv_file.exists():
            with open(self.csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ts = datetime.fromisoformat(row['timestamp'])
                        if ts >= cutoff:
                            # Find which bucket this belongs to
                            bucket_idx = int((ts - cutoff) / bucket_size)
                            if 0 <= bucket_idx < buckets:
                                timeline[bucket_idx]['requests'] += 1
                                if row['status'] == 'error':
                                    timeline[bucket_idx]['errors'] += 1
                                if int(row['retry_count']) > 0:
                                    timeline[bucket_idx]['retries'] += int(row['retry_count'])
                    except Exception as e:
                        from retrieval_service.infrastructure.logging import log_error
                        log_error(f"Error parsing timeline row: {e}")
                        continue
        
        return timeline
    
    def calculate_risk_level(self) -> Tuple[int, str]:
        """
        Calculate risk level (0-100) based on recent activity
        Returns: (risk_level, reason)
        """
        # Get stats for different time ranges
        stats_10min = self.get_stats('10min')
        stats_1hour = self.get_stats('1hour')
        
        risk = 0
        reasons = []
        
        # Factor 1: Error rate (0-40 points)
        if stats_10min['total_requests'] > 0:
            error_rate = stats_10min['total_errors'] / stats_10min['total_requests']
            error_risk = min(40, int(error_rate * 100))
            risk += error_risk
            if error_risk > 10:
                reasons.append(f"High error rate: {error_rate*100:.1f}%")
        
        # Factor 2: Retry rate (0-30 points)
        if stats_10min['total_requests'] > 0:
            retry_rate = stats_10min['total_retries'] / stats_10min['total_requests']
            retry_risk = min(30, int(retry_rate * 60))
            risk += retry_risk
            if retry_risk > 10:
                reasons.append(f"High retry rate: {retry_rate*100:.1f}%")
        
        # Factor 3: Request volume (0-30 points)
        # Assume rate limits: OpenAI ~3500/min, Google ~10000/min
        openai_requests = stats_10min['api_breakdown'].get('openai', {}).get('total', 0)
        google_requests = stats_10min['api_breakdown'].get('google', {}).get('total', 0)
        
        # OpenAI: 3500/min = 583/10min
        if openai_requests > 400:
            volume_risk = min(15, int((openai_requests / 583) * 15))
            risk += volume_risk
            if volume_risk > 5:
                reasons.append(f"High OpenAI volume: {openai_requests}/10min")
        
        # Google: 10000/min = 1666/10min
        if google_requests > 1000:
            volume_risk = min(15, int((google_requests / 1666) * 15))
            risk += volume_risk
            if volume_risk > 5:
                reasons.append(f"High Google volume: {google_requests}/10min")
        
        risk = min(100, risk)
        reason = "; ".join(reasons) if reasons else "Normal operation"
        
        return risk, reason


# Global instance
monitor = RateLimitMonitor()
