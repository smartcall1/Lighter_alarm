"""메시지 포맷 테스트 (풀 메타데이터 포함)"""
import asyncio
import httpx
from lighter_monitor import (
    fetch_account, fetch_pool_meta, parse_positions, format_message, HEADERS, API_BASE,
)


async def test():
    async with httpx.AsyncClient() as client:
        acct = await fetch_account(client)
        if not acct:
            print("FAIL: no account")
            return

        pool_details = []
        for s in acct.get("shares", []):
            principal = float(s.get("principal_amount", "0"))
            if principal == 0:
                continue
            pool_idx = s.get("public_pool_index", 0)
            meta = await fetch_pool_meta(client, pool_idx)
            name = (meta.get("name") or "Unknown Pool") if meta else f"Pool #{pool_idx & 0xFFFF}"
            apy = float(meta["annual_percentage_yield"]) if meta and meta.get("annual_percentage_yield") else None
            tav = float(meta["total_asset_value"]) if meta and meta.get("total_asset_value") else 0
            pool_details.append({"name": name, "principal": principal, "apy": apy, "tav": tav})
        acct["_pool_details"] = sorted(pool_details, key=lambda x: x["principal"], reverse=True)

        positions = parse_positions(acct)
        msg = format_message(acct, positions)
        print(msg)
        print(f"\n--- {len(msg)} chars ---")


if __name__ == "__main__":
    asyncio.run(test())
