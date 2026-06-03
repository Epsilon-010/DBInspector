import type { FinalReport, PipelineStage, ProgressEvent } from '@/domain/types'

export type ChatTurnStatus = 'streaming' | 'done' | 'rejected' | 'failed'

export interface ChatTurn {
  id: string
  question: string
  status: ChatTurnStatus
  latestStage?: PipelineStage
  progress: ProgressEvent[]
  report?: FinalReport
  rejection?: string
  error?: { stage: string; message: string }
}
