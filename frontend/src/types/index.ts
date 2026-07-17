export type DocumentStatus =
  | 'completed'
  | 'processing'
  | 'failed'
  | 'queued'
  | 'pending'

export type RiskLevel = 'low' | 'medium' | 'high'

export type AnalysisCategory =
  | 'Commercial'
  | 'Social'
  | 'IT'
  | 'Fiscal'
  | 'Compliance'

export interface User {
  id: string
  name: string
  role: string
  email: string
  avatarUrl?: string
  initials: string
}

export interface StatCard {
  id: string
  label: string
  value: string
  trend: string
  trendUp: boolean
  sparkline: number[]
}

export interface ActivityItem {
  id: string
  title: string
  subtitle: string
  timeAgo: string
  status: DocumentStatus
}

export interface CategorySlice {
  name: AnalysisCategory
  value: number
  color: string
}

export interface MonthlyAnalysis {
  month: string
  count: number
}

export interface DocumentItem {
  id: string
  filename: string
  type: AnalysisCategory
  date: string
  agents: string[]
  score: number
  status: DocumentStatus
  pageCount?: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export interface CriticalPoint {
  id: string
  title: string
  description: string
  risk: RiskLevel
  reference: string
  page: number
}

export interface AnalysisResult {
  id: string
  document: DocumentItem
  score: number
  riskLabel: string
  complianceRate: number
  clausesAnalyzed: number
  legalReferences: number
  agents: AgentSummary[]
  criticalPoints: CriticalPoint[]
  summary: string
}

export interface AgentSummary {
  id: string
  name: string
  initials: string
  color: string
}

export interface AgentDetail extends AgentSummary {
  status: 'active' | 'idle' | 'error'
  description: string
  responsibilities: string[]
  inputs: string[]
  outputs: string[]
  stats: {
    analyses: number
    successRate: number
    avgTime: string
    avgCost: string
  }
}

export type PipelineStageStatus = 'done' | 'active' | 'pending' | 'error'

export interface PipelineStage {
  id: string
  label: string
  status: PipelineStageStatus
}

export interface PipelineEvent {
  id: string
  time: string
  message: string
  status: 'ok' | 'info' | 'warn'
}

export interface PipelineRun {
  id: string
  documentName: string
  progress: number
  stages: PipelineStage[]
  activeStageLabel: string
  activeStageDetail: string
  events: PipelineEvent[]
  consumption: {
    model: string
    inputTokens: number
    outputTokens: number
    estimatedCost: string
  }
}

export interface Suggestion {
  id: string
  label: string
}
