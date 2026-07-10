import asyncio
from app.services.market_data import fetch_fundamentals
data = fetch_fundamentals("HDFCBANK")
print("Fundamentals Output:")
print(data)
