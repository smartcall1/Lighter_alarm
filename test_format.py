"""메시지 포맷 테스트"""
import asyncio
import httpx
from lighter_monitor import fetch_account, parse_positions, format_message


async def test():
    async with httpx.AsyncClient() as client:
        acct = await fetch_account(client)
        if not acct:
            print("FAIL: no account")
            return
        positions = parse_positions(acct)
        msg = format_message(acct, positions)
        print(msg)
        print(f"\n--- {len(msg)} chars ---")


if __name__ == "__main__":
    asyncio.run(test())
