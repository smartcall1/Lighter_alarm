"""메시지 포맷 테스트 (equity 포함)"""
import asyncio
import httpx
from lighter_monitor import (
    fetch_account, fetch_pool_meta, fetch_lit_price, parse_positions, format_message,
)


async def test():
    async with httpx.AsyncClient() as client:
        acct = await fetch_account(client)
        if not acct:
            print("FAIL: no account")
            return

        lit_price = await fetch_lit_price(client)
        print(f"$LIT price: ${lit_price}" if lit_price else "$LIT price: N/A")

        pool_details = []
        for s in acct.get("shares", []):
            principal = float(s.get("principal_amount", "0"))
            if principal == 0:
                continue
            pool_idx = s.get("public_pool_index", 0)
            my_shares = int(s.get("shares_amount", 0))
            entry_usdc = s.get("entry_usdc", "0")
            meta = await fetch_pool_meta(client, pool_idx)
            name = (meta.get("name") or "$LIT Staking") if meta else "$LIT Staking"
            apy = float(meta["annual_percentage_yield"]) if meta and meta.get("annual_percentage_yield") else None
            tav = float(meta["total_asset_value"]) if meta and meta.get("total_asset_value") else 0
            total_shares = int(meta.get("total_shares", 0)) if meta else 0

            is_lit_staking = entry_usdc == "0" and not meta
            if is_lit_staking and lit_price:
                equity = principal * lit_price
            elif total_shares:
                equity = (my_shares / total_shares) * tav
            else:
                equity = principal
            lp_pnl = equity - principal if principal else 0
            lit_tag = f" @${lit_price:.2f}" if is_lit_staking and lit_price else ""
            pool_details.append({"name": name, "principal": principal, "equity": equity, "lp_pnl": lp_pnl, "apy": apy, "lit_tag": lit_tag})
        acct["_pool_details"] = sorted(pool_details, key=lambda x: x["equity"], reverse=True)

        positions = parse_positions(acct)
        msg = format_message(acct, positions)
        print(msg)
        print(f"\n--- {len(msg)} chars ---")


if __name__ == "__main__":
    asyncio.run(test())
