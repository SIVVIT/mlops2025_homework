# src/validate_model.py
from __future__ import annotations

import argparse
import json
import os
import sys

import joblib
import pandas as pd
import yaml
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


def load_params(params_path: str) -> dict:
    with open(params_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_metrics(metrics_path: str) -> dict | None:
    if not os.path.exists(metrics_path):
        return None
    with open(metrics_path, "r", encoding="utf-8") as f:
        return json.load(f)


def recompute_accuracy(model_path: str, data_path: str, params: dict) -> float:
    # загрузка
    model = joblib.load(model_path)
    df = pd.read_csv(data_path)

    target_col = "high_tip"
    feature_cols = ["total_bill", "size"]

    for col in feature_cols + [target_col]:
        if col not in df.columns:
            raise ValueError(f"Ожидалась колонка '{col}' в {data_path}")

    X = df[feature_cols]
    y = df[target_col]

    # та же логика, что и в evaluate.py
    test_size = params.get("test_size", 0.2)
    seed = params.get("seed", 42)

    _, X_test, _, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed
    )
    y_pred = model.predict(X_test)
    return float(accuracy_score(y_test, y_pred))


def main():
    parser = argparse.ArgumentParser(
        description="Validate model quality against accuracy_min from params.yaml"
    )
    parser.add_argument("--model", default="models/model.pkl", help="Путь к модели")
    parser.add_argument(
        "--data", default="data/processed/dataset.csv", help="Путь к датасету"
    )
    parser.add_argument(
        "--metrics", default="metrics/metrics.json", help="Путь к метрикам"
    )
    parser.add_argument("--params", default="params.yaml", help="Путь к params.yaml")
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="Игнорировать metrics.json и пересчитать accuracy",
    )
    args = parser.parse_args()

    params = load_params(args.params)
    thr = float(params.get("accuracy_min", 0.0))

    # получаем accuracy
    acc: float
    if args.recompute:
        acc = recompute_accuracy(args.model, args.data, params)
        print(f"[validate] recompute accuracy: {acc:.6f}")
    else:
        m = read_metrics(args.metrics)
        if m is not None and "accuracy" in m:
            acc = float(m["accuracy"])
            print(f"[validate] read accuracy from {args.metrics}: {acc:.6f}")
        else:
            print("[validate] metrics not found → recompute accuracy")
            acc = recompute_accuracy(args.model, args.data, params)
            print(f"[validate] recompute accuracy: {acc:.6f}")

    print(f"[validate] accuracy_min threshold from {args.params}: {thr:.6f}")
    ok = acc >= thr
    print(f"[validate] pass: {ok}")

    # код выхода
    if not ok:
        # явный вывод — полезно для CI/DVC логов
        print(
            f"[validate] FAILED: accuracy {acc:.6f} < accuracy_min {thr:.6f}",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
