import { type ReactNode } from 'react'
import { cn } from '@/lib/cn'

/**
 * Lightweight, dependency-free Markdown renderer for LLM answers.
 *
 * Supports the subset models actually emit: headings (#..######), unordered and
 * ordered lists, horizontal rules, and inline **bold**, *italic*, `code` and
 * __underline__. It builds React elements (never dangerouslySetInnerHTML), so it
 * is XSS-safe and works while an answer is still streaming in.
 */

let counter = 0
const nextKey = () => `md-${counter++}`

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

  for (const raw of lines) {
    const trimmed = raw.trim()

    if (!trimmed) {
      flushParagraph()
      flushList()
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
