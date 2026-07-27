import { type ReactNode } from 'react'
import { cn } from '@/lib/cn'

/**
 * Lightweight, dependency-free Markdown renderer for LLM answers.
 *
 * Supports the subset models actually emit: headings (#..######), unordered and
 * ordered lists, GitHub-style pipe tables, horizontal rules, and inline
 * **bold**, *italic*, `code` and __underline__. It builds React elements (never
 * dangerouslySetInnerHTML), so it is XSS-safe and works while an answer is still
 * streaming in.
 */

let counter = 0
const nextKey = () => `md-${counter++}`

type CellAlign = 'left' | 'center' | 'right' | null

/** Split a pipe-table row into trimmed cells (handles escaped `\|`). */
function splitTableRow(line: string): string[] {
  let s = line.trim()
  if (s.startsWith('|')) s = s.slice(1)
  if (s.endsWith('|')) s = s.slice(0, -1)
  return s
    .split(/(?<!\\)\|/)
    .map((c) => c.replace(/\\\|/g, '|').trim())
}

/** A separator row is `| --- | :--: | ---: |` (dashes with optional colons). */
function isTableSeparator(line: string): boolean {
  if (!line.includes('-')) return false
  const cells = splitTableRow(line)
  return cells.length > 0 && cells.every((c) => /^:?-{1,}:?$/.test(c))
}

function cellAlign(sep: string): CellAlign {
  const s = sep.trim()
  const left = s.startsWith(':')
  const right = s.endsWith(':')
  if (left && right) return 'center'
  if (right) return 'right'
  if (left) return 'left'
  return null
}

const ALIGN_CLASS: Record<'left' | 'center' | 'right', string> = {
  left: 'text-left',
  center: 'text-center',
  right: 'text-right',
}

/** Render inline emphasis inside a single line of text. */
function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = []
  // Order matters: match ** and __ before single * so bold wins over italic.
  const token = /(\*\*[^*\n]+\*\*|__[^_\n]+__|`[^`\n]+`|\*[^*\n]+\*|_[^_\n]+_)/g
  let last = 0
  let match: RegExpExecArray | null
  while ((match = token.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index))
    const raw = match[0]
    if (raw.startsWith('**')) {
      nodes.push(
        <strong key={nextKey()} className="font-semibold">
          {raw.slice(2, -2)}
        </strong>,
      )
    } else if (raw.startsWith('__')) {
      nodes.push(<u key={nextKey()}>{raw.slice(2, -2)}</u>)
    } else if (raw.startsWith('`')) {
      nodes.push(
        <code
          key={nextKey()}
          className="rounded bg-black/5 px-1 py-0.5 font-mono text-[0.85em]"
        >
          {raw.slice(1, -1)}
        </code>,
      )
    } else {
      // *italic* or _italic_
      nodes.push(<em key={nextKey()}>{raw.slice(1, -1)}</em>)
    }
    last = token.lastIndex
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

const HEADING_CLASS: Record<number, string> = {
  1: 'mt-3 text-[15px] font-bold text-slate-900',
  2: 'mt-3 text-sm font-bold text-slate-900',
  3: 'mt-2 text-sm font-semibold text-slate-900',
  4: 'mt-2 text-xs font-semibold uppercase tracking-wide text-slate-700',
  5: 'mt-2 text-xs font-semibold text-slate-700',
  6: 'mt-2 text-xs font-semibold text-slate-700',
}

export function MarkdownText({
  content,
  className,
}: {
  content: string
  className?: string
}) {
  const lines = (content ?? '').replace(/\r\n/g, '\n').split('\n')
  const blocks: ReactNode[] = []
  let paragraph: string[] = []
  let list: { ordered: boolean; items: string[] } | null = null

  const flushParagraph = () => {
    if (!paragraph.length) return
    const nodes: ReactNode[] = []
    paragraph.forEach((line, index) => {
      if (index > 0) nodes.push(<br key={nextKey()} />)
      nodes.push(...renderInline(line))
    })
    blocks.push(
      <p key={nextKey()} className="leading-relaxed">
        {nodes}
      </p>,
    )
    paragraph = []
  }

  const flushList = () => {
    if (!list) return
    const { ordered, items } = list
    const inner = items.map((item) => (
      <li key={nextKey()} className="leading-relaxed">
        {renderInline(item)}
      </li>
    ))
    blocks.push(
      ordered ? (
        <ol key={nextKey()} className="my-1 list-decimal space-y-1 pl-5">
          {inner}
        </ol>
      ) : (
        <ul key={nextKey()} className="my-1 list-disc space-y-1 pl-5">
          {inner}
        </ul>
      ),
    )
    list = null
  }

  const flushTable = (header: string[], aligns: CellAlign[], rows: string[][]) => {
    const cols = header.length
    const alignFor = (i: number) => {
      const a = aligns[i]
      return a ? ALIGN_CLASS[a] : ''
    }
    blocks.push(
      <div key={nextKey()} className="my-2 overflow-x-auto">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr>
              {header.map((cell, i) => (
                <th
                  key={nextKey()}
                  className={cn(
                    'border border-black/10 bg-black/5 px-2 py-1 font-semibold text-slate-800',
                    alignFor(i) || 'text-left',
                  )}
                >
                  {renderInline(cell)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={nextKey()}>
                {Array.from({ length: cols }, (_, i) => (
                  <td
                    key={nextKey()}
                    className={cn(
                      'border border-black/10 px-2 py-1 align-top',
                      alignFor(i),
                    )}
                  >
                    {renderInline(row[i] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    )
  }

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i]
    const trimmed = raw.trim()

    if (!trimmed) {
      flushParagraph()
      flushList()
      continue
    }

    // GFM pipe table: a row containing "|" immediately followed by a separator.
    if (
      trimmed.includes('|') &&
      i + 1 < lines.length &&
      isTableSeparator(lines[i + 1])
    ) {
      flushParagraph()
      flushList()
      const header = splitTableRow(trimmed)
      const aligns = splitTableRow(lines[i + 1]).map(cellAlign)
      const rows: string[][] = []
      let j = i + 2
      while (j < lines.length && lines[j].trim().includes('|')) {
        if (!lines[j].trim()) break
        rows.push(splitTableRow(lines[j]))
        j++
      }
      flushTable(header, aligns, rows)
      i = j - 1
      continue
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      flushParagraph()
      flushList()
      blocks.push(<hr key={nextKey()} className="my-2 border-black/10" />)
      continue
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed)
    if (heading) {
      flushParagraph()
      flushList()
      const level = heading[1].length
      blocks.push(
        <p key={nextKey()} className={HEADING_CLASS[level]}>
          {renderInline(heading[2])}
        </p>,
      )
      continue
    }

    const ordered = /^(\d+)[.)]\s+(.*)$/.exec(trimmed)
    if (ordered) {
      flushParagraph()
      if (!list || !list.ordered) {
        flushList()
        list = { ordered: true, items: [] }
      }
      list.items.push(ordered[2])
      continue
    }

    const unordered = /^[-*•]\s+(.*)$/.exec(trimmed)
    if (unordered) {
      flushParagraph()
      if (!list || list.ordered) {
        flushList()
        list = { ordered: false, items: [] }
      }
      list.items.push(unordered[1])
      continue
    }

    flushList()
    paragraph.push(trimmed)
  }

  flushParagraph()
  flushList()

  return <div className={cn('space-y-1.5', className)}>{blocks}</div>
}
