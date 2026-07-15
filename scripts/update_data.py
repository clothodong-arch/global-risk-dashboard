from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "dashboard.json"

MARKET = {
    "^TNX": ("美国10Y收益率", "利率", "%", 2, True),
    "^TYX": ("美国30Y收益率", "利率", "%", 2, True),
    "^MOVE": ("MOVE债券波动率", "波动率", "", 1, True),
    "^VIX": ("VIX股票波动率", "波动率", "", 1, True),
    "DX-Y.NYB": ("美元指数DXY", "美元", "", 2, True),
    "JPY=X": ("USD/JPY", "套息交易", "", 2, True),
    "^GSPC": ("标普500", "股市", "", 0, False),
    "^IXIC": ("纳斯达克", "股市", "", 0, False),
    "^N225": ("日经225", "股市", "", 0, False),
    "^KS11": ("韩国KOSPI", "股市", "", 0, False),
    "^TWII": ("台湾加权", "股市", "", 0, False),
    "^HSI": ("恒生指数", "股市", "", 0, False),
    "HYG": ("高收益债ETF HYG", "信用", "", 2, False),
    "TLT": ("长期美债ETF TLT", "债券", "", 2, False),
}

FRED = {
    "BAMLH0A0HYM2": ("美国高收益债利差", "信用", "%", 2, True),
    "NFCI": ("芝加哥金融状况指数", "流动性", "", 2, True),
    "WRESBAL": ("美国银行准备金", "流动性", "十亿美元", 0, False),
    "RRPONTSYD": ("隔夜逆回购", "流动性", "十亿美元", 0, False),
    "WTREGEN": ("美国财政部TGA", "流动性", "十亿美元", 0, True),
}

MONEY_SERIES = {"WRESBAL", "RRPONTSYD", "WTREGEN"}


def pct(series: pd.Series, periods: int) -> float | None:
    series = series.dropna()
    if len(series) <= periods:
        return None
    base = series.iloc[-periods - 1]
    latest = series.iloc[-1]
    if pd.isna(base) or base == 0:
        return None
    return float((latest / base - 1) * 100)


def clean_series(series: pd.Series) -> pd.Series:
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    series = pd.to_numeric(series, errors="coerce").dropna()
    return series[~series.index.duplicated(keep="last")].sort_index()


def fetch_market() -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    out: dict[str, dict[str, Any]] = {}
    missing: list[dict[str, str]] = []
    for ticker, meta in MARKET.items():
        try:
            raw = yf.download(
                ticker,
                period="1y",
                auto_adjust=True,
                progress=False,
                threads=False,
                timeout=25,
            )
            if raw.empty or "Close" not in raw:
                raise ValueError("empty close series")
            close = clean_series(raw["Close"])
            if close.empty:
                raise ValueError("no numeric close values")
            out[ticker] = {
                "series": close,
                "value": float(close.iloc[-1]),
                "c1": pct(close, 1),
                "c20": pct(close, 20),
                "source": "Yahoo Finance",
            }
            print(f"market ok {ticker} {meta[0]}")
        except Exception as exc:
            print(f"market missing {ticker} {meta[0]}: {exc}")
            missing.append({"symbol": ticker, "name": meta[0], "source": "Yahoo Finance", "reason": str(exc)})
    return out, missing


def fred_csv(series: str, session: requests.Session) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    response = session.get(url, timeout=25)
    response.raise_for_status()
    df = pd.read_csv(pd.io.common.StringIO(response.text))
    if df.empty or len(df.columns) < 2:
        raise ValueError("empty FRED response")
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    data = df.dropna().set_index("date")["value"]
    if data.empty:
        raise ValueError("no numeric FRED values")
    return clean_series(data)


def fetch_fred() -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    out: dict[str, dict[str, Any]] = {}
    missing: list[dict[str, str]] = []
    session = requests.Session()
    for series, meta in FRED.items():
        try:
            values = fred_csv(series, session)
            if series in MONEY_SERIES:
                values = values / 1000
            out[series] = {
                "series": values,
                "value": float(values.iloc[-1]),
                "c1": pct(values, 1),
                "c20": pct(values, 20),
                "source": "FRED",
            }
            print(f"fred ok {series} {meta[0]}")
        except Exception as exc:
            print(f"fred missing {series} {meta[0]}: {exc}")
            missing.append({"symbol": series, "name": meta[0], "source": "FRED", "reason": str(exc)})
    return out, missing


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def level(value: float, low: float, high: float) -> float:
    return clamp((value - low) / (high - low) * 100)


def calculate(market: dict[str, dict[str, Any]], fred: dict[str, dict[str, Any]]) -> tuple[int, str, str]:
    pieces: list[tuple[str, float, float]] = []

    def add(name: str, score: float | None, weight: float) -> None:
        if score is not None:
            pieces.append((name, clamp(score), weight))

    if "^VIX" in market:
        add("VIX", level(market["^VIX"]["value"], 13, 40), 0.15)
    if "^MOVE" in market:
        add("MOVE", level(market["^MOVE"]["value"], 80, 180), 0.15)
    if "^TNX" in market:
        add("10Y", level(market["^TNX"]["value"], 3.5, 5.5), 0.12)
    if "^TYX" in market:
        add("30Y", level(market["^TYX"]["value"], 3.8, 5.8), 0.10)
    if "BAMLH0A0HYM2" in fred:
        add("HY spread", level(fred["BAMLH0A0HYM2"]["value"], 2.8, 7), 0.16)
    if "NFCI" in fred:
        add("NFCI", level(fred["NFCI"]["value"], -0.6, 0.8), 0.10)
    if "^GSPC" in market:
        add("SPX momentum", clamp(-(market["^GSPC"]["c20"] or 0) * 5 + 35), 0.10)
    if "JPY=X" in market:
        add("JPY carry", clamp(-(market["JPY=X"]["c20"] or 0) * 6 + 35), 0.06)
    if "DX-Y.NYB" in market:
        add("DXY", level(market["DX-Y.NYB"]["value"], 98, 112), 0.06)

    if not pieces:
        raise RuntimeError("no usable indicators for risk score")

    score = round(sum(score * weight for _, score, weight in pieces) / sum(weight for _, _, weight in pieces))
    if score >= 70:
        return score, "高风险", "去杠杆 / 压力状态"
    if score >= 45:
        return score, "中等风险", "防御性上升"
    return score, "低风险", "风险偏好正常"


def narrative(score: int, market: dict[str, dict[str, Any]], fred: dict[str, dict[str, Any]]) -> tuple[str, str, list[str]]:
    signals: list[str] = []
    vix = market.get("^VIX", {}).get("value")
    move = market.get("^MOVE", {}).get("value")
    spx = market.get("^GSPC", {}).get("c20")
    hy = fred.get("BAMLH0A0HYM2", {}).get("value")
    usdjpy = market.get("JPY=X", {}).get("c20")
    if move and move > 120:
        signals.append("债券波动率处于高位，利率风险可能继续向股票估值与杠杆资金传导。")
    if vix and vix > 25:
        signals.append("VIX 已进入明显压力区，波动率目标基金与风险平价策略可能被动减仓。")
    if spx is not None and spx < -5:
        signals.append("标普500二十日动量显著转弱，当前调整已不只是单日事件。")
    if hy and hy > 4.5:
        signals.append("高收益债利差扩大，需警惕从估值调整转向信用收缩。")
    if usdjpy is not None and usdjpy < -3:
        signals.append("美元兑日元快速下行，日元套息交易平仓风险上升。")
    if not signals:
        signals.append("暂未出现多指标共振，当前更接近普通风险重定价，而非系统性危机。")

    if score >= 70:
        headline = "多项压力指标共振，市场可能处于机械化去杠杆阶段。"
        summary = "当前风险不只来自基本面预期下修，还可能受到波动率控制、CTA、风险平价及融资约束的放大。重点观察信用利差和债券波动率是否继续恶化。"
    elif score >= 45:
        headline = "风险偏好正在下降，但尚未确认演变为系统性流动性事件。"
        summary = "市场处于利率、估值与仓位再平衡阶段。若信用利差保持稳定，调整更可能是风险预算收缩；若信用与融资指标同步恶化，则应提高危机概率判断。"
    else:
        headline = "整体金融条件仍可控，尚无广泛去杠杆证据。"
        summary = "波动可能集中在个别高估值资产或地区市场。当前更适合区分基本面弱化与仓位冲击，而非直接套用金融危机叙事。"
    return headline, summary, signals


def norm90(series: pd.Series) -> tuple[list[float], list[str]]:
    values = series.dropna().tail(90)
    if values.empty or values.iloc[0] == 0:
        return [], []
    return [round(float(value / values.iloc[0] * 100), 2) for value in values], [
        date.strftime("%Y-%m-%d") for date in values.index
    ]


def build_cards(market: dict[str, dict[str, Any]], fred: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    cards = []
    for key, meta in {**MARKET, **FRED}.items():
        source = market.get(key) or fred.get(key)
        if not source:
            continue
        name, category, unit, decimals, risk_up = meta
        cards.append(
            {
                "name": name,
                "category": category,
                "value": source["value"],
                "change_1d": source["c1"],
                "change_20d": source["c20"],
                "unit": unit,
                "change_unit": "%",
                "decimals": decimals,
                "risk_up": risk_up,
                "source": source["source"],
            }
        )
    return cards


def build_history(market: dict[str, dict[str, Any]]) -> dict[str, Any]:
    dates: list[str] = []
    stress: list[dict[str, Any]] = []
    equities: list[dict[str, Any]] = []
    for key in ["^VIX", "^MOVE", "^TNX"]:
        if key in market:
            values, series_dates = norm90(market[key]["series"])
            if values:
                dates = dates or series_dates
                stress.append({"name": MARKET[key][0], "values": values})
    for key in ["^GSPC", "^IXIC", "^N225", "^KS11", "^TWII", "^HSI"]:
        if key in market:
            values, series_dates = norm90(market[key]["series"])
            if values:
                dates = dates or series_dates
                equities.append({"name": MARKET[key][0], "values": values})
    return {"dates": dates, "stress": stress, "equities": equities}


def main() -> None:
    market, market_missing = fetch_market()
    fred, fred_missing = fetch_fred()
    score, label, regime = calculate(market, fred)
    headline, summary, signals = narrative(score, market, fred)
    cards = build_cards(market, fred)
    missing = market_missing + fred_missing
    expected = len(MARKET) + len(FRED)
    successful = len(cards)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "risk": {"score": score, "label": label, "regime": regime},
        "analysis": {
            "headline": headline,
            "summary": summary,
            "signals": signals,
            "transmission": [
                "长端利率 / 政策冲击",
                "债券与股票波动率上升",
                "风险预算下降",
                "CTA / Vol Target / Risk Parity 减仓",
                "全球风险资产同步调整",
            ],
        },
        "cards": cards,
        "history": build_history(market),
        "data_quality": {
            "expected": expected,
            "successful": successful,
            "missing": missing,
            "sources": sorted({card["source"] for card in cards}),
        },
    }

    if successful == 0:
        raise RuntimeError("all live data sources failed; refusing to publish an empty dashboard")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"data coverage {successful}/{expected}; missing {len(missing)}")


if __name__ == "__main__":
    main()
