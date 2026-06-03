export type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'table'

export interface ChartSpec {
  type: ChartType
  x: string | null
  y: string | null
  series: string | null
  title: string
}

export interface AnalysisResult {
  summary: string
  chart: ChartSpec
}

export interface QueryResult {
  columns: string[]
  rowCount: number
  truncated: boolean
  rows: Array<Record<string, unknown>>
}

export interface FinalReport {
  question: string
  sql: string
  result: QueryResult
  analysis: AnalysisResult
}

export type PipelineStage =
  | 'guardrail'
  | 'sql_generator'
  | 'sql_executor'
  | 'data_processor'
  | 'analyzer'

export interface ProgressEvent {
  kind: 'progress'
  stage: PipelineStage
  message: string
  attempt: number
  payload: Record<string, unknown>
}

export interface RejectedEvent {
  kind: 'rejected'
  reason: string
}

export interface FailedEvent {
  kind: 'failed'
  stage: string
  error: string
}

export interface ResultEvent {
  kind: 'result'
  report: FinalReport
}

export type PipelineEvent = ProgressEvent | RejectedEvent | FailedEvent | ResultEvent

export type FlowStatus =
  | { kind: 'idle' }
  | { kind: 'running'; requestId: string; latestStage?: PipelineStage }
  | { kind: 'rejected'; reason: string }
  | { kind: 'failed'; stage: string; error: string }
  | { kind: 'done'; report: FinalReport }

export interface ConversationTurn {
  createdAt: string
  report: FinalReport
}

export interface Conversation {
  id: string
  createdAt: string
  updatedAt: string
  turns: ConversationTurn[]
}
