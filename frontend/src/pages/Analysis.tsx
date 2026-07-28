import { useMemo, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Eye,
  FileOutput,
  FileText,
  HelpCircle,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { ScoreGauge } from '@/components/charts/ScoreGauge'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { MarkdownText } from '@/components/MarkdownText'
import { RiskBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import {
  useDocuments,
  useLegalAnalysis,
  useRefreshLegalAnalysis,
} from '@/hooks/useDocuments'
import { useGeneratedDocuments } from '@/hooks/useGeneratedDocuments'
import { cn } from '@/lib/cn'
import { downloadDocumentPdf } from '@/services/chat'
import { fetchGeneratedDocumentBlob } from '@/services/generatedDocuments'
import type {
  GeneratedDocumentItem,
  LegalAnalysis,
  RiskLevel,
} from '@/types'

const tabs = [
  'Résumé',
  'Points critiques',
  'Informations manquantes',
  'Recommandations',
  'Sources',
  'Documents générés',
]

const RISK_META: Record<RiskLevel, { score: number; label: string }> = {
  low: { score: 85, label: 'Risque faible' },
  medium: { score: 58, label: 'Risque modéré' },
  high: { score: 32, label: 'Risque élevé' },
}

function formatAnalyzedAt(value: unknown): string | null {
  if (typeof value !== 'string' || !value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function renderInlineMarkdown(value: string): string {
  return escapeHtml(value)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<u>$1</u>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

function splitTableRow(value: string): string[] {
  return value
    .trim()
    .replace(/^\||\|$/g, '')
    .split('|')
    .map((cell) => cell.trim())
}

/** Convert the safe Markdown subset used by analyses into printable HTML. */
function analysisMarkdownToHtml(markdown: string): string {
  const lines = (markdown || '').replace(/\r\n/g, '\n').split('\n')
  const html: string[] = []
  let list: 'ul' | 'ol' | null = null

  const closeList = () => {
    if (list) html.push(`</${list}>`)
    list = null
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i].trim()
    if (!line) {
      closeList()
      continue
    }

    if (
      line.includes('|') &&
      i + 1 < lines.length &&
      splitTableRow(lines[i + 1]).every((cell) => /^:?-{1,}:?$/.test(cell))
    ) {
      closeList()
      const headers = splitTableRow(line)
      const rows: string[][] = []
      i += 2
      while (i < lines.length && lines[i].trim().includes('|')) {
        rows.push(splitTableRow(lines[i]))
        i += 1
      }
      i -= 1
      html.push(
        '<table><thead><tr>',
        ...headers.map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`),
        '</tr></thead><tbody>',
        ...rows.map(
          (row) =>
            `<tr>${headers
              .map(
                (_header, index) =>
                  `<td>${renderInlineMarkdown(row[index] ?? '')}</td>`,
              )
              .join('')}</tr>`,
        ),
        '</tbody></table>',
      )
      continue
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      closeList()
      const level = Math.min(4, heading[1].length + 1)
      html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`)
      continue
    }

    const unordered = /^[-*•]\s+(.*)$/.exec(line)
    const ordered = /^\d+[.)]\s+(.*)$/.exec(line)
    if (unordered || ordered) {
      const nextList = ordered ? 'ol' : 'ul'
      if (list !== nextList) {
        closeList()
        list = nextList
        html.push(`<${nextList}>`)
      }
      html.push(`<li>${renderInlineMarkdown((unordered ?? ordered)?.[1] ?? '')}</li>`)
      continue
    }

    closeList()
    html.push(`<p>${renderInlineMarkdown(line)}</p>`)
  }
  closeList()
  return html.join('')
}

function buildAnalysisPdfHtml(params: {
  filename: string
  analysis: LegalAnalysis
  score: number
  riskLabel: string
  analyzedAt: string | null
}): string {
  const { filename, analysis, score, riskLabel, analyzedAt } = params
  const findings = analysis.metadata?.risk_findings ?? []
  const danger = score < 50
  const accent = danger ? '#dc2626' : '#16a34a'
  const soft = danger ? '#fef2f2' : '#f0fdf4'
  const section = (title: string, body: string) =>
    `<section><h2>${escapeHtml(title)}</h2>${body}</section>`
  const list = (items: string[]) =>
    items.length
      ? `<ul>${items.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join('')}</ul>`
      : '<p class="muted">Aucun élément identifié.</p>'

  return `<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Analyse juridique — ${escapeHtml(filename)}</title>
  <style>
    @page { size: A4; margin: 18mm 16mm; }
    * { box-sizing: border-box; }
    body { margin: 0; color: #1e293b; font: 10.5pt/1.55 Arial, sans-serif; }
    header { border-bottom: 2px solid #7c2869; margin-bottom: 22px; padding-bottom: 14px; }
    .brand { color: #7c2869; font-size: 10pt; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
    h1 { color: #0f172a; font-size: 21pt; margin: 6px 0 3px; }
    h2 { border-bottom: 1px solid #e2e8f0; color: #0f172a; font-size: 14pt; margin: 22px 0 10px; padding-bottom: 5px; }
    h3, h4 { color: #0f172a; margin: 14px 0 5px; }
    p { margin: 5px 0; }
    ul, ol { margin: 6px 0 10px; padding-left: 22px; }
    li { margin: 3px 0; }
    code { background: #f1f5f9; border-radius: 3px; padding: 1px 3px; }
    table { border-collapse: collapse; margin: 10px 0; width: 100%; }
    th, td { border: 1px solid #cbd5e1; padding: 6px 7px; text-align: left; vertical-align: top; }
    th { background: #f1f5f9; color: #0f172a; }
    section { break-inside: auto; }
    .meta { color: #64748b; font-size: 9pt; }
    .risk { align-items: center; background: ${soft}; border: 1px solid ${accent}33; border-radius: 10px; display: flex; gap: 18px; margin: 16px 0; padding: 13px 16px; }
    .score { color: ${accent}; font-size: 25pt; font-weight: 700; }
    .risk-label { color: ${accent}; font-weight: 700; }
    .finding { border-left: 4px solid ${accent}; background: #f8fafc; margin: 8px 0; padding: 8px 11px; }
    .finding strong { display: block; }
    .source { border-bottom: 1px solid #e2e8f0; padding: 5px 0; }
    .muted { color: #64748b; font-style: italic; }
    footer { border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 8pt; margin-top: 26px; padding-top: 8px; }
  </style>
</head>
<body>
  <header>
    <div class="brand">LegalLink</div>
    <h1>Rapport d’analyse juridique</h1>
    <div class="meta">${escapeHtml(filename)}${analyzedAt ? ` · Analyse du ${escapeHtml(analyzedAt)}` : ''}</div>
  </header>
  <div class="risk">
    <div class="score">${score}/100</div>
    <div><div class="risk-label">${escapeHtml(riskLabel)}</div><div class="meta">Niveau de risque global</div></div>
  </div>
  ${section('Résumé de l’analyse', analysisMarkdownToHtml(analysis.analysis))}
  ${section(
    'Points critiques',
    findings.length
      ? findings
          .map(
            (finding) =>
              `<div class="finding"><strong>${escapeHtml(finding.category)} — ${escapeHtml(finding.level)}</strong>${renderInlineMarkdown(finding.detail)}</div>`,
          )
          .join('')
      : '<p class="muted">Aucun point critique majeur détecté.</p>',
  )}
  ${section('Informations manquantes', list(analysis.missing_information))}
  ${section('Recommandations', list(analysis.recommendations))}
  ${section(
    'Sources examinées',
    analysis.sources.length
      ? analysis.sources
          .map(
            (source) =>
              `<div class="source"><strong>${escapeHtml(source.filename ?? 'Document')}</strong>${source.page ? ` — page ${source.page}` : ''}</div>`,
          )
          .join('')
      : '<p class="muted">Aucune source disponible.</p>',
  )}
  <footer>Rapport généré par LegalLink. Cette analyse constitue une aide à la lecture contractuelle.</footer>
</body>
</html>`
}

export function AnalysisPage() {
  const { id = '' } = useParams()
  const { data: documents } = useDocuments()
  const { data, isLoading, isError, error } = useLegalAnalysis(id)
  const { data: generatedDocuments, isLoading: generatedDocumentsLoading } =
    useGeneratedDocuments(id)
  const refresh = useRefreshLegalAnalysis(id)
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('Résumé')
  const [severityFilter, setSeverityFilter] = useState<RiskLevel | 'all'>('all')
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)
  const [generatedBusy, setGeneratedBusy] = useState<string | null>(null)

  const document = useMemo(
    () => documents?.find((d) => d.id === id),
    [documents, id],
  )

  const findings = data?.metadata?.risk_findings ?? []
  const filteredFindings =
    severityFilter === 'all'
      ? findings
      : findings.filter((finding) => finding.level === severityFilter)
  const severityOptions: Array<{
    value: RiskLevel | 'all'
    label: string
    count: number
  }> = [
    { value: 'all', label: 'Tous', count: findings.length },
    {
      value: 'high',
      label: 'Élevée',
      count: findings.filter((finding) => finding.level === 'high').length,
    },
    {
      value: 'medium',
      label: 'Modérée',
      count: findings.filter((finding) => finding.level === 'medium').length,
    },
    {
      value: 'low',
      label: 'Faible',
      count: findings.filter((finding) => finding.level === 'low').length,
    },
  ]
  const riskMeta = data ? RISK_META[data.risk_level] : RISK_META.medium
  const risk = {
    ...riskMeta,
    score: data?.risk_score ?? riskMeta.score,
  }
  const analyzedAt = formatAnalyzedAt(data?.metadata?.analyzed_at)

  if (isLoading) {
    return (
      <LoadingSpinner label="Analyse en cours en arrière-plan… vous pouvez quitter cette page et revenir plus tard." />
    )
  }

  if (isError || !data) {
    return (
      <Card padding="lg">
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertTriangle className="size-8 text-danger" />
          <h2 className="text-lg font-semibold text-slate-900">
            Analyse indisponible
          </h2>
          <p className="max-w-md text-sm text-muted">
            {error instanceof Error
              ? error.message
              : "Impossible d'analyser ce contrat pour le moment."}
          </p>
        </div>
      </Card>
    )
  }

  const handleExportPdf = async () => {
    setPdfError(null)
    setPdfLoading(true)
    const filename = document?.filename ?? 'contrat'
    try {
      const html = buildAnalysisPdfHtml({
        filename,
        analysis: data,
        score: risk.score,
        riskLabel: risk.label,
        analyzedAt,
      })
      const pdfName = `${filename.replace(/\.pdf$/i, '')}-analyse.pdf`
      const blob = await downloadDocumentPdf(html, {
        filename: pdfName,
        title: `Analyse de ${filename}`,
        sourceDocumentId: id,
        kind: 'analysis_export',
      })
      const url = URL.createObjectURL(blob)
      const anchor = window.document.createElement('a')
      anchor.href = url
      anchor.download = pdfName
      window.document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      void queryClient.invalidateQueries({ queryKey: ['generated-documents'] })
    } catch {
      setPdfError(
        'L’export PDF a échoué. Veuillez réessayer dans un instant.',
      )
    } finally {
      setPdfLoading(false)
    }
  }

  const openGeneratedDocument = async (
    item: GeneratedDocumentItem,
    download: boolean,
  ) => {
    setGeneratedBusy(item.id)
    try {
      const blob = await fetchGeneratedDocumentBlob(item.id)
      const url = URL.createObjectURL(blob)
      if (download) {
        const anchor = window.document.createElement('a')
        anchor.href = url
        anchor.download = item.filename
        window.document.body.appendChild(anchor)
        anchor.click()
        anchor.remove()
      } else {
        window.open(url, '_blank', 'noopener,noreferrer')
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      setPdfError("Impossible d'ouvrir ce document généré.")
    } finally {
      setGeneratedBusy(null)
    }
  }

  return (
    <div className="space-y-6">
      <Card padding="lg">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex size-12 items-center justify-center rounded-xl bg-red-50 text-red-500">
              <FileText className="size-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                {document?.filename ?? 'Contrat'}
              </h2>
              <p className="mt-0.5 text-sm text-muted">
                {document?.pageCount ? `${document.pageCount} pages · ` : ''}
                {document?.date ?? ''}
                {analyzedAt ? ` · Analyse enregistrée le ${analyzedAt}` : ''}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              onClick={handleExportPdf}
              disabled={pdfLoading}
              leftIcon={
                pdfLoading ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Download className="size-3.5" />
                )
              }
            >
              {pdfLoading ? 'Création du PDF…' : 'Exporter en PDF'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => refresh.mutate()}
              disabled={refresh.isPending}
              leftIcon={
                refresh.isPending ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="size-3.5" />
                )
              }
            >
              {refresh.isPending ? 'Nouvelle analyse…' : 'Relancer l’analyse'}
            </Button>
          </div>
        </div>

        {pdfError ? (
          <p className="mt-3 flex items-center gap-1.5 text-xs text-danger">
            <AlertTriangle className="size-3.5" />
            {pdfError}
          </p>
        ) : null}

        {refresh.isError ? (
          <p className="mt-3 flex items-center gap-1.5 text-xs text-danger">
            <AlertTriangle className="size-3.5" />
            {refresh.error instanceof Error
              ? refresh.error.message
              : 'La nouvelle analyse a échoué.'}
          </p>
        ) : null}

        <div className="mt-5 flex gap-1 overflow-x-auto border-b border-border pb-px scrollbar-thin">
          {tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={cn(
                'whitespace-nowrap rounded-t-lg px-4 py-2.5 text-sm font-medium transition-colors',
                activeTab === tab
                  ? 'border-b-2 border-brand text-brand'
                  : 'text-muted hover:text-slate-800',
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          {activeTab === 'Résumé' ? (
            <Card padding="lg">
              <CardHeader title="Analyse juridique" />
              <MarkdownText
                content={data.analysis}
                className="text-sm text-slate-700"
              />
            </Card>
          ) : null}

          {activeTab === 'Points critiques' ? (
            <>
              <Card padding="md">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="mr-1 text-xs font-semibold text-slate-500">
                    Filtrer par sévérité
                  </span>
                  {severityOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setSeverityFilter(option.value)}
                      className={cn(
                        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition',
                        severityFilter === option.value
                          ? option.value === 'high'
                            ? 'border-red-200 bg-red-50 text-danger'
                            : option.value === 'medium'
                              ? 'border-amber-200 bg-amber-50 text-warning'
                              : option.value === 'low'
                                ? 'border-emerald-200 bg-emerald-50 text-success'
                                : 'border-brand bg-brand text-white'
                          : 'border-border bg-white text-slate-500 hover:border-brand/30 hover:text-slate-700',
                      )}
                    >
                      {option.label}
                      <span
                        className={cn(
                          'rounded-full px-1.5 py-0.5 text-[10px]',
                          severityFilter === option.value
                            ? 'bg-white/70 text-current'
                            : 'bg-slate-100 text-slate-500',
                        )}
                      >
                        {option.count}
                      </span>
                    </button>
                  ))}
                </div>
              </Card>

              {findings.length ? (
                filteredFindings.length ? (
                  filteredFindings.map((point, index) => (
                    <Card
                      key={`${point.category}-${index}`}
                      className="transition-all duration-200 hover:border-brand/20 hover:shadow-md"
                      padding="lg"
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={cn(
                            'mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg',
                            point.level === 'high'
                              ? 'bg-red-50 text-danger'
                              : point.level === 'medium'
                                ? 'bg-amber-50 text-warning'
                                : 'bg-emerald-50 text-success',
                          )}
                        >
                          <AlertTriangle className="size-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-slate-900">
                              {point.category}
                            </h3>
                            <RiskBadge risk={point.level} />
                          </div>
                          <p className="mt-1.5 text-sm text-slate-600">
                            {point.detail}
                          </p>
                        </div>
                      </div>
                    </Card>
                  ))
                ) : (
                  <EmptyState
                    icon={<CheckCircle2 className="size-6 text-success" />}
                    text="Aucun point critique pour cette sévérité."
                  />
                )
              ) : (
                <EmptyState
                  icon={<CheckCircle2 className="size-6 text-success" />}
                  text="Aucun point critique majeur détecté."
                />
              )}
            </>
          ) : null}

          {activeTab === 'Informations manquantes' ? (
            data.missing_information.length ? (
              <Card padding="lg">
                <CardHeader title="Éléments manquants ou ambigus" />
                <ul className="space-y-2.5">
                  {data.missing_information.map((item, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm text-slate-700">
                      <HelpCircle className="mt-0.5 size-4 shrink-0 text-warning" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : (
              <EmptyState
                icon={<CheckCircle2 className="size-6 text-success" />}
                text="Aucune information manquante identifiée."
              />
            )
          ) : null}

          {activeTab === 'Recommandations' ? (
            data.recommendations.length ? (
              <Card padding="lg">
                <CardHeader title="Recommandations" />
                <ul className="space-y-2.5">
                  {data.recommendations.map((item, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm text-slate-700">
                      <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-brand" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : (
              <EmptyState
                icon={<CheckCircle2 className="size-6 text-success" />}
                text="Aucune recommandation particulière."
              />
            )
          ) : null}

          {activeTab === 'Sources' ? (
            data.sources.length ? (
              <Card padding="lg">
                <CardHeader title="Passages de référence" />
                <div className="space-y-2">
                  {data.sources.map((source, index) => (
                    <div
                      key={source.chunk_id ?? index}
                      className="flex items-center justify-between rounded-lg border border-border bg-slate-50 px-3 py-2.5 text-sm"
                    >
                      <span className="min-w-0 truncate font-medium text-slate-700">
                        {source.filename ?? 'Document'}
                      </span>
                      <span className="ml-3 shrink-0 text-xs text-muted">
                        {source.page ? `p. ${source.page}` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            ) : (
              <EmptyState
                icon={<FileText className="size-6 text-muted" />}
                text="Aucune source disponible."
              />
            )
          ) : null}

          {activeTab === 'Documents générés' ? (
            generatedDocumentsLoading ? (
              <LoadingSpinner label="Chargement des documents générés…" />
            ) : generatedDocuments?.length ? (
              <Card padding="lg">
                <CardHeader
                  title="Documents générés pour ce contrat"
                  subtitle={`${generatedDocuments.length} document${generatedDocuments.length > 1 ? 's' : ''} enregistré${generatedDocuments.length > 1 ? 's' : ''}`}
                />
                <ul className="space-y-3">
                  {generatedDocuments.map((item) => (
                    <li
                      key={item.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-slate-50 px-4 py-3"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-500">
                          <FileOutput className="size-5" />
                        </span>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-slate-800">
                            {item.title}
                          </p>
                          <p className="text-xs text-muted">
                            {item.kind === 'analysis_export'
                              ? 'Rapport d’analyse'
                              : 'Document de consultation'}
                            {' · '}
                            {new Date(item.createdAt).toLocaleString('fr-FR')}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={generatedBusy === item.id}
                          onClick={() => openGeneratedDocument(item, false)}
                        >
                          {generatedBusy === item.id ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <Eye className="size-4" />
                          )}
                          Voir
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={generatedBusy === item.id}
                          onClick={() => openGeneratedDocument(item, true)}
                        >
                          <Download className="size-4" />
                          Télécharger
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : (
              <EmptyState
                icon={<FileOutput className="size-6 text-muted" />}
                text="Aucun document généré pour ce contrat."
              />
            )
          ) : null}
        </div>

        <div className="space-y-4">
          <Card padding="lg">
            <CardHeader title="Niveau de risque" />
            <ScoreGauge score={risk.score} label={risk.label} />
            <div className="mt-6 grid grid-cols-2 gap-3">
              <Metric label="Points critiques" value={String(findings.length)} />
              <Metric
                label="Passages examinés"
                value={String(data.sources.length)}
              />
              <Metric
                label="Éléments manquants"
                value={String(data.missing_information.length)}
                className="col-span-2"
              />
            </div>
          </Card>

          <Card padding="lg">
            <CardHeader title="Niveau de risque global" />
            <div className="flex items-center justify-center py-2">
              <RiskBadge risk={data.risk_level} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

function EmptyState({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <Card padding="lg">
      <div className="flex flex-col items-center gap-2 py-8 text-center">
        {icon}
        <p className="text-sm text-muted">{text}</p>
      </div>
    </Card>
  )
}

function Metric({
  label,
  value,
  className,
}: {
  label: string
  value: string
  className?: string
}) {
  return (
    <div className={cn('rounded-xl bg-slate-50 px-3 py-3 text-center', className)}>
      <p className="text-lg font-bold text-slate-900">{value}</p>
      <p className="text-[11px] text-muted">{label}</p>
    </div>
  )
}
