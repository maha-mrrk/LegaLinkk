export function ScoreGauge({
  score,
  label,
}: {
  score: number
  label: string
}) {
  const clamped = Math.max(0, Math.min(100, score))
  const circumference = Math.PI * 90
  const offset = circumference - (clamped / 100) * circumference

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-32 w-56">
        <svg viewBox="0 0 200 110" className="h-full w-full">
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="#E2E8F0"
            strokeWidth="14"
            strokeLinecap="round"
          />
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="#22C55E"
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-700 ease-out"
          />
        </svg>
        <div className="absolute inset-x-0 bottom-2 text-center">
          <p className="text-3xl font-bold text-slate-900">
            {score}
            <span className="text-base font-medium text-muted">/100</span>
          </p>
        </div>
      </div>
      <p className="mt-1 rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700">
        {label}
      </p>
    </div>
  )
}
