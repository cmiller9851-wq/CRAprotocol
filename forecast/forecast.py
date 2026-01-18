# forecast/forecast.py
import pandas as pd, numpy as np, joblib
from tensorflow.keras.models import load_model
from sklearn.preprocessing import MinMaxScaler

model = load_model("forecast/predix_model.h5")
scaler = joblib.load("forecast/scaler.pkl")

def forecast_next(df):
    series = scaler.transform(df[["dqfr"]].values)
    window = series[-30:]  # last 30 days
    pred = model.predict(window.reshape(1,30,1))
    return scaler.inverse_transform(pred)[0,0]

df = pd.read_csv("logs/dqfr_history.csv")
next_dqfr = forecast_next(df)
if next_dqfr < 0.95:
    # trigger alert / rollback
    print("⚠️ Forecasted DQFR below threshold")
