import { useEffect, useRef } from 'react'

// A quiet instrument-panel backdrop: a faint technical grid with a handful of
// slow-drifting glow traces, like sparklines ticking across a dark terminal.
export const LiquidBackground = () => {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    let width, height, dpr
    let animId

    const ACCENT = [62, 142, 255]   // matches --accent
    const GRID_SPACING = 46

    const traces = Array.from({ length: 4 }, (_, i) => ({
      baseY: 0.15 + i * 0.24 + Math.random() * 0.05,
      amp: 26 + Math.random() * 34,
      freq1: 0.0016 + Math.random() * 0.0012,
      freq2: 0.004 + Math.random() * 0.003,
      speed: 0.00006 + i * 0.00002,
      phase: Math.random() * 1000,
      opacity: 0.10 + Math.random() * 0.09,
    }))

    const nodes = Array.from({ length: 7 }, () => ({
      gx: Math.floor(Math.random() * 40),
      gy: Math.floor(Math.random() * 40),
      t: Math.random() * Math.PI * 2,
      speed: 0.006 + Math.random() * 0.008,
    }))

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = window.innerWidth
      height = window.innerHeight
      canvas.width = width * dpr
      canvas.height = height * dpr
      canvas.style.width = width + 'px'
      canvas.style.height = height + 'px'
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()
    window.addEventListener('resize', resize)

    const drawGrid = () => {
      ctx.strokeStyle = 'rgba(255,255,255,0.028)'
      ctx.lineWidth = 1
      ctx.beginPath()
      for (let x = 0; x < width; x += GRID_SPACING) {
        ctx.moveTo(x + 0.5, 0)
        ctx.lineTo(x + 0.5, height)
      }
      for (let y = 0; y < height; y += GRID_SPACING) {
        ctx.moveTo(0, y + 0.5)
        ctx.lineTo(width, y + 0.5)
      }
      ctx.stroke()
    }

    const drawTrace = (trace, t) => {
      const y0 = trace.baseY * height
      ctx.beginPath()
      for (let x = 0; x <= width; x += 6) {
        const y =
          y0 +
          Math.sin(x * trace.freq1 + t * trace.speed + trace.phase) * trace.amp +
          Math.sin(x * trace.freq2 - t * trace.speed * 1.7 + trace.phase) * (trace.amp * 0.35)
        if (x === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.strokeStyle = `rgba(${ACCENT[0]},${ACCENT[1]},${ACCENT[2]},${trace.opacity})`
      ctx.lineWidth = 1.4
      ctx.shadowColor = `rgba(${ACCENT[0]},${ACCENT[1]},${ACCENT[2]},0.55)`
      ctx.shadowBlur = 8
      ctx.stroke()
      ctx.shadowBlur = 0
    }

    const drawNodes = (t) => {
      nodes.forEach((n) => {
        const pulse = (Math.sin(t * n.speed + n.t) + 1) / 2
        const x = n.gx * GRID_SPACING
        const y = n.gy * GRID_SPACING
        const r = 1.5 + pulse * 2
        ctx.beginPath()
        ctx.arc(x, y, r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${ACCENT[0]},${ACCENT[1]},${ACCENT[2]},${pulse * 0.35})`
        ctx.fill()
      })
    }

    const animate = (t) => {
      ctx.clearRect(0, 0, width, height)
      drawGrid()
      traces.forEach((trace) => drawTrace(trace, t))
      drawNodes(t)
      animId = requestAnimationFrame(animate)
    }
    animId = requestAnimationFrame(animate)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        pointerEvents: 'none',
      }}
    />
  )
}