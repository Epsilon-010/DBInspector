import { Card } from '@/components/Card'
import type { FlowStatus, PipelineStage, ProgressEvent } from '@/domain/types'

interface ProgressTimelineProps {
  status: FlowStatus
  events: ProgressEvent[]
}

const STAGE_ORDER: PipelineStage[] = [
  'guardrail',
  'sql_generator',
  'sql_executor',
  'data_processor',
  'analyzer',
]

const STAGE_LABEL: Record<PipelineStage, string> = {
  guardrail: 'Validación de seguridad',
  sql_generator: 'Generación de SQL',
  sql_executor: 'Ejecución en la base',
  data_processor: 'Procesamiento de datos',
  analyzer: 'Análisis y visualización',
}

export function ProgressTimeline({ status, events }: ProgressTimelineProps) {
  if (status.kind === 'idle') return null

  const seenStages = new Set(events.map((e) => e.stage))
  const activeStage = status.kind === 'running' ? status.latestStage : undefined
  const finalKind = status.kind

  return (
    <Card title="Progreso en vivo">
      <ol className="space-y-3">
        {STAGE_ORDER.map((stage) => {
          const stageEvents = events.filter((e) => e.stage === stage)
          const state = stageState(stage, seenStages, activeStage, finalKind)
          return (
            <li key={stage} className="flex items-start gap-3">
              <StageDot state={state} />
              <div className="flex-1 min-w-0">
                <p
                  className={`text-sm font-medium ${
                    state === 'pending' ? 'text-ink-faint' : 'text-ink'
                  }`}
                >
                  {STAGE_LABEL[stage]}
                </p>
                {stageEvents.map((evt, idx) => (
                  <p
                    key={idx}
                    className="text-xs text-ink-dim font-mono animate-fade-in mt-0.5"
                  >
                    {evt.attempt > 1 ? `(intento ${evt.attempt}) ` : ''}
                    {evt.message}
                  </p>
                ))}
              </div>
            </li>
          )
        })}
      </ol>

      {status.kind === 'rejected' && (
        <div className="mt-4 rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">
          <strong className="block text-xs uppercase tracking-wider mb-1">Pregunta rechazada</strong>
          {status.reason}
        </div>
      )}
      {status.kind === 'failed' && (
        <div className="mt-4 rounded-lg border border-err/30 bg-err/10 p-3 text-sm text-err">
          <strong className="block text-xs uppercase tracking-wider mb-1">
            Falló ({status.stage})
          </strong>
          {status.error}
        </div>
      )}
    </Card>
  )
}

type StageState = 'pending' | 'active' | 'done' | 'skipped'

function stageState(
  stage: PipelineStage,
  seen: Set<PipelineStage>,
  active: PipelineStage | undefined,
  finalKind: FlowStatus['kind'],
): StageState {
  if (seen.has(stage)) {
    if (active === stage && finalKind === 'running') return 'active'
    return 'done'
  }
  if (finalKind === 'done') return 'done'
  if (finalKind === 'rejected' || finalKind === 'failed') return 'skipped'
  return 'pending'
}

function StageDot({ state }: { state: StageState }) {
  const base = 'mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full border'
  switch (state) {
    case 'active':
      return <span className={`${base} border-accent bg-accent animate-pulse-soft`} />
    case 'done':
      return <span className={`${base} border-ok bg-ok`} />
    case 'skipped':
      return <span className={`${base} border-white/10 bg-transparent`} />
    case 'pending':
      return <span className={`${base} border-white/10 bg-white/5`} />
  }
}
