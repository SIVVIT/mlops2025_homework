# Minimal entrypoint to run monitoring with Step 2 FastAPI service
# Usage:
#   1) Запусти FastAPI сервис из шага 2 (uvicorn ...).
#   2) В отдельном терминале запусти мониторинг:
#        python main.py --config config/monitoring_config.yaml
#
# Зависимости: requests, pyyaml, colorama (необязательно)

import argparse

from src.config import load_config
from src.monitor import run_monitor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/monitoring_config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    run_monitor(cfg)


if __name__ == "__main__":
    main()
