export interface Meeting {
  id: string
  title: string
  meeting_date?: string
  source_name?: string
  extraction_status?: string
  processing_message?: string
  synthetic?: boolean
}

export interface Citation {
  meeting_id: string
  meeting_title: string
  meeting_date?: string
  excerpt: string
  section?: string
  entity_id: string
  entity_type: string
  timestamp_start?: string
  timestamp_end?: string
}

export interface ChatAnswer {
  answer: string
  category: string
  evidence_strength: 'strong' | 'moderate' | 'limited' | 'none'
  citations: Citation[]
  related_entities: { id: string; label: string; name: string }[]
  session_id: string
  answer_provider: string
  warning?: string
}

const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

function validationDetail(detail: unknown): string | undefined {
  if (!Array.isArray(detail)) return undefined

  const messages = detail.flatMap((item) => {
    if (typeof item !== 'object' || item === null) return []
    const error = item as Record<string, unknown>
    if (typeof error.msg !== 'string') return []

    const location = Array.isArray(error.loc)
      ? error.loc
        .filter((part): part is string | number => typeof part === 'string' || typeof part === 'number')
        .filter((part) => part !== 'body')
        .join('.')
      : ''

    return [location ? `${location}: ${error.msg}` : error.msg]
  })

  return messages.length ? messages.join('; ') : undefined
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail =
      typeof body.detail === 'string'
        ? body.detail
        : validationDetail(body.detail) ?? `Request failed (${response.status})`
    throw new Error(detail)
  }
  return body as T
}
