import json
import os
import pickle

import pandas as pd
import yaml
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


def load_params():
    with open("params.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def evaluate_model():
    params = load_params()

    # модель
    with open("models/model.pkl", "rb") as f:
        model = pickle.load(f)

    # данные
    data_path = "data/processed/dataset.csv"
    df = pd.read_csv(data_path)

    # фичи/цель
    X = df[["total_bill", "size"]]
    y = df["high_tip"]

    # как и раньше — используем test_size/seed из params.yaml
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=params["test_size"], random_state=params["seed"]
    )

    # метрики
    y_pred = model.predict(X_test)
    accuracy = float(accuracy_score(y_test, y_pred))
    n_rows = int(len(df))

    # вывод в консоль как прежде
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Rows: {n_rows}")

    # запись в metrics/metrics.json
    os.makedirs("metrics", exist_ok=True)
    metrics_path = os.path.join("metrics", "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(
            {"accuracy": accuracy, "rows": n_rows}, f, ensure_ascii=False, indent=2
        )

    print(f"Saved metrics to {metrics_path}")


if __name__ == "__main__":
    evaluate_model()
