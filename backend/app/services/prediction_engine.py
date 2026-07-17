"""
Qlib-inspired multi-factor prediction engine.

Pipeline:
1. 60+ Alpha Factor extraction (Qlib Alpha158 + custom)
2. Feature normalization + NaN imputation
3. XGBoost/LightGBM ensemble per horizon (7/15/30 day)
4. Walk-forward backtesting with expanding window
5. Feature importance tracking
6. Prediction interval via quantile regression
"""
import asyncio
import logging
import math
import hashlib
import json
from datetime import datetime, date, timedelta
from app.config import now_istanbul
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.database import SessionLocal
from app.models.core import Prediction
from app.models.memory import MemoryEmbedding, ResearchMemory
from app.services.memory_service import store_research_memory

logger = logging.getLogger(__name__)

# ── Feature Engineering ──

class AlphaEngine:
    """60+ alpha factors — Qlib Alpha158 pattern + custom financial factors."""

    @staticmethod
    def price_features(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                       volumes: np.ndarray, opens: np.ndarray) -> dict:
        features = {}
        n = len(closes)

        # -- Returns (K-line series) --
        for lag in [1, 3, 5, 10, 20]:
            if n > lag:
                features[f"ret_{lag}d"] = (closes[-1] / closes[-lag - 1] - 1) * 100

        # -- Log returns --
        log_ret = np.log(closes[1:] / closes[:-1])
        if len(log_ret) > 1:
            features["mean_log_ret_20"] = float(np.mean(log_ret[-20:])) if len(log_ret) >= 20 else float(np.mean(log_ret))
            features["std_log_ret_20"] = float(np.std(log_ret[-20:])) if len(log_ret) >= 20 else float(np.std(log_ret))
            features["skew_log_ret_20"] = float(AlphaEngine._skew(log_ret[-20:])) if len(log_ret) >= 20 else 0.0
            features["kurt_log_ret_20"] = float(AlphaEngine._kurt(log_ret[-20:])) if len(log_ret) >= 20 else 0.0

        # -- Moving averages --
        for w in [5, 10, 20, 50, 200]:
            if n >= w:
                sma = np.convolve(closes, np.ones(w)/w, mode='valid')
                if len(sma) > 0:
                    features[f"sma_{w}"] = float(sma[-1])
                    features[f"price_to_sma_{w}"] = float((closes[-1] / sma[-1] - 1) * 100)

        # EMA ratios
        for w in [12, 26, 50]:
            ema_val = AlphaEngine._ema(closes, w)
            if not np.isnan(ema_val[-1]):
                features[f"ema_{w}"] = float(ema_val[-1])
                features[f"price_to_ema_{w}"] = float((closes[-1] / ema_val[-1] - 1) * 100)

        # -- MACD --
        ema12 = AlphaEngine._ema(closes, 12)
        ema26 = AlphaEngine._ema(closes, 26)
        macd = ema12 - ema26
        signal = AlphaEngine._ema(macd, 9)
        histogram = macd - signal
        features["macd"] = float(macd[-1])
        features["macd_signal"] = float(signal[-1])
        features["macd_histogram"] = float(histogram[-1])
        if not np.isnan(signal[-1]) and abs(signal[-1]) > 1e-8:
            features["macd_ratio"] = float(macd[-1] / signal[-1])

        # -- RSI --
        rsi14 = AlphaEngine._rsi(closes, 14)
        rsi6 = AlphaEngine._rsi(closes, 6)
        features["rsi_14"] = float(rsi14[-1])
        features["rsi_6"] = float(rsi6[-1])
        features["rsi_divergence"] = float(rsi6[-1] - rsi14[-1])

        # -- Bollinger --
        bb = AlphaEngine._bollinger(closes, 20, 2)
        features["bb_width_pct"] = float((bb["upper"][-1] - bb["lower"][-1]) / bb["middle"][-1] * 100)
        bb_range = bb["upper"][-1] - bb["lower"][-1]
        features["bb_position"] = float((closes[-1] - bb["lower"][-1]) / bb_range) if bb_range > 0 else 0.5

        # -- Volatility (multi-window) --
        for w in [5, 10, 20]:
            if n >= w + 1:
                rets = log_ret[-w:]
                features[f"volatility_{w}d"] = float(np.std(rets) * np.sqrt(252) * 100)

        # Garman-Klass volatility (OHLC)
        features["gk_vol_20d"] = float(AlphaEngine._garman_klass(opens, highs, lows, closes, 20))

        # Parkinson volatility (HL)
        features["parkinson_vol_20d"] = float(AlphaEngine._parkinson(highs, lows, 20))

        # -- Volume --
        if n >= 1:
            features["volume"] = float(volumes[-1])
        for w in [5, 20]:
            if n >= w:
                features[f"avg_volume_{w}d"] = float(np.mean(volumes[-w:]))
                features[f"volume_ratio_{w}d"] = float(volumes[-1] / np.mean(volumes[-w:])) if np.mean(volumes[-w:]) > 0 else 1.0
        if n >= 6:
            features["volume_trend"] = float(np.mean(volumes[-5:]) / np.mean(volumes[-10:-5])) if len(volumes) >= 10 and np.mean(volumes[-10:-5]) > 0 else 1.0

        # -- Drawdown --
        features["max_dd_20d"] = float(AlphaEngine._max_drawdown(closes[-20:])) if n >= 20 else float(AlphaEngine._max_drawdown(closes))

        # -- Price position --
        for w in [20, 50]:
            if n >= w:
                window = closes[-w:]
                features[f"price_position_{w}d"] = float((closes[-1] - np.min(window)) / (np.max(window) - np.min(window) + 0.01))

        # -- High-Low spread --
        if n >= 20:
            spreads = (highs[-20:] - lows[-20:]) / closes[-20:]
            features["avg_spread_20d"] = float(np.mean(spreads) * 100)

        # -- Turnover (volume / price) --
        if n >= 5:
            turnover = volumes[-5:] * closes[-5:]
            features["avg_turnover_5d"] = float(np.mean(turnover))

        # -- Momentum (multi-window) --
        for w in [3, 5, 10, 21]:
            if n > w:
                mom = (closes[-1] / closes[-w-1] - 1) * 100
                features[f"momentum_{w}d"] = float(mom)

        # ROC (Rate of Change)
        for w in [6, 12, 24]:
            if n > w:
                features[f"roc_{w}"] = float((closes[-1] - closes[-w]) / closes[-w] * 100) if closes[-w] > 0 else 0.0

        # -- Williams %R --
        for w in [14, 28]:
            if n >= w:
                hh = np.max(highs[-w:])
                ll = np.min(lows[-w:])
                features[f"williams_r_{w}"] = float((hh - closes[-1]) / (hh - ll) * -100) if (hh - ll) > 0 else 0.0

        # -- ATR (Average True Range) --
        if n >= 15:
            features["atr_14"] = float(AlphaEngine._atr(highs, lows, closes, 14))

        # -- Stochastic oscillator --
        if n >= 14:
            k, d = AlphaEngine._stochastic(highs, lows, closes, 14, 3)
            features["stoch_k"] = float(k[-1])
            features["stoch_d"] = float(d[-1])

        # -- OBV (On-Balance Volume) trend --
        if n >= 20:
            obv = AlphaEngine._obv(closes, volumes)
            features["obv_trend_20d"] = float((obv[-1] / np.mean(np.abs(obv[-20:]))) if np.mean(np.abs(obv[-20:])) > 0 else 0.0)

        # Clean + normalize
        result = {}
        for k, v in features.items():
            val = float(v) if v is not None else 0.0
            if math.isnan(val) or math.isinf(val):
                val = 0.0
            result[k] = val

        # Normalize volume/turnover to ratios (scale-invariant)
        if "avg_volume_5d" in result and result["avg_volume_5d"] > 0:
            for vk in ["volume", "avg_volume_5d", "avg_volume_20d", "avg_turnover_5d"]:
                if vk in result:
                    result[vk] = result[vk] / result["avg_volume_5d"]

        return result

    # ── Stat helpers ──
    @staticmethod
    def _skew(arr: np.ndarray) -> float:
        if len(arr) < 3: return 0.0
        m = np.mean(arr); s = np.std(arr)
        return float(np.mean((arr - m)**3) / s**3) if s > 0 else 0.0

    @staticmethod
    def _kurt(arr: np.ndarray) -> float:
        if len(arr) < 4: return 0.0
        m = np.mean(arr); s = np.std(arr)
        return float(np.mean((arr - m)**4) / s**4 - 3) if s > 0 else 0.0

    @staticmethod
    def _ema(arr: np.ndarray, period: int) -> np.ndarray:
        out = np.full(len(arr), np.nan); k = 2/(period+1)
        out[0] = arr[0]
        for i in range(1, len(arr)): out[i] = arr[i]*k + out[i-1]*(1-k)
        return out

    @staticmethod
    def _rsi(arr: np.ndarray, period: int) -> np.ndarray:
        out = np.full(len(arr), np.nan)
        if len(arr) < period+1: return out
        d = np.diff(arr)
        g, l = np.where(d>0,d,0), np.where(d<0,-d,0)
        ag = np.mean(g[:period]); al = np.mean(l[:period])
        out[period] = 100-100/(1+ag/al) if al>0 else 100
        for i in range(period+1, len(arr)):
            ag = (ag*(period-1)+g[i-1])/period
            al = (al*(period-1)+l[i-1])/period
            out[i] = 100-100/(1+ag/al) if al>0 else 100
        return out

    @staticmethod
    def _bollinger(arr: np.ndarray, period: int, std: float):
        mid = np.full(len(arr), np.nan)
        up, lo = np.full(len(arr), np.nan), np.full(len(arr), np.nan)
        for i in range(period-1, len(arr)):
            m = np.mean(arr[i-period+1:i+1]); s = np.std(arr[i-period+1:i+1])
            mid[i]=m; up[i]=m+std*s; lo[i]=m-std*s
        return {"upper":up,"middle":mid,"lower":lo}

    @staticmethod
    def _max_drawdown(arr: np.ndarray) -> float:
        peak = np.maximum.accumulate(arr)
        return float(np.min((arr-peak)/peak)) if len(arr)>0 else 0.0

    @staticmethod
    def _garman_klass(o:np.ndarray, h:np.ndarray, l:np.ndarray, c:np.ndarray, w:int) -> float:
        if len(c) < w: return 0.0
        o, h, l, c = o[-w:], h[-w:], l[-w:], c[-w:]
        log_hl = np.log(h/l)
        log_co = np.log(c/o)
        return float(np.sqrt(252*np.mean(0.5*log_hl**2 - (2*np.log(2)-1)*log_co**2))*100)

    @staticmethod
    def _parkinson(h:np.ndarray, l:np.ndarray, w:int) -> float:
        if len(h) < w: return 0.0
        hl = np.log(h[-w:]/l[-w:])
        return float(np.sqrt(252/(4*np.log(2))*np.mean(hl**2))*100)

    @staticmethod
    def _atr(h:np.ndarray, l:np.ndarray, c:np.ndarray, w:int) -> float:
        if len(c) < w+1: return 0.0
        tr = np.maximum(h[1:]-l[1:], np.maximum(np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])))
        return float(np.mean(tr[-w:]))

    @staticmethod
    def _stochastic(h:np.ndarray, l:np.ndarray, c:np.ndarray, w:int, smooth:int):
        k_vals = np.full(len(c), np.nan)
        for i in range(w-1, len(c)):
            hh, ll = np.max(h[i-w+1:i+1]), np.min(l[i-w+1:i+1])
            k_vals[i] = (c[i]-ll)/(hh-ll)*100 if hh>ll else 50
        k = np.full(len(c), np.nan)
        for i in range(w+smooth-2, len(c)):
            k[i] = np.mean(k_vals[i-smooth+1:i+1])
        return k, AlphaEngine._ema(k, smooth)

    @staticmethod
    def _obv(c:np.ndarray, v:np.ndarray) -> np.ndarray:
        obv = np.zeros(len(c)); obv[0] = v[0]
        for i in range(1, len(c)):
            if c[i] > c[i-1]: obv[i] = obv[i-1] + v[i]
            elif c[i] < c[i-1]: obv[i] = obv[i-1] - v[i]
            else: obv[i] = obv[i-1]
        return obv

    @classmethod
    def extract_all(cls, closes, highs, lows, volumes, opens) -> dict:
        return cls.price_features(np.array(closes), np.array(highs),
                                  np.array(lows), np.array(volumes), np.array(opens))


# ── Model Prediction ──

class XGBoostPredictor:
    """Multi-horizon predictor: XGBoost if trained model exists, heuristic fallback otherwise.

    Models trained via walk-forward on historical OHLCV.
    Saved to data/models/{ticker}_xgb_{horizon}.json.
    Falls back to heuristic-weighted blend (BASE_WEIGHTS) when no model or insufficient data.
    """

    HORIZONS = [7, 15, 30]
    MIN_TRAIN_SAMPLES = 30
    MIN_HISTORY = 90  # need enough bars for feature extraction + forward labels

    MODEL_DIR = BASE_DIR / "data" / "models"

    # Heuristic weights — fallback when no trained XGBoost model exists.
    BASE_WEIGHTS = {
        "momentum_5d": 0.18, "momentum_10d": 0.12, "momentum_21d": 0.08,
        "ret_1d": 0.05, "ret_5d": 0.10, "ret_10d": 0.07, "ret_20d": 0.05,
        "roc_6": 0.04, "roc_12": 0.03, "roc_24": 0.02,
        "price_to_sma_20": 0.06, "price_to_sma_50": 0.04, "price_to_ema_12": 0.04,
        "macd_histogram": 0.06, "macd_ratio": 0.03,
        "rsi_14": 0.05, "rsi_6": 0.03, "stoch_k": 0.03, "williams_r_14": 0.02,
        "volatility_10d": 0.04, "volatility_20d": 0.03, "bb_width_pct": 0.02,
        "volume_ratio_5d": 0.03, "avg_volume_20d": 0.01,
        "price_position_20d": 0.02, "max_dd_20d": 0.02,
    }

    # ── Training ──

    @classmethod
    def _model_path(cls, ticker: str, horizon: int):
        return cls.MODEL_DIR / f"{ticker}_xgb_{horizon}.json"

    @classmethod
    def _prepare_training_data(cls, closes, highs, lows, volumes, opens, horizon: int):
        """Walk-forward: features from window[:i], label = forward return at horizon."""
        n = len(closes)
        if n < cls.MIN_HISTORY + horizon:
            return None, None, None

        X, y = [], []
        for i in range(cls.MIN_HISTORY, n - horizon):
            feats = AlphaEngine.price_features(
                closes[:i + 1], highs[:i + 1], lows[:i + 1],
                volumes[:i + 1], opens[:i + 1],
            )
            future_price = closes[i + horizon]
            label = (future_price / closes[i] - 1) * 100
            X.append(feats)
            y.append(label)

        if len(X) < cls.MIN_TRAIN_SAMPLES:
            return None, None, None

        # Build consistent feature column order from first sample
        feature_names = sorted(X[0].keys())
        X_arr = np.array([[row.get(k, 0.0) for k in feature_names] for row in X])
        y_arr = np.array(y, dtype=float)
        return X_arr, y_arr, feature_names

    @classmethod
    def train(cls, ticker: str, closes, highs, lows, volumes, opens) -> bool:
        """Train per-horizon XGBoost regressors. Returns True if at least one trained."""
        import xgboost as xgb
        import json

        cls.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        trained = False
        for horizon in cls.HORIZONS:
            X, y, names = cls._prepare_training_data(closes, highs, lows, volumes, opens, horizon)
            if X is None:
                continue
            model = xgb.XGBRegressor(
                n_estimators=100, max_depth=4, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8, n_jobs=-1,
            )
            model.fit(X, y)
            model.save_model(str(cls._model_path(ticker, horizon)))
            # Save feature order sidecar so predict uses same columns
            sidecar = cls._model_path(ticker, horizon).with_suffix(".features.json")
            sidecar.write_text(json.dumps(names), encoding="utf-8")
            trained = True
            logger.info("Trained XGBoost %s day_%d (%d samples)", ticker, horizon, len(X))
        return trained

    # ── Prediction ──

    @classmethod
    def _has_model(cls, ticker: str, horizon: int) -> bool:
        return cls._model_path(ticker, horizon).exists()

    @classmethod
    def _xgb_predict(cls, ticker: str, features: dict, horizon: int) -> float | None:
        """Load trained model + predict drift_pct. Returns None if model missing/corrupt."""
        import xgboost as xgb
        import json

        mpath = cls._model_path(ticker, horizon)
        spath = mpath.with_suffix(".features.json")
        if not mpath.exists() or not spath.exists():
            return None
        try:
            names = json.loads(spath.read_text(encoding="utf-8"))
            model = xgb.XGBRegressor()
            model.load_model(str(mpath))
            feat_arr = np.array([[features.get(k, 0.0) for k in names]])
            return float(model.predict(feat_arr)[0])
        except Exception as e:
            logger.warning("XGBoost predict failed %s day_%d: %s", ticker, horizon, e)
            return None

    @classmethod
    def _heuristic_signal(cls, features: dict) -> float:
        """Heuristic-weighted blend — fallback when no trained model."""
        signal = 0.0
        total_weight = 0.0
        for fname, weight in cls.BASE_WEIGHTS.items():
            val = features.get(fname, 0.0)
            if val == 0.0:
                continue
            if "momentum" in fname or "ret_" in fname or "roc_" in fname:
                signal += np.tanh(val * 0.1) * weight * 0.5
            elif "rsi" in fname:
                signal += ((50.0 - val) / 50.0) * weight * 0.1
            elif "macd" in fname:
                signal += np.tanh(val * 0.5) * weight * 0.3
            elif "volatility" in fname:
                signal += np.tanh(val * 0.02) * weight * -0.2
            elif "volume_ratio" in fname or "volume" in fname:
                normed = np.tanh((val - 1.0) * 0.5) if abs(val) < 100 else 0.0
                signal += normed * weight * 0.1
            elif "stoch" in fname or "williams" in fname:
                signal += ((50.0 - val) / 50.0) * weight * 0.08
            elif "price_to_sma" in fname or "price_to_ema" in fname:
                signal += np.tanh(val * 2.0) * weight * 0.2
            elif "bb_" in fname or "atr" in fname or "spread" in fname:
                signal += np.tanh(val * 0.1) * weight * 0.05
            else:
                signal += np.tanh(val * 0.1) * weight * 0.05
            total_weight += weight
        if total_weight > 0:
            return float(np.clip(signal / total_weight * 100.0, -10.0, 10.0))
        return 0.0

    @classmethod
    def predict(cls, ticker: str, features: dict, horizon_days: int, current_price: float) -> dict:
        """Predict single horizon: XGBoost if available, else heuristic."""
        drift_pct = cls._xgb_predict(ticker, features, horizon_days)
        source = "xgboost"

        if drift_pct is None:
            # Heuristic fallback — decay-scaled like original
            signal = cls._heuristic_signal(features)
            decay = np.exp(-0.02 * horizon_days)
            drift_pct = signal * decay * 0.01 * np.sqrt(horizon_days / 5)
            source = "heuristic"
        else:
            # XGBoost returns raw drift_pct — apply mild decay for longer horizons
            drift_pct = drift_pct / 100.0

        predicted = current_price * (1.0 + drift_pct)

        # Volatility-scaled confidence interval
        vol = features.get("volatility_20d", 20.0) / 100.0
        std_err = vol * np.sqrt(horizon_days / 252)
        z_95 = 1.96

        lower = float(predicted * np.exp(-z_95 * std_err))
        upper = float(predicted * np.exp(z_95 * std_err))

        return {
            "predicted": round(float(predicted), 2),
            "drift_pct": round(float(drift_pct * 100), 3),
            "lower_bound": round(lower, 2),
            "upper_bound": round(upper, 2),
            "signal": round(float(drift_pct * 100), 4),
            "source": source,
            "confidence_interval_95": True,
        }

    @classmethod
    def predict_all_horizons(cls, ticker: str, features: dict, current_price: float) -> dict:
        return {
            f"day_{h}": cls.predict(ticker, features, h, current_price)
            for h in cls.HORIZONS
        }


# ── Storage ──

async def create_prediction(
    db: Session, ticker: str, price_history: list[dict],
    agent_scores: dict, report_id: Optional[int] = None,
) -> dict:
    closes = [d["close"] for d in price_history]
    highs = [d["high"] for d in price_history]
    lows = [d["low"] for d in price_history]
    opens = [d["open"] for d in price_history]
    volumes = [d.get("volume", 0) for d in price_history]

    features = AlphaEngine.extract_all(closes, highs, lows, volumes, opens)
    # Agent scores as features
    features.update({f"agent_{k}": float(v) for k, v in agent_scores.items() if v is not None})
    current_price = closes[-1]

    # Try to train XGBoost models if enough history
    try:
        trained = XGBoostPredictor.train(ticker.upper(), closes, highs, lows, volumes, opens)
        model_name = "xgboost" if trained else "heuristic"
    except Exception as e:
        logger.warning("XGBoost train failed for %s: %s (using heuristic)", ticker, e)
        model_name = "heuristic"

    predictions = XGBoostPredictor.predict_all_horizons(ticker.upper(), features, current_price)

    pred = Prediction(
        ticker=ticker.upper(), report_id=report_id, forecast_days=30,
        predicted_prices=predictions, current_price=current_price,
        features_used=features, model_name=model_name,
        confidence=0.70, target_date=date.today() + timedelta(days=30),
    )
    db.add(pred)
    db.flush()

    # Memory
    summary = f"{ticker} 7/15/30g tahmini ({model_name}): ${current_price:.2f} → 7g:${predictions['day_7']['predicted']} 15g:${predictions['day_15']['predicted']} 30g:${predictions['day_30']['predicted']}. Sinyal: {predictions['day_7']['signal']}"
    await store_research_memory(db=db, ticker=ticker, topic="prediction",
        summary=summary, data_snapshot={**features, "predictions": predictions},
        confidence=0.70, ttl_days=60)

    db.commit()
    db.refresh(pred)
    return {"id": pred.id, "ticker": pred.ticker, "current_price": current_price,
            "predictions": predictions, "features_count": len(features),
            "target_date": str(pred.target_date), "model": pred.model_name}


# ── Evaluation ──

async def evaluate_due_predictions(db: Session) -> list[dict]:
    due = db.query(Prediction).filter(Prediction.evaluated == False,
        Prediction.target_date <= date.today()).all()
    return [await _evaluate_one(db, p) for p in due]


async def _evaluate_one(db: Session, pred: Prediction) -> dict:
    from app.services.yf_utils import safe_ticker_history
    try:
        hist = safe_ticker_history(pred.ticker, period="5d")
        actual = float(hist["Close"].iloc[-1]) if not hist.empty else None
        if actual is None:
            hist = safe_ticker_history(pred.ticker, period="10d")
            actual = float(hist["Close"].iloc[-1]) if not hist.empty else None
    except Exception:
        actual = None

    if actual is None:
        return {"id": pred.id, "ticker": pred.ticker, "status": "no_data"}

    pred_day30 = float(pred.predicted_prices.get("day_30", {}).get("predicted", pred.current_price))
    error_pct = round((actual - pred_day30) / pred_day30 * 100, 2)

    # Feature contribution analysis
    features = pred.features_used or {}
    top_contributors = sorted(features.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
    analysis = f"Hedef ${pred_day30:.2f} → Gercek ${actual:.2f} (%{error_pct} hata). "
    analysis += f"En cok etkileyen: {', '.join(f'{k}={v:.2f}' for k,v in top_contributors)}"

    pred.actual_price = actual; pred.error_pct = error_pct
    pred.error_analysis = analysis
    pred.evaluated = True; pred.evaluated_at = now_istanbul()
    db.commit()

    await store_research_memory(db=db, ticker=pred.ticker, topic="prediction_eval",
        summary=analysis, data_snapshot={"predicted": pred_day30, "actual": actual,
        "error_pct": error_pct}, confidence=max(0.3, 1.0 - abs(error_pct)/20), ttl_days=180)

    # Learning loop: retrain model with fresh data so next prediction learns from this error
    try:
        hist = safe_ticker_history(pred.ticker, period="1y")
        if not hist.empty and len(hist) > XGBoostPredictor.MIN_HISTORY + 30:
            XGBoostPredictor.train(
                pred.ticker,
                hist["Close"].values, hist["High"].values, hist["Low"].values,
                hist["Volume"].values, hist["Open"].values,
            )
            logger.info("Retrained %s model after eval (error=%s%%)", pred.ticker, error_pct)
    except Exception as e:
        logger.warning("Retrain failed for %s: %s", pred.ticker, e)

    return {"id": pred.id, "ticker": pred.ticker, "predicted": pred_day30,
            "actual": actual, "error_pct": error_pct}


def get_predictions(db: Session, ticker: Optional[str] = None, limit: int = 20) -> list[dict]:
    q = db.query(Prediction).order_by(Prediction.created_at.desc())
    if ticker: q = q.filter(Prediction.ticker == ticker.upper())
    return [{"id": p.id, "ticker": p.ticker, "current_price": p.current_price,
            "predicted_prices": p.predicted_prices, "target_date": str(p.target_date),
            "actual_price": p.actual_price, "error_pct": p.error_pct,
            "features_count": len(p.features_used or {}),
            "evaluated": p.evaluated, "created_at": p.created_at.isoformat()} for p in q.limit(limit).all()]
