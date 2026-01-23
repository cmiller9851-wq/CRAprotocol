import time
import functools
import json

# --- CRA PROTOCOL: OBSERVABILITY LAYER ---
# [span_4](start_span)Stack: Prometheus + Grafana[span_4](end_span)
# [span_5](start_span)Target SLO: <250ms average response time[span_5](end_span)

def monitor_latency(func):
    """Decorator to track execution time against SLOs."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration_ms = (time.time() - start_time) * 1000
        
        # Log to 'Loki' (Standard Output for Pythonista)
        status = "PASS" if duration_ms < 250 else "FAIL"
        print(f"[METRIC] Latency: {duration_ms:.2f}ms | SLO: 250ms | Status: {status}")
        
        # Append telemetry to the result for 'Grafana' ingestion
        if isinstance(result, dict):
            result['telemetry'] = {
                "latency_ms": round(duration_ms, 2),
                "slo_compliant": duration_ms < 250
            }
        return result
    wrapper.monitor = True
    return wrapper

# Example usage integrating with the existing canonize module
# [span_6](start_span)This ensures every motif submitted is measured for compliance[span_6](end_span)
