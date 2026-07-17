import { Search } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import { cn } from '@/lib/cn'

interface SearchBarProps {
  value?: string
  onChange?: (value: string) => void
  placeholder?: string
  className?: string
}

export function SearchBar({
  value,
  onChange,
  placeholder = 'Rechercher…',
  className,
}: SearchBarProps) {
  return (
    <div className={cn('w-full max-w-md', className)}>
      <Input
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        leftIcon={<Search className="size-4" />}
        aria-label="Recherche"
      />
    </div>
  )
}
