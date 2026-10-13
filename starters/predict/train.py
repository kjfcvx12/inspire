"""CSV -> 예측 모델 스타터. 사용: python train.py data.csv target_col"""
import sys
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

path, target = sys.argv[1], sys.argv[2]
df = pd.read_csv(path).dropna(subset=[target])
X, y = df.drop(columns=[target]), df[target]
num = X.select_dtypes("number").columns
cat = X.columns.difference(num)
pre = ColumnTransformer([
    ("num", SimpleImputer(strategy="median"), num),
    ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                      ("oh", OneHotEncoder(handle_unknown="ignore"))]), cat),
])
is_cls = y.dtype == object or y.nunique() < 10
model = RandomForestClassifier(300, random_state=0) if is_cls else RandomForestRegressor(300, random_state=0)
pipe = Pipeline([("pre", pre), ("m", model)])
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=0)
pipe.fit(Xtr, ytr)
pred = pipe.predict(Xte)
print(classification_report(yte, pred) if is_cls else f"R2: {r2_score(yte, pred):.3f}")
