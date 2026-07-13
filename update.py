from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

SEOUL = ZoneInfo("Asia/Seoul")
OUTPUT = Path("data.json")
TICKER = "^KS11"


def safe_float(value):
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


def download_data(period: str, interval: str) -> pd.DataFrame:
    last_error = None

    for attempt in range(3):
        try:
            df = yf.download(
                TICKER,
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

    raise RuntimeError(f"코스피 데이터 수집 실패: {last_error}")


def normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    index = pd.to_datetime(result.index)

    if index.tz is None:
        index = index.tz_localize("UTC").tz_convert(SEOUL)
    else:
        index = index.tz_convert(SEOUL)

    result.index = index
    return result


def load_kospi() -> dict:
    daily = normalize_index(download_data("1y", "1d"))
    intraday = normalize_index(download_data("5d", "5m"))

    daily = daily.dropna(subset=["Open", "High", "Low", "Close"])
    intraday = intraday.dropna(subset=["Close"])

    # 당일 5분봉을 이용해 최신 일봉을 보정합니다.
    if not intraday.empty:
        latest_day = intraday.index[-1].date()
        today_rows = intraday[intraday.index.date == latest_day]

        if not today_rows.empty:
            open_value = today_rows["Open"].dropna().iloc[0]
            close_value = today_rows["Close"].dropna().iloc[-1]

            new_row = {
                "Open": float(open_value),
                "High": float(today_rows["High"].max()),
                "Low": float(today_rows["Low"].min()),
                "Close": float(close_value),
                "Volume": float(today_rows["Volume"].fillna(0).sum()),
            }

            timestamp = pd.Timestamp(
                datetime.combine(latest_day, datetime.min.time()),
                tz=SEOUL,
            )

            daily = daily[daily.index.date != latest_day]
            daily.loc[timestamp] = new_row
            daily = daily.sort_index()

    daily = daily.tail(260)

    candles = []

    for timestamp, row in daily.iterrows():
        candles.append(
            {
                "time": timestamp.strftime("%Y-%m-%d"),
                "open": safe_float(row["Open"]),
                "high": safe_float(row["High"]),
                "low": safe_float(row["Low"]),
                "close": safe_float(row["Close"]),
                "volume": int(float(row.get("Volume", 0) or 0)),
            }
        )

    if len(candles) < 2:
        raise RuntimeError("표시할 코스피 데이터가 부족합니다.")

    latest = candles[-1]
    previous = candles[-2]

    change = latest["close"] - previous["close"]
    change_pct = (
        change / previous["close"] * 100
        if previous["close"]
        else 0
    )

    return {
        "ticker": TICKER,
        "name": "코스피",
        "unit": "KOSPI",
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
        "market": load_kospi(),
    }

    temp_file = OUTPUT.with_suffix(".tmp")
    temp_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_file.replace(OUTPUT)

    print(
        json.dumps(
            {
                "updatedAt": payload["updatedAt"],
                "latest": payload["market"]["latest"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
