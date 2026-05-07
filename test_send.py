"""텔레그램 전송 테스트"""
import asyncio
from lighter_monitor import check_and_notify


if __name__ == "__main__":
    asyncio.run(check_and_notify())
