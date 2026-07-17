import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { MonthlyAnalysis } from '@/types'

export function MonthlyBarChart({ data }: { data: MonthlyAnalysis[] }) {
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} barSize={28}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
          <XAxis
            dataKey="month"
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#64748B', fontSize: 12 }}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#64748B', fontSize: 12 }}
            width={14}
          />
          <Tooltip
            cursor={{ fill: '#EFF6FF' }}
            contentStyle={{
              borderRadius: 12,
              border: '1px solid #E2E8F0',
              boxShadow: '0 8px 20px rgba(15,23,42,0.08)',
            }}
          />
          <Bar dataKey="count" fill="#2563EB" radius={[8, 8, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
