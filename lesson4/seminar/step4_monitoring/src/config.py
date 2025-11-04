from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ServiceCfg:
    host: str
    port: int
    base_url: str


@dataclass
class MonitoringCfg:
    check_interval_seconds: int
    samples_per_check: int
    request_timeout_seconds: int


@dataclass
class ThresholdsCfg:
    response_time_warning: int
    response_time_critical: int
    p95_warning: int
    p95_critical: int
    error_rate_warning: float
    error_rate_critical: float
    consecutive_failures_warning: int
    consecutive_failures_critical: int


@dataclass
class AlertsCfg:
    enabled: bool
    cooldown_minutes: int


@dataclass
class LoggingCfg:
    console_colors: bool
    log_file: str
    metrics_file: str


@dataclass
class TestingCfg:
    sample_image_path: str | None = None
    form_field: str = "file"


@dataclass
class AppConfig:
    service: ServiceCfg
    monitoring: MonitoringCfg
    thresholds: ThresholdsCfg
    alerts: AlertsCfg
    logging: LoggingCfg
    testing: TestingCfg | None = None


def load_config(path: str) -> AppConfig:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    th = data["thresholds"]
    testing = data.get("testing") or {}
    return AppConfig(
        service=ServiceCfg(**data["service"]),
        monitoring=MonitoringCfg(**data["monitoring"]),
        thresholds=ThresholdsCfg(
            response_time_warning=th["response_time_ms"]["warning"],
            response_time_critical=th["response_time_ms"]["critical"],
            p95_warning=th["p95_latency_ms"]["warning"],
            p95_critical=th["p95_latency_ms"]["critical"],
            error_rate_warning=float(th["error_rate_percent"]["warning"]),
            error_rate_critical=float(th["error_rate_percent"]["critical"]),
            consecutive_failures_warning=th["consecutive_failures"]["warning"],
            consecutive_failures_critical=th["consecutive_failures"]["critical"],
        ),
        alerts=AlertsCfg(**data["alerts"]),
        logging=LoggingCfg(**data["logging"]),
        testing=TestingCfg(
            sample_image_path=testing.get("sample_image_path"),
            form_field=testing.get("form_field", "file"),
        ),
    )
