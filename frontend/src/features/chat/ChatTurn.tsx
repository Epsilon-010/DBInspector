import { lazy, Suspense } from 'react'

import { Card } from '@/components/Card'
import { CollapsiblePanel } from '@/components/CollapsiblePanel'
import { DataTable } from '@/components/DataTable'
import { ProgressTimeline } from '@/features/query/ProgressTimeline'
import type { FlowStatus } from '@/domain/types'

import type { ChatTurn as ChatTurnState } from './types'

const ChartRenderer = lazy(() =>
  import('@/components/ChartRenderer').then((m) => ({ default: m.ChartRenderer })),
)

interface ChatTurnViewProps {
  turn: ChatTurnState
  isLatest: boolean
}

export function ChatTurnView({ turn, isLatest }: ChatTurnViewProps) {
  return (
    <div className="space-y-3">
      <UserBubble question={turn.question} />
      <AssistantBubble turn={turn} initiallyExpanded={isLatest} />
    </div>
  )
}

function UserBubble({ question }: { question: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-accent/15 border border-accent/30 px-4 py-2.5 text-sm text-ink leading-relaxed shadow-sm">
        {question}
      </div>
    </div>
  )
}

interface AssistantBubbleProps {
  turn: ChatTurnState
  initiallyExpanded: boolean
}

function AssistantBubble({ turn, initiallyExpanded }: AssistantBubbleProps) {
  if (turn.status === 'streaming') {
    return <ProgressTimeline status={toFlowStatus(turn)} events={turn.progress} />
  }

  if (turn.status === 'rejected') {
    return (
      <Card title="Pregunta rechazada" subtitle="El guardrail bloqueó la consulta">
        <p className="text-sm text-warn">{turn.rejection ?? 'Pregunta no permitida.'}</p>
      </Card>
    )
  }

  if (turn.status === 'failed' || !turn.report) {
    return (
      <Card title="Error" subtitle={turn.error?.stage ?? 'pipeline'}>
        <p className="text-sm text-err">{turn.error?.message ?? 'Falló la consulta.'}</p>
      </Card>
    )
  }

  const { report } = turn
  const { result, analysis, sql } = report

  return (
    <div className="space-y-3 animate-fade-in">
      <Card title="Resumen ejecutivo" subtitle={analysis.chart.title}>
        <p className="text-ink leading-relaxed">{analysis.summary}</p>
      </Card>

      {analysis.chart.type !== 'table' && analysis.chart.x && analysis.chart.y && (
        <Card title="Gráfica">
          <Suspense
            fallback={<div className="h-72 animate-pulse-soft rounded-xl bg-white/[0.02]" />}
          >
            <ChartRenderer spec={analysis.chart} rows={result.rows} />
          </Suspense>
        </Card>
      )}

      <CollapsiblePanel
        defaultOpen={initiallyExpanded}
        summary={
          result.truncated
            ? `Datos — ${result.rowCount} filas (truncado)`
            : `Datos — ${result.rowCount} fila${result.rowCount === 1 ? '' : 's'}`
        }
      >
        <DataTable columns={result.columns} rows={result.rows} />
      </CollapsiblePanel>

      <CollapsiblePanel defaultOpen={initiallyExpanded} summary="SQL generado">
        <pre className="overflow-x-auto rounded-xl bg-bg-subtle/60 p-4 text-xs text-ink font-mono leading-relaxed">
          <code>{sql}</code>
        </pre>
      </CollapsiblePanel>
    </div>
  )
}

function toFlowStatus(turn: ChatTurnState): FlowStatus {
  switch (turn.status) {
    case 'streaming':
      return { kind: 'running', requestId: turn.id, latestStage: turn.latestStage }
    case 'rejected':
      return { kind: 'rejected', reason: turn.rejection ?? '' }
    case 'failed':
      return {
        kind: 'failed',
        stage: turn.error?.stage ?? 'pipeline',
        error: turn.error?.message ?? '',
      }
    case 'done':
      return turn.report
        ? { kind: 'done', report: turn.report }
        : { kind: 'failed', stage: 'pipeline', error: 'missing report' }
  }
}

