import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    binance_api_key: str | None = os.getenv("BINANCE_API_KEY")
    binance_api_secret: str | None = os.getenv("BINANCE_API_SECRET")

    # True = use SPOT testnet for trading actions
    use_testnet: bool = os.getenv("USE_TESTNET", "true").lower() in {"1", "true", "yes"}

    default_quote_asset: str = os.getenv("DEFAULT_QUOTE_ASSET", "USDT")
    risk_fraction: float = float(os.getenv("RISK_FRACTION", "0.1"))

    # Backtest defaults
    backtest_symbol: str = os.getenv("BACKTEST_SYMBOL", "BTCUSDT")
    backtest_interval: str = os.getenv("BACKTEST_INTERVAL", "1h")
    backtest_limit: int = int(os.getenv("BACKTEST_LIMIT", "500"))


settings = Settings() 