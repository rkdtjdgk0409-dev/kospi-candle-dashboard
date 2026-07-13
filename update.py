from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

SEOUL = ZoneInfo("Asia/Seoul")
OUTPUT = Path("data.json")

MARKETS = {
    "kospi": {"ticker": "^KS11", "name": "코스피", "unit": "KOSPI"},
    "kosdaq": {"ticker": "^KQ11", "name": "코스닥", "unit": "KOSDAQ"},
}


def _safe_float(value):
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


def _download(ticker: str, period: str, interval: str) -> pd.DataFrame:
    last_error = None
    for attempt in range(3):
        try:
            df = yf.download(
                ticker,
                period=period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=30,
            )
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df
        except Exception as exc:
            last_error = exc
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"{ticker} 데이터 수집 실패: {last_error}")


def _normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    idx = pd.to_datetime(out.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC").tz_convert(SEOUL)
    else:
        idx = idx.tz_convert(SEOUL)
    out.index = idx
    return out


def load_market(ticker: str) -> dict:
    daily = _normalize_index(_download(ticker, "1y", "1d"))
    intraday = _normalize_index(_download(ticker, "5d", "5m"))

    daily = daily.dropna(subset=["Open", "High", "Low", "Close"])
    intraday = intraday.dropna(subset=["Close"])

    # 최근 장중 시세로 오늘 일봉을 보정합니다.
    if not intraday.empty:
        latest_day = intraday.index[-1].date()
        today_rows = intraday[intraday.index.date == latest_day]
        if not today_rows.empty:
            row = {
                "Open": float(today_rows["Open"].dropna().iloc[0]),
                "High": float(today_rows["High"].max()),
                "Low": float(today_rows["Low"].min()),
                "Close": float(today_rows["Close"].dropna().iloc[-1]),
                "Volume": float(today_rows["Volume"].fillna(0).sum()),
            }
            ts = pd.Timestamp(datetime.combine(latest_day, datetime.min.time()), tz=SEOUL)
            daily = daily[daily.index.date != latest_day]
            daily.loc[ts] = row
            daily = daily.sort_index()

    daily = daily.tail(260)
    candles = []
    for ts, row in daily.iterrows():
        candles.append({
            "time": ts.strftime("%Y-%m-%d"),
            "open": _safe_float(row["Open"]),
            "high": _safe_float(row["High"]),
            "low": _safe_float(row["Low"]),
            "close": _safe_float(row["Close"]),
            "volume": int(float(row.get("Volume", 0) or 0)),
        })

    if len(candles) < 2:
        raise RuntimeError(f"{ticker}: 표시할 데이터가 부족합니다.")

    latest = candles[-1]
    prev = candles[-2]
    change = latest["close"] - prev["close"]
    change_pct = change / prev["close"] * 100 if prev["close"] else 0

    return {
        "latest": latest["close"],
        "change": round(change, 2),
        "changePct": round(change_pct, 2),
        "marketDate": latest["time"],
        "candles": candles,
    }


def main():
    now = datetime.now(SEOUL)
    payload = {
        "updatedAt": now.strftime("%Y-%m-%d %H:%M:%S KST"),
        "source": "Yahoo Finance 지연 시세",
        "markets": {},
    }

    errors = {}
    for key, meta in MARKETS.items():
        try:
            payload["markets"][key] = {**meta, **load_market(meta["ticker"])}
        except Exception as exc:
            errors[key] = str(exc)

    if errors:
        payload["errors"] = errors

    if not payload["markets"]:
        raise RuntimeError(f"모든 시장 데이터 수집 실패: {errors}")

    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUTPUT)
    print(json.dumps({"updatedAt": payload["updatedAt"], "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
