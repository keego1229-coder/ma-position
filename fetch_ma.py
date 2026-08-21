"""日足を取得して 5/25/75日移動平均線に対する位置を判定し、docs/data/ma.json に書き出す。

GitHub Actions から平日の引け後に実行される想定。
ブラウザからは docs/data/ma.json を読むだけなので CORS の問題は起きない。
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "watchlist.json"
OUT = ROOT / "docs" / "data" / "ma.json"

PERIODS = [5, 25, 75]
SPARK_DAYS = 60          # フロントの折れ線に渡す日数
CROSS_LOOKBACK = 60      # 直近クロスを何営業日さかのぼって探すか
JST = timezone(timedelta(hours=9))


def to_symbol(code: str) -> str:
    """7203 -> 7203.T / ^N225 はそのまま / 8306.T のような指定もそのまま。"""
    code = code.strip()
    if code.startswith("^") or "." in code:
        return code
    return f"{code}.T"


def judge_position(close: float, mas: dict) -> str:
    above = [p for p in PERIODS if mas[p] is not None and close > mas[p]]
    below = [p for p in PERIODS if mas[p] is not None and close < mas[p]]
    if len(above) == 3:
        return "三線すべての上"
    if len(below) == 3:
        return "三線すべての下"
    if len(above) == 2:
        return f"{below[0]}日線だけ下"
    if len(above) == 1:
        return f"{above[0]}日線だけ上"
    return "判定できず"


def judge_order(mas: dict) -> str | None:
    if any(mas[p] is None for p in PERIODS):
        return None
    if mas[5] > mas[25] > mas[75]:
        return "上昇パーフェクトオーダー"
    if mas[5] < mas[25] < mas[75]:
        return "下降パーフェクトオーダー"
    return None


def find_cross(sma_fast, sma_slow, dates) -> dict | None:
    """5日線と25日線の直近のゴールデン/デッドクロスを探す。"""
    n = len(sma_fast)
    start = max(1, n - CROSS_LOOKBACK)
    for i in range(n - 1, start - 1, -1):
        f_now, s_now = sma_fast[i], sma_slow[i]
        f_prev, s_prev = sma_fast[i - 1], sma_slow[i - 1]
        if None in (f_now, s_now, f_prev, s_prev):
            continue
        if f_prev <= s_prev and f_now > s_now:
            return {"type": "ゴールデンクロス", "date": dates[i], "bars_ago": n - 1 - i}
        if f_prev >= s_prev and f_now < s_now:
            return {"type": "デッドクロス", "date": dates[i], "bars_ago": n - 1 - i}
    return None


def sma_series(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= window:
            total -= values[i - window]
        out.append(total / window if i >= window - 1 else None)
    return out


def build_entry(code: str, name: str) -> dict:
    symbol = to_symbol(code)
    hist = yf.Ticker(symbol).history(period="1y", interval="1d", auto_adjust=False)
    hist = hist.dropna(subset=["Close"])
    if len(hist) < max(PERIODS) + 2:
        raise ValueError(f"日足が{len(hist)}本しか取れませんでした（75日線に足りません）")

    closes = [float(v) for v in hist["Close"].tolist()]
    dates = [d.strftime("%Y-%m-%d") for d in hist.index]

    smas = {p: sma_series(closes, p) for p in PERIODS}
    close = closes[-1]
    prev_close = closes[-2]
    mas = {p: smas[p][-1] for p in PERIODS}

    dev = {
        p: round((close - mas[p]) / mas[p] * 100, 2) if mas[p] else None
        for p in PERIODS
    }

    return {
        "code": code,
        "name": name,
        "symbol": symbol,
        "date": dates[-1],
        "close": round(close, 2),
        "change_pct": round((close - prev_close) / prev_close * 100, 2),
        "ma": {str(p): (round(mas[p], 2) if mas[p] else None) for p in PERIODS},
        "dev": {str(p): dev[p] for p in PERIODS},
        "position": judge_position(close, mas),
        "order": judge_order(mas),
        "cross": find_cross(smas[5], smas[25], dates),
        "spark": [round(c, 2) for c in closes[-SPARK_DAYS:]],
    }


def main() -> int:
    watchlist = json.loads(WATCHLIST.read_text(encoding="utf-8"))
    stocks, errors = [], []

    for item in watchlist:
        code, name = item["code"], item.get("name", item["code"])
        try:
            stocks.append(build_entry(code, name))
            print(f"OK   {code} {name}")
        except Exception as e:  # 1銘柄失敗しても全体は止めない
            errors.append({"code": code, "name": name, "message": str(e)})
            print(f"FAIL {code} {name}: {e}", file=sys.stderr)
        time.sleep(1)  # 連続アクセスを避ける

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
                "stocks": stocks,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({len(stocks)} 銘柄 / {len(errors)} 失敗)")
    return 0 if stocks else 1


if __name__ == "__main__":
    raise SystemExit(main())
