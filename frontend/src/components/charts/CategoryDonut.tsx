import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts'
import type { CategorySlice } from '@/types'

export function CategoryDonut({
  data,
  totalLabel = 'Analyses',
}: {
  data: CategorySlice[]
  totalLabel?: string
}) {
  const total = data.reduce((sum, item) => sum + item.value, 0)

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
      <div className="relative mx-auto h-44 w-44 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={52}
              outerRadius={72}
              paddingAngle={3}
              strokeWidth={0}
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <p className="text-2xl font-bold text-slate-900">{total}</p>
          <p className="text-[11px] text-muted">{totalLabel}</p>
        </div>
      </div>
      <ul className="flex flex-1 flex-col gap-2">
        {data.map((item) => (
          <li key={item.name} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-slate-600">
              <span
                className="size-2.5 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              {item.name}
            </span>
            <span className="font-medium text-slate-900">{item.value}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
