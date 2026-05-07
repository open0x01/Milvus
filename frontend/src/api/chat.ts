import { SourceDoc } from '../stores/chatStore'

interface ChatRequest {
  question: string
  session_id?: string
  user_id?: string
  top_k?: number
}

export interface SessionInfo {
  session_id: string
  title: string
  created_at: number
  updated_at: number
}

const API_BASE = import.meta.env.VITE_API_URL || '/api'

export async function sendStreamMessage(
  req: ChatRequest,
  onSources: (sources: SourceDoc[], sessionId: string) => void,
  onToken: (token: string) => void,
  onDone: (answer: string, sessionId: string) => void,
  onError: (error: string) => void
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

  if (!res.ok) {
    onError('Failed to send message')
    return
  }

  const reader = res.body?.getReader()
  if (!reader) {
    onError('No response body')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data: ')) continue

      const jsonStr = trimmed.slice(6)
      try {
        const data = JSON.parse(jsonStr)

        if (data.type === 'sources') {
          onSources(data.sources, data.session_id)
        } else if (data.type === 'token') {
          onToken(data.content)
        } else if (data.type === 'done') {
          onDone(data.answer, data.session_id)
        } else if (data.type === 'error') {
          onError(data.content)
        }
      } catch {
        // skip malformed JSON
      }
    }
  }
}

export async function fetchSessions(): Promise<SessionInfo[]> {
  const res = await fetch(`${API_BASE}/chat/sessions`)
  if (!res.ok) throw new Error('Failed to fetch sessions')
  const data = await res.json()
  return data.sessions
}

export async function fetchChatHistory(sessionId: string): Promise<{ session_id: string; history: { role: string; content: string }[] }> {
  const res = await fetch(`${API_BASE}/chat/history/${sessionId}`)
  if (!res.ok) throw new Error('Failed to fetch chat history')
  return res.json()
}

export async function deleteChatHistory(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/history/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete chat history')
}
