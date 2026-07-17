import { useCallback, useRef, useState } from 'react'
import { CloudUpload } from 'lucide-react'
import { cn } from '@/lib/cn'

interface UploadZoneProps {
  onFiles?: (files: File[]) => void
  accept?: string
  className?: string
}

export function UploadZone({
  onFiles,
  accept = 'application/pdf',
  className,
}: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const handleFiles = useCallback(
    (list: FileList | null) => {
      if (!list?.length) return
      onFiles?.(Array.from(list))
    },
    [onFiles],
  )

  return (
    <div
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
      }}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        handleFiles(e.dataTransfer.files)
      }}
      className={cn(
        'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition-all duration-200',
        dragging
          ? 'border-brand bg-brand-soft scale-[1.01]'
          : 'border-slate-200 bg-slate-50/80 hover:border-brand/50 hover:bg-brand-soft/50',
        className,
      )}
    >
      <div className="mb-3 flex size-11 items-center justify-center rounded-full bg-white shadow-sm text-brand">
        <CloudUpload className="size-5" />
      </div>
      <p className="text-sm font-medium text-slate-800">
        Glissez-déposez votre PDF
      </p>
      <p className="mt-1 text-xs text-muted">
        ou{' '}
        <span className="font-medium text-brand underline-offset-2 hover:underline">
          Parcourir
        </span>
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  )
}
