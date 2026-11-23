import { api } from './api'
import type { ChatReply } from './types'

export interface StreamHandlers { onStep: (agent: string) => void }
export type StreamEnd = { ok: true; reply: ChatReply } | { ok: false; status: number; detail: string }

/** Plain-language names for the pipeline steps. An unknown step falls back to its own name. */
export const STEP_LABEL: Record<string, string> = {
  corrector: 'Fixing typos in the question',
  refiner: 'Understanding the question',
  router: 'Checking it is about the company',
  retriever: 'Searching documents you may see',
  reranker: 'Ranking the best passages',
  analysis: 'Planning the answer',
  answerer: 'Writing the answer',
  validator: 'Checking every claim against the sources',
  fit: 'Checking it answers what you asked',
}
export const stepLabel = (agent: string): string => STEP_LABEL[agent] ?? agent

/** Reads the server-sent events from /chat/stream. Progress arrives step by step; the answer arrives once, verified. */
export async function streamAnswer(body: unknown, handlers: StreamHandlers): Promise<StreamEnd> {
  const res = await api('/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok || !res.body) return { ok: false, status: res.status, detail: '' }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let cut = buffer.indexOf('\n\n')
    while (cut !== -1) {
      const block = buffer.slice(0, cut)
      buffer = buffer.slice(cut + 2)
      const event = /^event: (.*)$/m.exec(block)?.[1]
      const data = /^data: (.*)$/m.exec(block)?.[1]
      if (event && data) {
        const parsed = JSON.parse(data)
        if (event === 'step') handlers.onStep(String(parsed.agent))
        else if (event === 'result') return { ok: true, reply: parsed as ChatReply }
        else if (event === 'error') return { ok: false, status: Number(parsed.status), detail: String(parsed.detail) }
      }
      cut = buffer.indexOf('\n\n')
    }
  }
  return { ok: false, status: 0, detail: 'The connection closed before an answer arrived.' }
}
