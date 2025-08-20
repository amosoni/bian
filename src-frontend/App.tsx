import { useEffect, useRef, useState } from 'react'
import { createChart, ISeriesApi, UTCTimestamp, LineData } from 'lightweight-charts'

const WS_BASES = ['wss://fstream.binance.com/ws', 'wss://stream.binancefuture.com/ws']

type Candle = { time: UTCTimestamp; open: number; high: number; low: number; close: number }

function generateMock(from: number, interval: string, bars = 300): Candle[] {
	const out: Candle[] = []
	let price = 3000
	let timeStep = 60
	if (interval === '1s') timeStep = 1
	else if (interval === '5m') timeStep = 300
	else if (interval === '15m') timeStep = 900
	else if (interval === '1h') timeStep = 3600
	else if (interval === '4h') timeStep = 14400
	else if (interval === '1d') timeStep = 86400
	else if (interval === '1w') timeStep = 604800
	for (let i = 0; i < bars; i++) {
		const t = (from + i * timeStep) as UTCTimestamp
		const drift = Math.sin(i / 20) * 10 + (Math.random() - 0.5) * 5
		const open = price
		const close = Math.max(1, open + drift)
		const high = Math.max(open, close) + Math.random() * 5
		const low = Math.min(open, close) - Math.random() * 5
		out.push({ time: t, open, high, low, close })
		price = close
	}
	return out
}

function useKline(symbol: string, interval: string) {
	const [points, setPoints] = useState<Candle[]>([])
	const [lastPrice, setLastPrice] = useState<number>(0)
	const [priceChange, setPriceChange] = useState<number>(0)
	const [isConnected, setIsConnected] = useState<boolean>(false)
	const reconnectTimeoutRef = useRef<number | null>(null)
	const baseIdxRef = useRef<number>(0)

	useEffect(() => {
		const openSocket = () => {
			const base = WS_BASES[baseIdxRef.current % WS_BASES.length]
			const stream = `${symbol.toLowerCase()}@kline_${interval}`
			const url = `${base}/${stream}`
			console.log('WS 连接尝试:', url)
			const ws = new WebSocket(url)

			ws.onopen = () => {
				setIsConnected(true)
				console.log('WebSocket已连接:', url)
			}

			ws.onmessage = (ev) => {
				const data = JSON.parse(ev.data)
				const k = data.k
				const p: Candle = {
					time: Math.floor(k.t / 1000) as UTCTimestamp,
					open: parseFloat(k.o),
					high: parseFloat(k.h),
					low: parseFloat(k.l),
					close: parseFloat(k.c),
				}
				setLastPrice(p.close)
				setPoints((prev) => {
					if (prev.length > 0) {
						const prevClose = prev[prev.length - 1].close
						setPriceChange(p.close - prevClose)
					}
					const last = prev[prev.length - 1]
					if (last && last.time === p.time) {
						const copy = prev.slice()
						copy[copy.length - 1] = p
						return copy
					}
					return [...prev.slice(-999), p]
				})
			}

			const scheduleNext = () => {
				setIsConnected(false)
				baseIdxRef.current = (baseIdxRef.current + 1) % WS_BASES.length
				console.log('WS 断开，3秒后切换到下一个域名重试。下次索引:', baseIdxRef.current)
				if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
				reconnectTimeoutRef.current = setTimeout(openSocket, 3000)
			}

			ws.onclose = scheduleNext
			ws.onerror = scheduleNext

			return ws
		}

		const ws = openSocket()
		return () => {
			if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
			if (ws && ws.readyState === WebSocket.OPEN) ws.close()
		}
	}, [symbol, interval])

	return { points, lastPrice, priceChange, isConnected }
}

function computeBollingerBands(candles: Candle[], period: number, mult: number) {
	const upper: LineData[] = []
	const mid: LineData[] = []
	const lower: LineData[] = []
	if (!candles.length) return { upper, mid, lower }
	let sum = 0
	let sumSq = 0
	for (let i = 0; i < candles.length; i++) {
		const c = candles[i].close
		sum += c
		sumSq += c * c
		if (i >= period) {
			const drop = candles[i - period].close
			sum -= drop
			sumSq -= drop * drop
		}
		if (i >= period - 1) {
			const mean = sum / period
			const variance = Math.max(0, sumSq / period - mean * mean)
			const sd = Math.sqrt(variance)
			mid.push({ time: candles[i].time, value: mean })
			upper.push({ time: candles[i].time, value: mean + mult * sd })
			lower.push({ time: candles[i].time, value: mean - mult * sd })
		}
	}
	return { upper, mid, lower }
}

export default function App() {
	const symbol = 'ETHUSDT'
	const [currentInterval, setCurrentInterval] = useState('1m')
	const { points: data, lastPrice, priceChange, isConnected } = useKline(symbol, currentInterval)
	const ref = useRef<HTMLDivElement>(null)
	const seriesRef = useRef<ISeriesApi<'Candlestick'>>()
	const bbUpperRef = useRef<ISeriesApi<'Line'>>()
	const bbMidRef = useRef<ISeriesApi<'Line'>>()
	const bbLowerRef = useRef<ISeriesApi<'Line'>>()
	const showBB = true
	const [bbPeriod, setBbPeriod] = useState(20)
	const [bbMult, setBbMult] = useState(2)

	const timeframes = [
		{ key: '1s', label: '1秒', interval: '1s' },
		{ key: '1m', label: '1分钟', interval: '1m' },
		{ key: '5m', label: '5分钟', interval: '5m' },
		{ key: '15m', label: '15分钟', interval: '15m' },
		{ key: '1h', label: '1小时', interval: '1h' },
		{ key: '4h', label: '4小时', interval: '4h' },
		{ key: '1d', label: '1天', interval: '1d' },
		{ key: '1w', label: '1周', interval: '1w' },
	]

	const handleTimeframeChange = (newInterval: string) => {
		setCurrentInterval(newInterval)
		console.log(`切换到时间周期: ${newInterval}`)
	}

	useEffect(() => {
		if (!ref.current) return
		console.log('开始创建图表...')
		const chart = createChart(ref.current, {
			rightPriceScale: { borderVisible: false },
			timeScale: { borderVisible: false },
			layout: { background: { color: '#0f1115' }, textColor: '#ddd' },
			grid: { horzLines: { color: '#1b1e26' }, vertLines: { color: '#1b1e26' } },
			height: 520,
			width: ref.current.clientWidth,
		})
		const s = chart.addCandlestickSeries({ upColor: '#26a69a', downColor: '#ef5350', wickUpColor: '#26a69a', wickDownColor: '#ef5350', borderVisible: false })
		seriesRef.current = s
		bbUpperRef.current = chart.addLineSeries({ color: '#a78bfa', lineWidth: 1 })
		bbMidRef.current = chart.addLineSeries({ color: '#94a3b8', lineWidth: 1 })
		bbLowerRef.current = chart.addLineSeries({ color: '#a78bfa', lineWidth: 1 })

		let cancelled = false
		;(async () => {
			await new Promise((r) => setTimeout(r, 100))
			console.log(`开始获取历史K线数据，时间周期: ${currentInterval}...`)
			const bases = [
				'https://fapi1.binance.com',
				'https://fapi2.binance.com',
				'https://fapi3.binance.com',
				'https://fapi4.binance.com',
				'https://testnet.binancefuture.com',
			]
			let ok = false
			let usedBase = ''
			const controller = new AbortController()
			const timeoutId = setTimeout(() => controller.abort(), 7000)
			for (const base of bases) {
				try {
					console.log(`尝试从 ${base} 获取数据...`)
					const res = await fetch(`${base}/fapi/v1/klines?symbol=${symbol}&interval=${currentInterval}&limit=500`, { cache: 'no-store', signal: controller.signal })
					if (!res.ok) { console.log(`${base} 响应状态: ${res.status}`); continue }
					const raw = await res.json()
					if (cancelled) return
					const hist: Candle[] = raw.map((r: any[]) => ({ time: (r[0] / 1000) as UTCTimestamp, open: parseFloat(r[1]), high: parseFloat(r[2]), low: parseFloat(r[3]), close: parseFloat(r[4]) }))
					seriesRef.current?.setData(hist as any)
					if (showBB) {
						const bb = computeBollingerBands(hist, bbPeriod, bbMult)
						bbUpperRef.current?.setData(bb.upper)
						bbMidRef.current?.setData(bb.mid)
						bbLowerRef.current?.setData(bb.lower)
					} else {
						bbUpperRef.current?.setData([])
						bbMidRef.current?.setData([])
						bbLowerRef.current?.setData([])
					}
					ok = true
					usedBase = base
					break
				} catch (e: any) {
					console.log(`${base} 请求失败:`, e)
					continue
				}
			}
			clearTimeout(timeoutId)
			if (!ok && !cancelled) {
				console.log('所有REST端点都失败，使用模拟数据兜底')
				const now = Math.floor(Date.now() / 1000)
				const mockData = generateMock(now - 60 * 500, currentInterval)
				seriesRef.current?.setData(mockData as any)
				if (showBB) {
					const bb = computeBollingerBands(mockData, bbPeriod, bbMult)
					bbUpperRef.current?.setData(bb.upper)
					bbMidRef.current?.setData(bb.mid)
					bbLowerRef.current?.setData(bb.lower)
				} else {
					bbUpperRef.current?.setData([])
					bbMidRef.current?.setData([])
					bbLowerRef.current?.setData([])
				}
				const badge = document.createElement('div')
				badge.textContent = '模拟数据 (REST不可达)'
				badge.style.position = 'absolute'
				badge.style.left = '16px'
				badge.style.top = '8px'
				badge.style.background = 'rgba(239,83,80,0.2)'
				badge.style.color = '#ef5350'
				badge.style.padding = '4px 8px'
				badge.style.borderRadius = '4px'
				badge.style.fontSize = '12px'
				badge.style.zIndex = '10'
				const container = ref.current?.parentElement
				if (container) container.appendChild(badge)
			} else {
				const container = ref.current?.parentElement
				const tagList = container?.querySelectorAll('div') || []
				tagList.forEach((n) => { if (n.textContent === '模拟数据 (REST不可达)') n.remove() })
				console.log(`K线来源: ${usedBase.includes('testnet') ? 'Binance Futures Testnet' : 'Binance Futures Prod'}`)
			}
		})()

		const ro = new ResizeObserver(() => chart.applyOptions({ width: ref.current!.clientWidth }))
		ro.observe(ref.current)
		return () => { cancelled = true; ro.disconnect(); chart.remove() }
	}, [currentInterval, bbPeriod, bbMult])

	// 实时增量更新 + BB尾点同步
	useEffect(() => {
		if (!seriesRef.current || !data.length) return
		seriesRef.current.update(data[data.length - 1] as any)
		if (showBB && data.length >= bbPeriod) {
			const tail = data.slice(-(bbPeriod))
			const bb = computeBollingerBands(tail, bbPeriod, bbMult)
			const lastIdx = bb.mid.length - 1
			if (lastIdx >= 0) {
				bbUpperRef.current?.update(bb.upper[lastIdx])
				bbMidRef.current?.update(bb.mid[lastIdx])
				bbLowerRef.current?.update(bb.lower[lastIdx])
			}
		}
	}, [data, bbPeriod, bbMult])

	const priceChangePercent = lastPrice > 0 ? (priceChange / (lastPrice - priceChange)) * 100 : 0

	return (
		<div className="page">
			<header className="top-bar">
				<div className="price-info">
					<div className="symbol">ETHUSDT</div>
					<div className="price">${lastPrice.toFixed(2)}</div>
					<div className={`change ${priceChange >= 0 ? 'positive' : 'negative'}`}>
						{priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)} ({priceChangePercent.toFixed(2)}%)
					</div>
				</div>
				<div className="market-info">
					<div className="info-item"><span className="label">标记价格</span><span className="value">${(lastPrice * 0.9999).toFixed(2)}</span></div>
					<div className="info-item"><span className="label">资金费率</span><span className="value">0.0009%</span></div>
					<div className="info-item"><span className="label">倒计时</span><span className="value">01:25:07</span></div>
				</div>
				<div className="connection-status">
					<span className={`status ${isConnected ? 'connected' : 'disconnected'}`}>{isConnected ? '●' : '○'}</span>
					<span className="status-text">{isConnected ? '已连接' : '未连接'}</span>
				</div>
			</header>

			<div className="chart-controls">
				<div className="timeframe-selector">
					{timeframes.map(tf => (
						<button key={tf.key} className={`timeframe-btn ${currentInterval === tf.interval ? 'active' : ''}`} onClick={() => handleTimeframeChange(tf.interval)}>
							{tf.label}
						</button>
					))}
				</div>

			</div>

			<main className="grid">
				<section className="panel chart" ref={ref} />
				<aside className="panel orderbook">
					<h3>盘口</h3>
					<div className="orderbook-content">
						<div className="sell-orders">
							<div className="order-row sell"><span className="price">${(lastPrice * 1.001).toFixed(2)}</span><span className="quantity">12.5</span></div>
							<div className="order-row sell"><span className="price">${(lastPrice * 1.002).toFixed(2)}</span><span className="quantity">8.3</span></div>
						</div>
						<div className="current-price">${lastPrice.toFixed(2)}</div>
						<div className="buy-orders">
							<div className="order-row buy"><span className="price">${(lastPrice * 0.999).toFixed(2)}</span><span className="quantity">15.2</span></div>
							<div className="order-row buy"><span className="price">${(lastPrice * 0.998).toFixed(2)}</span><span className="quantity">9.7</span></div>
						</div>
					</div>
				</aside>
				<aside className="panel trades">
					<h3>最新成交</h3>
					<div className="trades-content">
						<div className="trade-row buy">${lastPrice.toFixed(2)} 2.5</div>
						<div className="trade-row sell">${(lastPrice * 0.999).toFixed(2)} 1.8</div>
						<div className="trade-row buy">${(lastPrice * 1.001).toFixed(2)} 3.2</div>
					</div>
				</aside>
				<section className="panel controls">
					<div className="trading-controls">
						<div className="control-group"><label>杠杆</label><select defaultValue="10"><option value="1">1x</option><option value="5">5x</option><option value="10">10x</option><option value="20">20x</option></select></div>
						<div className="control-group"><label>数量</label><input type="number" placeholder="0.00" step="0.01" /></div>
						<div className="control-group"><label>价格</label><input type="number" placeholder="市价" step="0.01" /></div>
					</div>
					<div className="trading-buttons">
						<button className="btn-buy">买入/做多</button>
						<button className="btn-sell">卖出/做空</button>
					</div>
				</section>
			</main>
		</div>
	)
} 