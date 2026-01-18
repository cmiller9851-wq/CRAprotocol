# forecast/train_predix.py
import pandas as pd
import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from sklearn.preprocessing import MinMaxScaler

def prepare_series(df, column="dqfr"):
    series = df[[column]].values.astype(float)
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(series)
    return scaled, scaler

def build_model(input_shape):
    model = Sequential([
        LSTM(64, input_shape=input_shape, return_sequences=False),
        Dense(1, activation="linear")
    ])
    model.compile(optimizer="adam", loss="mse")
    return model

def train(df_path="logs/dqfr_history.csv"):
    df = pd.read_csv(df_path, parse_dates=["timestamp"])
    series, scaler = prepare_series(df)
    # create sliding windows
    X, y = [], []
    window = 30
    for i in range(len(series)-window):
        X.append(series[i:i+window])
        y.append(series[i+window])
    X, y = np.array(X), np.array(y)
    model = build_model((window, 1))
    model.fit(X, y, epochs=30, batch_size=8, verbose=0)
    model.save("forecast/predix_model.h5")
    return scaler
