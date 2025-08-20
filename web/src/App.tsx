import { useEffect, useRef, useState } from 'react'
import { createChart, ISeriesApi, UTCTimestamp } from 'lightweight-charts'

const WS_BASE = 'wss://fstream.binance.com/ws'

type Candle = { time: UTCTimestamp; open: number; high: number; low: number; close: number }

function generateMock(from: number, bars = 300): Candle[] {
  const out: Candle[] = []
  let price = 3000
  for (let i = 0; i < bars; i++) {
    const t = (from + i * 60) as UTCTimestamp
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
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    const connect = () => {
      const stream = `${symbol.toLowerCase()}@kline_${interval}`
      const ws = new WebSocket(`${WS_BASE}/${stream}`)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        console.log('WebSocket已连接，开始接收实时数据')
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
        
        console.log(`收到实时K线: 时间=${new Date(p.time * 1000).toLocaleTimeString()}, 价格=${p.close}`)
        
        // 更新最新价格和涨跌幅
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

      ws.onclose = () => {
        setIsConnected(false)
        console.log('WebSocket连接断开，3秒后重连...')
        // 自动重连
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = setTimeout(connect, 3000)
      }

      ws.onerror = (error) => {
        console.error('WebSocket连接错误:', error)
        setIsConnected(false)
      }

      return ws
    }

    const ws = connect()

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      if (ws.readyState === WebSocket.OPEN) ws.close()
    }
  }, [symbol, interval])

  return { points, lastPrice, priceChange, isConnected }
}

export default function App() {
  const symbol = 'ETHUSDT'
  const interval = '1m'
  const { points: data, lastPrice, priceChange, isConnected } = useKline(symbol, interval)
  const ref = useRef<HTMLDivElement>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'>>()

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
    
    console.log('图表创建完成，添加K线系列...')
    const s = chart.addCandlestickSeries({ upColor: '#26a69a', downColor: '#ef5350', wickUpColor: '#26a69a', wickDownColor: '#ef5350', borderVisible: false })
    seriesRef.current = s
    console.log('K线系列添加完成')

    let cancelled = false
    ;(async () => {
      // 等待图表完全初始化
      await new Promise(resolve => setTimeout(resolve, 100))
      
      console.log('开始获取历史K线数据...')
      const bases = ['/fapi1', '/fapi2', '/fapi3', '/fapi4']
      let ok = false
      
      // 设置请求超时
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5000) // 5秒超时
      
      for (const base of bases) {
        try {
          console.log(`尝试从 ${base} 获取数据...`)
          const res = await fetch(`${base}/fapi/v1/klines?symbol=${symbol}&interval=${interval}&limit=500`, { 
            cache: 'no-store',
            signal: controller.signal
          })
          if (!res.ok) {
            console.log(`${base} 响应状态: ${res.status}`)
            continue
          }
          const raw = await res.json()
          if (cancelled) return
          console.log(`从 ${base} 获取到 ${raw.length} 条K线数据`)
          const hist: Candle[] = raw.map((r: any[]) => ({
            time: (r[0] / 1000) as UTCTimestamp,
            open: parseFloat(r[1]),
            high: parseFloat(r[2]),
            low: parseFloat(r[3]),
            close: parseFloat(r[4]),
          }))
          
          if (!cancelled && seriesRef.current) {
            console.log('设置历史数据到图表...')
            seriesRef.current.setData(hist as any)
            ok = true
            console.log('历史数据设置成功')
            break
          }
        } catch (error: any) {
          if (error.name === 'AbortError') {
            console.log(`${base} 请求超时`)
          } else {
            console.log(`${base} 请求失败:`, error)
          }
          continue
        }
      }
      
      clearTimeout(timeoutId)
      
      if (!ok && !cancelled) {
        console.log('所有REST端点都失败，使用模拟数据兜底')
        // 离线兜底：生成模拟K线，确保界面有图
        const now = Math.floor(Date.now() / 1000)
        const mockData = generateMock(now - 60 * 500)
        console.log(`生成 ${mockData.length} 条模拟K线数据`)
        
        if (!cancelled && seriesRef.current) {
          seriesRef.current.setData(mockData as any)
          console.log('模拟数据设置成功')
        }
      }
    })()

    const ro = new ResizeObserver(() => chart.applyOptions({ width: ref.current!.clientWidth }))
    ro.observe(ref.current)
    return () => { cancelled = true; ro.disconnect(); chart.remove() }
  }, [])

  useEffect(() => {
    if (seriesRef.current && data.length) {
      try {
        console.log(`更新图表，最新K线: 时间=${new Date(data[data.length - 1].time * 1000).toLocaleTimeString()}, 价格=${data[data.length - 1].close}`)
        seriesRef.current.update(data[data.length - 1] as any)
      } catch (error) {
        console.error('图表更新失败:', error)
      }
    }
  }, [data])

  return (
    <div className="page">
      <header className="bar">
        <div className="logo">Futures Pro</div>
        <div className="pair">
          {symbol} · {interval}
          <span className={`status ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '●' : '○'}
          </span>
        </div>
        <div className="price-info">
          <span className="price">${lastPrice.toFixed(2)}</span>
          <span className={`change ${priceChange >= 0 ? 'positive' : 'negative'}`}>
            {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}
          </span>
        </div>
      </header>
      <main className="grid">
        <section className="panel chart" ref={ref} />
        <aside className="panel orderbook">盘口（开发中）</aside>
        <aside className="panel trades">成交（开发中）</aside>
        <section className="panel controls">下单面板（开发中）：市价/限价、杠杆、数量、reduceOnly</section>
      </main>
    </div>
  )
} 