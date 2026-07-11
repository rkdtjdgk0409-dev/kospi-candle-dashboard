from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests


FRONT_API = "https://m.stock.naver.com/front-api"
CHART_PATH = "/chart/domestic/stock/end"
PRICE_LIST_PATH = "/stock/domestic/index/price/list"

OUTPUT_PATH = Path("data.json")
KST = ZoneInfo("Asia/Seoul")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Referer": "https://m.stock.naver.com/domestic/index/KOSPI/total",
    "Accept": "application/json, text/plain, */*",
}


def to_number(value: Any) -> float | None:
    """네이버 응답의 쉼표가 포함된 숫자 문자열을 float로 변환합니다."""
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace(",", "")
    text = text.replace("%", "").replace("원", "").replace("주", "")
    text = re.sub(r"[^0-9.+-]", "", text)

    if text in {"", "+", "-", ".", "+.", "-."}:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def first_value(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def normalize_date(value: Any) -> str | None:
    """YYYYMMDD 또는 YYYY-MM-DD를 Lightweight Charts용 YYYY-MM-DD로 바꿉니다."""
    if value is None:
        return None

    text = re.sub(r"[^0-9]", "", str(value))

    if len(text) < 8:
        return None

    text = text[:8]
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def find_candidate_lists(value: Any) -> list[list[dict[str, Any]]]:
    """응답 구조가 바뀌어도 OHLC가 든 리스트 후보를 재귀적으로 찾습니다."""
    candidates: list[list[dict[str, Any]]] = []

    if isinstance(value, list):
        dict_rows = [item for item in value if isinstance(item, dict)]

        if dict_rows:
            candidates.append(dict_rows)

        for item in value:
            candidates.extend(find_candidate_lists(item))

    elif isinstance(value, dict):
        for item in value.values():
            candidates.extend(find_candidate_lists(item))

    return candidates


def row_score(row: dict[str, Any]) -> int:
    keys = set(row.keys())
    groups = [
        {"localDate", "date", "businessDate", "tradeDate"},
        {"openPrice", "open"},
        {"highPrice", "high"},
        {"lowPrice", "low"},
        {"closePrice", "close", "currentPrice"},
    ]
    return sum(1 for group in groups if keys & group)


def choose_price_rows(payload: Any) -> list[dict[str, Any]]:
    """날짜·시가·고가·저가·종가가 들어 있는 리스트를 선택합니다."""
    if isinstance(payload, dict):
        direct = payload.get("priceInfos")

        if isinstance(direct, list) and direct:
            return [row for row in direct if isinstance(row, dict)]

    candidates = find_candidate_lists(payload)

    if not candidates:
        return []

    scored = []

    for rows in candidates:
        sample = rows[:5]
        score = sum(row_score(row) for row in sample)
        scored.append((score, len(rows), rows))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_score, _, best_rows = scored[0]

    if best_score < 4:
        return []

    return best_rows


def normalize_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}

    for row in raw_rows:
        date = normalize_date(
            first_value(
                row,
                ("localDate", "date", "businessDate", "tradeDate"),
            )
        )

        open_price = to_number(first_value(row, ("openPrice", "open")))
        high_price = to_number(first_value(row, ("highPrice", "high")))
        low_price = to_number(first_value(row, ("lowPrice", "low")))
        close_price = to_number(
            first_value(row, ("closePrice", "close", "currentPrice"))
        )
        volume = to_number(
            first_value(
                row,
                (
                    "accumulatedTradingVolume",
                    "tradingVolume",
                    "volume",
                    "accumulatedVolume",
                ),
            )
        )

        if (
            not date
            or open_price is None
            or high_price is None
            or low_price is None
            or close_price is None
        ):
            continue

        if min(open_price, high_price, low_price, close_price) <= 0:
            continue

        normalized[date] = {
            "time": date,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume or 0,
        }

    return [normalized[key] for key in sorted(normalized)]


def request_json(path: str, params: dict[str, Any]) -> Any:
    response = requests.get(
        f"{FRONT_API}{path}",
        params=params,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")

    if "json" not in content_type.lower():
        # Content-Type이 달라도 실제 본문이 JSON인 경우를 허용합니다.
        return response.json()

    return response.json()


def fetch_chart_rows() -> tuple[list[dict[str, Any]], str]:
    """네이버 캔들 차트 JSON을 우선 사용하고 가격 목록을 예비 경로로 사용합니다."""
    errors: list[str] = []

    try:
        payload = request_json(
            CHART_PATH,
            {
                "code": "KOSPI",
                "chartInfoType": "index",
                "scriptChartType": "candleDay",
            },
        )
        rows = normalize_rows(choose_price_rows(payload))

        if len(rows) >= 20:
            return rows[-500:], "네이버 증권 공개 캔들 차트 JSON"

        errors.append(f"캔들 API 데이터 부족: {len(rows)}개")

    except Exception as exc:
        errors.append(f"캔들 API: {type(exc).__name__}: {exc}")

    try:
        payload = request_json(
            PRICE_LIST_PATH,
            {
                "code": "KOSPI",
                "page": 1,
                "pageSize": 500,
            },
        )
        rows = normalize_rows(choose_price_rows(payload))

        if len(rows) >= 20:
            return rows[-500:], "네이버 증권 공개 지수 가격 JSON"

        errors.append(f"가격 목록 데이터 부족: {len(rows)}개")

    except Exception as exc:
        errors.append(f"가격 목록 API: {type(exc).__name__}: {exc}")

    raise RuntimeError(
        "코스피 OHLC 데이터를 가져오지 못했습니다. "
        + " | ".join(errors)
    )


def build_payload() -> dict[str, Any]:
    rows, source_name = fetch_chart_rows()

    latest = rows[-1]
    previous = rows[-2]

    change = latest["close"] - previous["close"]
    change_rate = (
        change / previous["close"] * 100
        if previous["close"]
        else 0
    )

    return {
        "index_code": "KOSPI",
        "index_name": "코스피",
        "market_date": latest["time"],
        "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "source_name": source_name,
        "source_url": "https://m.stock.naver.com/domestic/index/KOSPI/total",
        "latest": {
            "close": round(latest["close"], 2),
            "change": round(change, 2),
            "change_rate": round(change_rate, 2),
            "open": round(latest["open"], 2),
            "high": round(latest["high"], 2),
            "low": round(latest["low"], 2),
            "volume": latest["volume"],
        },
        "rows": rows,
    }


def main() -> None:
    payload = build_payload()

    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"저장 완료: {payload['market_date']} "
        f"종가 {payload['latest']['close']:,.2f}"
    )
    print(f"캔들 개수: {len(payload['rows'])}")
    print(f"출처: {payload['source_name']}")


if __name__ == "__main__":
    main()
