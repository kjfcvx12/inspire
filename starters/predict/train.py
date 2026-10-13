"""CSV -> 예측 모델 스타터. 사용: python train.py data.csv target_col
평가 가능한 함수 fit_and_score()를 두어 골든셋 평가(scripts/eval.py --target train.py:fit_and_score)에 쓴다."""
import sys

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


def fit_and_score(path: str, target: str, seed: int = 0) -> dict:
    df = pd.read_csv(path)
    if target not in df.columns:
        raise ValueError(f"타깃 열 '{target}'이 없습니다. 열 목록: {list(df.columns)}")
    df = df.dropna(subset=[target])
    if len(df) < 10:
        raise ValueError(f"학습할 행이 너무 적습니다({len(df)}행)")
    X, y = df.drop(columns=[target]), df[target]
    num = X.select_dtypes("number").columns
    cat = X.columns.difference(num)
    pre = ColumnTransformer([
        ("num", SimpleImputer(strategy="median"), num),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore"))]), cat),
    ])
    is_cls = y.dtype == object or y.nunique() < 10
    model = RandomForestClassifier(300, random_state=seed) if is_cls else RandomForestRegressor(300, random_state=seed)
    pipe = Pipeline([("pre", pre), ("m", model)])
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=seed)
    pipe.fit(Xtr, ytr)
    pred = pipe.predict(Xte)
    if is_cls:
        return {"task": "classification", "metric": "accuracy", "score": float(accuracy_score(yte, pred)),
                "n_train": len(Xtr), "n_test": len(Xte), "report": classification_report(yte, pred)}
    return {"task": "regression", "metric": "r2", "score": float(r2_score(yte, pred)),
            "n_train": len(Xtr), "n_test": len(Xte), "report": f"R2: {r2_score(yte, pred):.3f}"}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("사용: python train.py data.csv target_col")
    try:
        print(fit_and_score(sys.argv[1], sys.argv[2])["report"])
    except (ValueError, OSError) as e:
        raise SystemExit(f"오류: {e}")
