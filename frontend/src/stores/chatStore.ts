import { create } from 'zustand'
import { SessionInfo, fetchSessions, fetchChatHistory, deleteChatHistory } from '../api/chat'

export interface SourceDoc {
  content: string
  source: string
  score?: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceDoc[]
  timestamp: Date
  streaming?: boolean
}

function getOrCreateUserId(): string {
  const key = 'rag_user_id'
  let userId = localStorage.getItem(key)
  if (!userId) {
    userId = crypto.randomUUID()
    localStorage.setItem(key, userId)
  }
  return userId
}

interface ChatStore {
  messages: Message[]
  sessionId: string | null
  userId: string
  sessions: SessionInfo[]
  isLoading: boolean
  addMessage: (msg: Message) => void
  updateStreamingMessage: (id: string, token: string) => void
  finalizeStreamingMessage: (id: string, sources?: SourceDoc[]) => void
  setLoading: (loading: boolean) => void
  setSessionId: (sessionId: string) => void
  resetChat: () => void
  loadSessions: () => Promise<void>
  switchSession: (sessionId: string) => Promise<void>
  removeSession: (sessionId: string) => Promise<void>
  setMessages: (msgs: Message[]) => void
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  sessionId: null,
  userId: getOrCreateUserId(),
  sessions: [],
  isLoading: false,
  addMessage: (msg) => set((state) => ({
    messages: [...state.messages, msg]
  })),
  updateStreamingMessage: (id, token) => set((state) => ({
    messages: state.messages.map((msg) =>
      msg.id === id ? { ...msg, content: msg.content + token } : msg
    )
  })),
  finalizeStreamingMessage: (id, sources) => set((state) => ({
    messages: state.messages.map((msg) =>
      msg.id === id ? { ...msg, streaming: false, sources } : msg
    )
  })),
  setLoading: (loading) => set({ isLoading: loading }),
  setSessionId: (sessionId) => set({ sessionId }),
  setMessages: (msgs) => set({ messages: msgs }),
  resetChat: () => set({ messages: [], sessionId: null }),
  loadSessions: async () => {
    try {
      const sessions = await fetchSessions()
      set({ sessions })
    } catch (e) {
      console.error('Failed to load sessions:', e)
    }
  },
  switchSession: async (sessionId: string) => {
    try {
      const data = await fetchChatHistory(sessionId)
      const msgs: Message[] = data.history.map((h, i) => ({
        id: `${sessionId}-${i}`,
        role: h.role as 'user' | 'assistant',
        content: h.content,
        timestamp: new Date(),
        streaming: false,
      }))
      set({ sessionId, messages: msgs })
    } catch (e) {
      console.error('Failed to switch session:', e)
    }
  },
  removeSession: async (sessionId: string) => {
    try {
      await deleteChatHistory(sessionId)
      const sessions = get().sessions.filter(s => s.session_id !== sessionId)
      if (get().sessionId === sessionId) {
        set({ sessions, sessionId: null, messages: [] })
      } else {
        set({ sessions })
      }
    } catch (e) {
      console.error('Failed to remove session:', e)
    }
  },
}))
