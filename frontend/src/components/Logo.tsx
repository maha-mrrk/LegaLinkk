import { cn } from '@/lib/cn'

/**
 * LegalLink brand mark: a white glyph on a transparent background, so it can be
 * dropped onto any dark/branded surface (sidebar gradient, aubergine tiles,
 * assistant avatars) and stay consistent everywhere.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <img
      src="/logo.png"
      alt="LegalLink"
      className={cn('object-contain', className)}
    />
  )
}
