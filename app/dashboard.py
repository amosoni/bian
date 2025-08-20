import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objs as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.append(str(ROOT))

from src.exchange.binance_futures_client import BinanceUSDMClient
from src.data.market_data import fetch_futures_klines_df
from src.strategy.ema_cross import add_ema_features
from src.backtest.backtester import run_backtest
from src.strategy.indicators import compute_bollinger_bands

st.set_page_config(page_title="币安USDM合约 · EMA金叉看板", layout="wide")
st.title("币安 USDM 合约 · EMA 金叉看板")

with st.sidebar:
	st.header("设置")
	symbol = st.text_input("交易对", value=os.getenv("BACKTEST_SYMBOL", "ETHUSDT"))
	interval = st.selectbox(
		"周期",
		["1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d"],
		index=5,
	)
	limit = st.slider("K线数量", min_value=100, max_value=1000, value=int(os.getenv("BACKTEST_LIMIT", 300)))
	fast = st.number_input("EMA 快线", min_value=2, max_value=200, value=12, step=1)
	slow = st.number_input("EMA 慢线", min_value=3, max_value=400, value=26, step=1)
	bb_period = st.number_input("布林带周期", min_value=5, max_value=200, value=20, step=1)
	bb_mult = st.number_input("布林带倍数", min_value=1.0, max_value=4.0, value=2.0, step=0.1, format="%.1f")
	leverage = st.number_input("杠杆", min_value=1, max_value=125, value=5, step=1)
	quote_size = st.number_input("每次名义资金(USDT)", min_value=5.0, max_value=100000.0, value=50.0, step=5.0)
	use_testnet = st.checkbox("使用测试网", value=os.getenv("USE_TESTNET", "true").lower() in {"1","true","yes"})
	base_url = st.text_input("期货公共域名 (public)", value=os.getenv("BINANCE_FAPI_BASE_URL", "https://fapi1.binance.com"))
	api_key = st.text_input("API Key（可选，交易必填）", value=os.getenv("BINANCE_API_KEY", ""))
	api_secret = st.text_input("API Secret（可选，交易必填）", value=os.getenv("BINANCE_API_SECRET", ""), type="password")
	market_only = st.checkbox("仅展示行情", value=True)
	auto_refresh = st.checkbox("自动刷新", value=True)
	refresh_seconds = st.number_input("刷新间隔(秒)", min_value=2, max_value=60, value=5, step=1)

# 自动刷新（无需点击运行）
if auto_refresh:
	st_autorefresh(interval=int(refresh_seconds * 1000), key="auto_tick")

# 关闭顶部交易按钮（改为底部交易面板）
open_long = False
close_long = False

# 始终渲染行情与图表
os.environ["BINANCE_FAPI_BASE_URL"] = base_url
client = BinanceUSDMClient(api_key=api_key or None, api_secret=api_secret or None, use_testnet=use_testnet)

try:
	# 自动退避：在 429 时逐步降低 limit 并重试
	cur_limit = int(limit)
	last_err: Exception | None = None
	for _ in range(3):
		try:
			df: pd.DataFrame = fetch_futures_klines_df(client, symbol, interval, limit=cur_limit)
			break
		except Exception as e:  # noqa: BLE001
			last_err = e
			msg = str(e)
			if "429" in msg or "Too Many Requests" in msg:
				cur_limit = max(100, int(cur_limit * 0.6))
				st.info(f"命中限流，自动将K线数量降至 {cur_limit} 并重试……")
				continue
			else:
				raise
	else:
		raise last_err if last_err else RuntimeError("拉取失败")

	if df is None or df.empty:
		st.warning("未获取到K线数据。请更换公共域名、减小K线数量或检查网络/代理。")
		raise SystemExit
	feat = add_ema_features(df, fast=fast, slow=slow).dropna()
	feat = compute_bollinger_bands(feat, period=int(bb_period), std_multiplier=float(bb_mult))

	# 仅行情模式下不跑回测，直接画图
	stats = None
	if not market_only:
		res = run_backtest(df, fast=fast, slow=slow)
		stats = res["stats"]

	if stats is not None:
		st.subheader("回测统计")
		col1, col2, col3, col4 = st.columns(4)
		col1.metric("收益率", f"{stats['return_pct']:.2f}%")
		col2.metric("最大回撤", f"{stats['max_dd_pct']:.2f}%")
		col3.metric("夏普比率", f"{stats['sharpe']:.2f}")
		col4.metric("交易次数", f"{stats['trades']}")

	fig = go.Figure()
	# 蜡烛图使用原始 df，保证总能显示
	fig.add_trace(go.Candlestick(
		x=df.index,
		open=df["open"], high=df["high"], low=df["low"], close=df["close"],
		name=symbol
	))
	# 指标叠加（使用已对齐的 feat）
	if not feat.empty:
		fig.add_trace(go.Scatter(x=feat.index, y=feat[f"ema_{fast}"], line=dict(color="#2ca02c"), name=f"EMA {fast}"))
		fig.add_trace(go.Scatter(x=feat.index, y=feat[f"ema_{slow}"], line=dict(color="#d62728"), name=f"EMA {slow}"))
		fig.add_trace(go.Scatter(x=feat.index, y=feat["bb_mid"], line=dict(color="#9467bd", width=1), name="BB Mid"))
		fig.add_trace(go.Scatter(x=feat.index, y=feat["bb_upper"], line=dict(color="#8c564b", width=1), name="BB Upper"))
		fig.add_trace(go.Scatter(x=feat.index, y=feat["bb_lower"], line=dict(color="#8c564b", width=1), name="BB Lower", fill=None))

	fig.update_layout(height=700, xaxis_rangeslider_visible=False)
	st.plotly_chart(fig, use_container_width=True)

	# 仅行情模式下显示成交量；使用原始 df
	fig_vol = go.Figure()
	fig_vol.add_trace(go.Bar(x=df.index, y=df["volume"], name="成交量", marker_color="#888"))
	fig_vol.update_layout(height=250)
	st.plotly_chart(fig_vol, use_container_width=True)

	if not market_only:
		# %B subplot（若有feat）
		if not feat.empty:
			fig_pb = go.Figure()
			fig_pb.add_trace(go.Scatter(x=feat.index, y=feat["bb_percent_b"], mode="lines", name="%B", line=dict(color="#17becf")))
			fig_pb.update_layout(height=200)
			st.plotly_chart(fig_pb, use_container_width=True)

		# 风控图
		res = res if 'res' in locals() else run_backtest(df, fast=fast, slow=slow)
		ec = res["equity_curve"].copy()
		dd = (ec / ec.cummax()) - 1.0
		st.subheader("趋势与风控图表")
		c1, c2 = st.columns(2)
		with c1:
			fig_eq = go.Figure()
			fig_eq.add_trace(go.Scatter(x=ec.index, y=ec.values, mode="lines", name="权益曲线", line=dict(color="#1f77b4")))
			fig_eq.update_layout(height=300)
			st.plotly_chart(fig_eq, use_container_width=True)
		with c2:
			fig_dd = go.Figure()
			fig_dd.add_trace(go.Scatter(x=dd.index, y=dd.values, mode="lines", name="回撤(%)", fill="tozeroy", line=dict(color="#ff7f0e")))
			fig_dd.update_layout(height=300, yaxis_tickformat=",.0%")
			st.plotly_chart(fig_dd, use_container_width=True)

		# ===== 底部交易面板 =====
		st.divider()
		st.subheader("交易面板")
		last_price = float(df["close"].iloc[-1])
		qty_preview = (quote_size * leverage) / max(last_price, 1e-9)
		m1, m2, m3 = st.columns(3)
		m1.metric("最新价", f"{last_price:.4f}")
		m2.metric("杠杆", str(int(leverage)))
		m3.metric("预计下单数量", f"{qty_preview:.6f}")

		b1, b2 = st.columns(2)
		with b1:
			btn_open = st.button("开多 (市价)")
		with b2:
			btn_close = st.button("平多 (reduceOnly)")

		if btn_open or btn_close:
			if not api_key or not api_secret:
				st.error("请在侧栏填写 API Key/Secret 后再下单。")
			else:
				# 设置杠杆
				try:
					client.change_leverage(symbol, int(leverage))
				except Exception as e:
					st.warning(f"设置杠杆失败：{e}")

				from decimal import Decimal
				filters = client.get_symbol_filters(symbol)
				if btn_open:
					qty = client.round_to_step(Decimal(str(qty_preview)), filters.lot_step_size)
					try:
						res_order = client.new_market_order(symbol=symbol, side="BUY", quantity=qty)
						st.success(f"已开多：订单ID {res_order.get('orderId')}")
					except Exception as e:
						st.error(f"开多失败：{e}")
				if btn_close:
					qty = filters.lot_min_qty
					try:
						res_order = client.new_market_order(symbol=symbol, side="SELL", quantity=qty, reduce_only=True)
						st.success(f"已平多（reduceOnly）：订单ID {res_order.get('orderId')}")
					except Exception as e:
						st.error(f"平多失败：{e}")

except Exception as e:
	st.error(f"错误：{e}")
	st.info("如果连接超时，请在侧边栏更换公共域名、开启代理或减少K线数量。") 