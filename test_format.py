"""메시지 포맷 테스트 (equity 포함)"""
import asyncio
import httpx
from lighter_monitor import (
    fetch_account, fetch_pool_meta, parse_positions, format_message,
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
            my_shares = int(s.get("shares_amount", 0))
            meta = await fetch_pool_meta(client, pool_idx)
            name = (meta.get("name") or "$LIT Staking") if meta else "$LIT Staking"
            apy = float(meta["annual_percentage_yield"]) if meta and meta.get("annual_percentage_yield") else None
            tav = float(meta["total_asset_value"]) if meta and meta.get("total_asset_value") else 0
            total_shares = int(meta.get("total_shares", 0)) if meta else 0
            equity = (my_shares / total_shares) * tav if total_shares else principal
            lp_pnl = equity - principal if principal else 0
            pool_details.append({"name": name, "principal": principal, "equity": equity, "lp_pnl": lp_pnl, "apy": apy})
        acct["_pool_details"] = sorted(pool_details, key=lambda x: x["equity"], reverse=True)

        positions = parse_positions(acct)
        msg = format_message(acct, positions)
        print(msg)
        print(f"\n--- {len(msg)} chars ---")


if __name__ == "__main__":
    asyncio.run(test())
