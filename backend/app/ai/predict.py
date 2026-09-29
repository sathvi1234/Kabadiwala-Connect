import math
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Material, PriceFeed


def _libs():
    import numpy as np
    from sklearn.linear_model import LinearRegression

    return np, LinearRegression


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _std(values: list[float]) -> float:
    mu = _mean(values)
    return (sum((value - mu) ** 2 for value in values) / len(values)) ** 0.5


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    rank = (len(ordered) - 1) * pct / 100
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def forecast(db: Session, material: Material, city: str) -> dict:
    q = db.query(PriceFeed).filter(PriceFeed.material_id == material.id)
    if city:
        rows = q.filter(PriceFeed.market == city).order_by(PriceFeed.recorded_on.asc()).all()
        if len(rows) < 14:
            rows = q.order_by(PriceFeed.recorded_on.asc()).all()
    else:
        rows = q.order_by(PriceFeed.recorded_on.asc()).all()
    if len(rows) < 7:
        return {"direction": "stable", "confidence": 0.2, "forecast": [], "provider": "insufficient_data"}
    dates = [r.recorded_on for r in rows]
    prices = [float(r.price_per_kg) for r in rows]
    origin = dates[0]
    try:
        np, LinearRegression = _libs()
        y = np.array(prices, dtype=float)
        t = np.array([(d - origin).days for d in dates], dtype=float)
        doy = np.array([d.timetuple().tm_yday for d in dates], dtype=float)
        x = np.column_stack([t, np.sin(2 * np.pi * doy / 365), np.cos(2 * np.pi * doy / 365)])
        model = LinearRegression()
        model.fit(x, y)
        pred = model.predict(x)
        resid = float(np.std(y - pred))
        predict_at = lambda future: float(model.predict(future)[0])
        provider = "sklearn_linear_seasonal"
        use_sklearn = True
    except ImportError:
        y = prices
        n = len(y)
        mean_x = (n - 1) / 2
        mean_y = _mean(y)
        den = sum((i - mean_x) ** 2 for i in range(n)) or 1.0
        slope = sum((i - mean_x) * (price - mean_y) for i, price in enumerate(y)) / den
        intercept = mean_y - slope * mean_x
        fitted = [intercept + slope * i for i in range(n)]
        resid = _std([price - fit for price, fit in zip(y, fitted)])
        predict_at = lambda future: intercept + slope * float(future)
        provider = "linear_trend"
        use_sklearn = False
        np = None
    last = float(y[-1])
    points = []
    last_day = dates[-1]
    for horizon in (7, 30):
        future_date = last_day + timedelta(days=horizon)
        ft = (future_date - origin).days
        if use_sklearn:
            fdoy = future_date.timetuple().tm_yday
            fx = np.array([[ft, math.sin(2 * math.pi * fdoy / 365), math.cos(2 * math.pi * fdoy / 365)]])
            value = predict_at(fx)
        else:
            value = predict_at((len(y) - 1) + horizon)
        points.append({"day": horizon, "date": future_date.isoformat(), "price": round(value, 2)})
    target = points[0]["price"]
    if target > last * 1.01:
        direction = "up"
    elif target < last * 0.99:
        direction = "down"
    else:
        direction = "stable"
    confidence = round(max(0.3, min(0.95, 1 - resid / max(last, 1))), 2)
    series = [{"date": d.isoformat(), "price": round(float(p), 2)} for d, p in zip(dates[-30:], y[-30:])]
    return {
        "direction": direction,
        "confidence": confidence,
        "current": round(last, 2),
        "forecast": points,
        "history": series,
        "provider": provider,
    }


def abnormal(value: float, history_prices: list[float], peer_prices: list[float]) -> dict:
    series = [p for p in history_prices + peer_prices if p is not None]
    if len(series) < 4:
        return {"flag": False, "reason": "Not enough peer or history prices.", "zscore": 0, "provider": "zscore_iqr"}
    try:
        np, _ = _libs()
        arr = np.array(series, dtype=float)
        mu = float(arr.mean())
        sigma = float(arr.std()) or 1.0
        q1, q3 = np.percentile(arr, [25, 75])
    except ImportError:
        mu = _mean(series)
        sigma = _std(series) or 1.0
        q1, q3 = _percentile(series, 25), _percentile(series, 75)
    z = (value - mu) / sigma
    iqr = q3 - q1 or 1.0
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    flag = abs(z) >= 2 or value < low or value > high
    if not flag:
        reason = "Quote is inside the usual range."
    elif value < mu:
        reason = f"Unusually low: z-score {z:.2f} versus mean ₹{mu:.0f}/kg."
    else:
        reason = f"Unusually high: z-score {z:.2f} versus mean ₹{mu:.0f}/kg."
    return {"flag": bool(flag), "reason": reason, "zscore": round(float(z), 2), "mean": round(mu, 2), "provider": "zscore_iqr"}
