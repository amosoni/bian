# Binance Quant Trading (EMA Crossover)

A minimal, extensible framework for Binance Spot testnet trading with an EMA crossover strategy. Includes data fetching, backtesting, risk management, and live execution (testnet by default).

## Quickstart (Windows PowerShell)

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env and add your API key/secret (testnet keys)

# Run a backtest
python -m src.main backtest --symbol BTCUSDT --interval 1h --limit 500 --fast 12 --slow 26

# Dry-run paper trading (no orders sent)
python -m src.main paper --symbol BTCUSDT --interval 1h --fast 12 --slow 26

# Live testnet trading (orders sent to testnet). Ensure USE_TESTNET=true and keys provided.
python -m src.main live --symbol BTCUSDT --interval 1h --fast 12 --slow 26 --quote 50
```

## Safety
- Testnet is enabled by default. Live trading requires explicit `live` command and valid keys.
- Uses `quoteOrderQty` by default for market orders to control max spend per trade.

## Structure
```
src/
  main.py
  config.py
  exchange/binance_client.py
  data/market_data.py
  strategy/ema_cross.py
  backtest/backtester.py
  risk/risk_manager.py
  live/trader.py
```

## Notes
- Backtests fetch public historical klines from mainnet API (no key required).
- Live/testnet trading uses your API keys; keep them secure and never commit `.env`. 

## USDM Futures (合约)

```powershell
# 测试网回测（期货K线）
python -m src.main futures-backtest --symbol BTCUSDT --interval 1h --limit 300 --fast 12 --slow 26

# 纸面（不下单）
python -m src.main futures-paper --symbol BTCUSDT --interval 1h --fast 12 --slow 26 --leverage 5

# 测试网下单（需在 .env 填入 KEY，且 USE_TESTNET=true）
python -m src.main futures-live --symbol BTCUSDT --interval 1h --fast 12 --slow 26 --leverage 5
```

- 可通过环境变量 `BINANCE_FAPI_BASE_URL` 指定备用域名，例如 `https://fapi1.binance.com` 以规避网络超时。
- 变更与限速参考官方衍生品变更日志：[Derivatives Change Log](https://developers.binance.com/docs/derivatives/change-log) 

## 查看可视化页面（Dashboard）

```powershell
# 安装依赖
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 启动可视化页面
streamlit run app\dashboard.py
```

- 浏览器会自动打开本地页面（若未自动打开，访问 `http://localhost:8501`）。
- 如网络到 Binance 接口超时，可在侧边栏填写 `Futures Base URL` 为 `https://fapi1.binance.com` 或配置系统代理。 