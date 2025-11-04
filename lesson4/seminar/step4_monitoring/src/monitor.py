import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from .config import AppConfig
from .logger import JsonLogger

# tiny 1x1 PNG (white), to avoid external deps
_ONEPX_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0cIDAT\x08\x1d\x01\x01\x00\xfe\xff\x00\xff\xff\xff\xff\xa0\x8d\xf7\xde\x00\x00\x00\x00IEND\xaeB`\x82"
)


def p95(latencies_ms: List[float]) -> float:
    if not latencies_ms:
        return 0.0
    data = sorted(latencies_ms)
    k = int(round(0.95 * (len(data) - 1)))
    return float(data[k])


def classify_status(
    cfg: AppConfig, resp_times: List[float], error_rate: float, consec_failures: int
) -> Tuple[str, str]:
    # Returns (color_level, reason)
    p95_val = p95(resp_times)
    if consec_failures >= cfg.thresholds.consecutive_failures_critical:
        return ("RED", f"consecutive_failures={consec_failures} >= critical")
    if error_rate >= cfg.thresholds.error_rate_critical:
        return ("RED", f"error_rate={error_rate:.1f}% >= critical")
    if resp_times and max(resp_times) >= cfg.thresholds.response_time_critical:
        return ("RED", f"response_time_max={max(resp_times):.0f}ms >= critical")
    if p95_val >= cfg.thresholds.p95_critical:
        return ("RED", f"p95={p95_val:.0f}ms >= critical")

    # warnings
    if consec_failures >= cfg.thresholds.consecutive_failures_warning:
        return ("YELLOW", f"consecutive_failures={consec_failures} >= warning")
    if error_rate >= cfg.thresholds.error_rate_warning:
        return ("YELLOW", f"error_rate={error_rate:.1f}% >= warning")
    if resp_times and max(resp_times) >= cfg.thresholds.response_time_warning:
        return ("YELLOW", f"response_time_max={max(resp_times):.0f}ms >= warning")
    if p95_val >= cfg.thresholds.p95_warning:
        return ("YELLOW", f"p95={p95_val:.0f}ms >= warning")
    return ("GREEN", "within thresholds")


def write_metrics(metrics_path: str, payload: Dict):
    p = Path(metrics_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def check_health(base_url: str, timeout: int) -> Tuple[bool, float, Optional[Dict]]:
    url = f"{base_url}/health"
    t0 = time.perf_counter()
    try:
        r = requests.get(url, timeout=timeout)
        dt = (time.perf_counter() - t0) * 1000.0
        ok = r.ok
        body = None
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text[:200]}
        return ok, dt, body
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000.0
        return False, dt, {"error": str(e)}


def check_predict(base_url: str, timeout: int, cfg: AppConfig):
    url = f"{base_url}/predict"
    t0 = time.perf_counter()
    try:
        if cfg.testing and cfg.testing.sample_image_path:
            path = cfg.testing.sample_image_path
            field = cfg.testing.form_field or "file"
            mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
            with open(path, "rb") as fp:
                files = {field: (os.path.basename(path), fp, mime)}
                r = requests.post(url, files=files, timeout=timeout)
        else:
            files = {"file": ("1x1.png", _ONEPX_PNG, "image/png")}
            r = requests.post(url, files=files, timeout=timeout)

        dt = (time.perf_counter() - t0) * 1000.0
        ok = r.ok
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text[:200]}
        return ok, dt, body

    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000.0
        return False, dt, {"error": str(e)}


def run_monitor(cfg: AppConfig):
    logger = JsonLogger(cfg.logging.log_file, console_colors=cfg.logging.console_colors)
    consecutive_failures = 0
    last_alert_ts = 0.0
    cooldown = cfg.alerts.cooldown_minutes * 60.0 if cfg.alerts.enabled else None
    base_url = cfg.service.base_url

    logger.info("monitor started", base_url=base_url)

    while True:
        latencies = []
        errors = 0
        samples = cfg.monitoring.samples_per_check

        for i in range(samples):
            ok_h, dt_h, body_h = check_health(
                base_url, cfg.monitoring.request_timeout_seconds
            )
            latencies.append(dt_h)
            logger.info("/health", ok=ok_h, latency_ms=round(dt_h, 2), body=body_h)
            if not ok_h:
                errors += 1
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            ok_p, dt_p, body_p = check_predict(
                base_url, cfg.monitoring.request_timeout_seconds, cfg
            )
            latencies.append(dt_p)
            logger.info("/predict", ok=ok_p, latency_ms=round(dt_p, 2), body=body_p)
            if not ok_p:
                errors += 1
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            time.sleep(0.1)  # short pause inside the sampling loop

        err_rate = 100.0 * errors / max(1, 2 * samples)
        p95_val = p95(latencies)

        color, reason = classify_status(cfg, latencies, err_rate, consecutive_failures)

        metrics_payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "response_time_ms_max": max(latencies) if latencies else 0,
            "response_time_ms_avg": sum(latencies) / len(latencies) if latencies else 0,
            "p95_latency_ms": p95_val,
            "error_rate_percent": err_rate,
            "consecutive_failures": consecutive_failures,
            "status": color,
            "reason": reason,
        }
        write_metrics(cfg.logging.metrics_file, metrics_payload)

        if color == "RED" or color == "YELLOW":
            now = time.time()
            if (cooldown is None) or (now - last_alert_ts >= cooldown):
                if color == "RED":
                    logger.error("ALERT", **metrics_payload)
                else:
                    logger.warn("ALERT", **metrics_payload)
                last_alert_ts = now
        else:
            logger.info("OK", **metrics_payload)

        time.sleep(cfg.monitoring.check_interval_seconds)
