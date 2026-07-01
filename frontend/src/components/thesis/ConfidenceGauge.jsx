export default function ConfidenceGauge({ value }) {
  const percentage = (value / 10) * 100
  const getColor = () => {
    if (value <= 3) return { bar: '#f43f5e', glow: 'rgba(244, 63, 94, 0.3)', label: 'Low' }
    if (value <= 6) return { bar: '#f59e0b', glow: 'rgba(245, 158, 11, 0.3)', label: 'Medium' }
    if (value <= 8) return { bar: '#3b82f6', glow: 'rgba(59, 130, 246, 0.3)', label: 'High' }
    return { bar: '#10b981', glow: 'rgba(16, 185, 129, 0.3)', label: 'Very High' }
  }

  const { bar, glow, label } = getColor()

  return (
    <div className="glass-1 rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-gray-500 font-medium">Confidence Level</span>
        <span className="text-xs font-mono font-semibold" style={{ color: bar }}>{label}</span>
      </div>
      <div className="relative h-2.5 rounded-full bg-white/[0.04] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${percentage}%`,
            background: `linear-gradient(90deg, ${bar}88, ${bar})`,
            boxShadow: `0 0 12px ${glow}`,
          }}
        />
      </div>
      <div className="flex justify-between mt-2">
        <span className="text-[10px] text-gray-600 font-mono">1</span>
        <span className="text-[10px] text-gray-600 font-mono">10</span>
      </div>
    </div>
  )
}
