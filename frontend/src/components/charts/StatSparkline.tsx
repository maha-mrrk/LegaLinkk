import { Area, AreaChart, ResponsiveContainer } from 'recharts'

export function StatSparkline({
  data,
  color = '#2563EB',
}: {
  data: number[]
  color?: string
}) {
  const chartData = data.map((value, index) => ({ index, value }))
  return (
    <div className="h-10 w-20">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id={`spark-${color}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            fill={`url(#spark-${color})`}
            isAnimationActive
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
