export interface Me { email: string; level: number; is_admin: boolean }
export interface Source { number: number; title: string; score: number; excerpt?: string }
export interface TraceStep { agent: string; ms: number; detail?: string | null }
export interface ChatReply {
  outcome: string
  answer: string
  sources?: Source[]
  corrected_query?: string | null
  message_id?: string
  conversation_id?: string
  rating?: number | null
  trace?: TraceStep[]
  can_request_access?: boolean
}
export interface ChatMessage {
  key: number
  role: 'user' | 'bot'
  text: string
  reply?: ChatReply
  pending?: boolean
  steps?: string[]
}

export const LEVELS: Record<number, string> = { 1: 'Analyst', 2: 'Manager', 3: 'Director', 4: 'Partner' }

export const OUTCOME_LABEL: Record<string, string> = {
  report: 'Research report',
  report_partial: 'Partial research report',
  answered: 'Answered',
  general: 'General knowledge',
  refused: 'Not available',
  no_answer: 'Not in documents',
  unverified: 'Could not verify',
  error: 'Error',
}
