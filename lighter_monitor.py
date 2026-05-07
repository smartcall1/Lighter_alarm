"""Lighter.xyz 포지션 모니터 — 텔레그램 알림 (Termux용)

Brisbane AEST(UTC+10) 기준 08:00, 12:00, 16:00, 20:00, 00:00 발송
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
WALLET_ADDRESS = os.getenv("LIGHTER_WALLET", "0x0FBeABcaFCf817d47E10a7bCFC15ba194dbD4EEF")

API_BASE = "https://mainnet.zklighter.elliot.ai/api/v1"
HEADERS = {
    "Origin": "https://app.lighter.xyz",
    "Referer": "https://app.lighter.xyz/",
    "User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/131.0.0.0",
}
AEST = timezone(timedelta(hours=10))
SEND_HOURS = [8, 12, 16, 20, 0]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SYMBOL_NAMES = {
    "SKHYNIXUSD": "SK하이닉스",
    "SAMSUNGUSD": "삼성전자",
    "HYUNDAIUSD": "현대차",
    "NVDAUSD": "NVIDIA",
    "TSLAUSD": "Tesla",
    "GOOGLUSD": "Google",
    "MSFTUSD": "Microsoft",
    "AMZNUSD": "Amazon",
    "AAPLUSD": "Apple",
    "AMDUSD": "AMD",
    "METAUSD": "Meta",
    "COINUSD": "Coinbase",
}


async def fetch_account(client: httpx.AsyncClient) -> dict | None:
    url = f"{API_BASE}/account"
    params = {"by": "l1_address", "value": WALLET_ADDRESS}
    try:
        r = await client.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        accounts = r.json().get("accounts", [])
        return accounts[0] if accounts else None
    except Exception as e:
        log.error("API 조회 실패: %s", e)
        return None


def parse_positions(account: dict) -> list[dict]:
    results = []
    for p in account.get("positions", []):
        size = float(p.get("position", "0"))
        if size == 0:
            continue

        symbol = p.get("symbol", "?")
        entry = float(p.get("avg_entry_price", "0"))
        value = float(p.get("position_value", "0"))
        upnl = float(p.get("unrealized_pnl", "0"))
        liq = float(p.get("liquidation_price", "0"))
        margin = float(p.get("allocated_margin", "0"))
        imf = float(p.get("initial_margin_fraction", "0"))
        funding = float(p.get("total_funding_paid_out", "0") or "0")
        side = "Long" if p.get("sign", 1) == 1 else "Short"
        orders = int(p.get("open_order_count", 0))

        current = value / size if size else entry
        pnl_pct = (upnl / (entry * size) * 100) if entry * size else 0
        leverage = round(100 / imf) if imf > 0 else 1
        liq_dist = ((liq - current) / current * 100) if current and liq > 0 else 0

        results.append({
            "symbol": symbol,
            "name": SYMBOL_NAMES.get(symbol, symbol.replace("USD", "")),
            "side": side,
            "size": size,
            "entry": entry,
            "current": current,
            "value": value,
            "upnl": upnl,
            "pnl_pct": pnl_pct,
            "liq": liq,
            "liq_dist": liq_dist,
            "margin": margin,
            "leverage": leverage,
            "funding": funding,
            "orders": orders,
        })
    return sorted(results, key=lambda x: abs(x["value"]), reverse=True)


def fmt_price(v: float) -> str:
    if abs(v) >= 1000:
        return f"${v:,.0f}"
    if abs(v) >= 100:
        return f"${v:,.1f}"
    return f"${v:,.2f}"


def format_message(account: dict, positions: list[dict]) -> str:
    now = datetime.now(AEST).strftime("%m/%d %H:%M")
    balance = float(account.get("available_balance", "0"))
    total_value = float(account.get("total_asset_value", "0"))
    total_upnl = sum(p["upnl"] for p in positions)
    total_margin = sum(p["margin"] for p in positions)

    lines = [f"📡 Lighter — {now} AEST"]

    if not positions:
        lines.append("")
        lines.append("활성 포지션 없음")
    else:
        for p in positions:
            pnl_e = "🟢" if p["upnl"] >= 0 else "🔴"
            d = "📈" if p["side"] == "Long" else "📉"
            lines.append("")
            lines.append(f"{d} {p['name']} {p['side']} ×{p['leverage']}")
            lines.append(f"  수량 {p['size']}주 ({fmt_price(p['value'])})")
            lines.append(
                f"  {fmt_price(p['entry'])} → {fmt_price(p['current'])}"
            )
            lines.append(
                f"  {pnl_e} ${p['upnl']:+,.1f} ({p['pnl_pct']:+.1f}%)"
            )
            lines.append(f"  ⚠️ 청산 {fmt_price(p['liq'])} ({p['liq_dist']:+.0f}%)")
            if p["orders"] > 0:
                lines.append(f"  📋 주문 {p['orders']}건 대기")

    lines.append("")
    lines.append("━" * 20)
    pnl_e = "🟢" if total_upnl >= 0 else "🔴"
    lines.append(f"{pnl_e} 합계 PnL ${total_upnl:+,.1f}")
    lines.append(f"💰 마진 ${total_margin:,.0f} / 가용 ${balance:,.0f}")
    lines.append(f"📊 총 자산 ${total_value:,.0f}")

    shares = account.get("shares", [])
    if shares:
        total_principal = sum(float(s.get("principal_amount", "0")) for s in shares)
        if total_principal > 0:
            lines.append(f"🏦 LP ${total_principal:,.0f} ({len(shares)}풀)")

    return "\n".join(lines)


async def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload, timeout=10)
            if r.status_code != 200:
                log.error("텔레그램 실패: %s %s", r.status_code, r.text[:200])
                payload["parse_mode"] = None
                await client.post(url, json=payload, timeout=10)
            else:
                log.info("텔레그램 전송 완료")
        except Exception as e:
            log.error("텔레그램 에러: %s", e)


async def check_and_notify():
    async with httpx.AsyncClient() as client:
        account = await fetch_account(client)
        if not account:
            return
        positions = parse_positions(account)
        msg = format_message(account, positions)
        log.info("포지션 %d개 → 텔레그램 전송", len(positions))
        await send_telegram(msg)


def seconds_until_next_send() -> int:
    now = datetime.now(AEST)
    for h in sorted(SEND_HOURS):
        target = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if target > now:
            return int((target - now).total_seconds())
    tomorrow_first = now.replace(hour=SEND_HOURS[0], minute=0, second=0, microsecond=0)
    tomorrow_first += timedelta(days=1)
    return int((tomorrow_first - now).total_seconds())


async def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정 (.env 확인)")
        return

    log.info(
        "Lighter 모니터 시작 — 지갑: %s...%s",
        WALLET_ADDRESS[:8], WALLET_ADDRESS[-4:],
    )
    log.info("발송 시각 (AEST): %s", ", ".join(f"{h:02d}:00" for h in sorted(SEND_HOURS)))

    await check_and_notify()

    while True:
        wait = seconds_until_next_send()
        next_time = datetime.now(AEST) + timedelta(seconds=wait)
        log.info("다음 발송: %s (%.1f시간 후)", next_time.strftime("%H:%M AEST"), wait / 3600)
        await asyncio.sleep(wait)
        await check_and_notify()


if __name__ == "__main__":
    asyncio.run(main())
