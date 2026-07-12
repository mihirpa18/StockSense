import { useEffect, useRef, memo } from 'react'


function TradingViewWidget({ ticker, exchange = 'BSE' }) {
  const containerRef = useRef(null)
  const cleanTicker = (ticker || '').replace('.NS', '').replace('.BO', '')

  console.log('[TradingViewWidget] Props received:', { ticker, cleanTicker, exchange })

  useEffect(() => {
    if (!cleanTicker || !containerRef.current) return

    const symbol = `${exchange}:${cleanTicker}`
    console.log('[TradingViewWidget] Initializing widget with symbol:', symbol)

    // Clean previous widget if re-rendering
    containerRef.current.innerHTML = ''

    // Build the TradingView widget container structure
    const widgetDiv = document.createElement('div')
    widgetDiv.className = 'tradingview-widget-container__widget'
    widgetDiv.style.height = '100%'
    widgetDiv.style.width = '100%'
    containerRef.current.appendChild(widgetDiv)

    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js'
    script.type = 'text/javascript'
    script.async = true
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: symbol,
      interval: 'D',
      timezone: 'Asia/Kolkata',
      theme: 'dark',
      style: '1',
      locale: 'en',
      backgroundColor: '#0a0f1e',
      gridColor: 'rgba(255, 255, 255, 0.06)',
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: false,
      enable_publishing: false,
      allow_symbol_change: false,
      calendar: false,
      support_host: 'https://www.tradingview.com'
    })

    containerRef.current.appendChild(script)

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = ''
      }
    }
  }, [cleanTicker, exchange])

  if (!cleanTicker) {
    return (
      <div className="tradingview-placeholder">
        <span>No chart data available</span>
      </div>
    )
  }

  return (
    <div className="tradingview-outer" key={`${exchange}-${cleanTicker}`}>
      <div
        className="tradingview-widget-container"
        ref={containerRef}
        style={{ height: '100%', width: '100%' }}
      />
    </div>
  )
}

export default memo(TradingViewWidget)
