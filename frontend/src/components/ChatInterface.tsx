import { useState, useEffect, useCallback } from 'react'
import { sendStreamMessage } from '../api/chat'
import { useChatStore } from '../stores/chatStore'
import MessageList from './MessageList'
import ChatInput from './ChatInput'

export default function ChatInterface() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { messages, sessionId, sessions, resetChat, loadSessions, switchSession, removeSession } = useChatStore()
  const [isStreaming, setIsStreaming] = useState(false)

  useEffect(() => {
    loadSessions()
  }, [])

  const handleSend = useCallback(async (question: string) => {
    const store = useChatStore.getState()
    const assistantMsgId = crypto.randomUUID()

    store.addMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: question,
      timestamp: new Date(),
    })

    store.addMessage({
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      streaming: true,
    })

    setIsStreaming(true)

    let sources: any[] | undefined

    try {
      await sendStreamMessage(
        {
          question,
          session_id: store.sessionId || undefined,
          user_id: store.userId,
        },
        (srcs, sid) => {
          sources = srcs
          useChatStore.getState().setSessionId(sid)
        },
        (token) => {
          useChatStore.getState().updateStreamingMessage(assistantMsgId, token)
        },
        (_answer, sid) => {
          useChatStore.getState().finalizeStreamingMessage(assistantMsgId, sources)
          useChatStore.getState().setSessionId(sid)
          setIsStreaming(false)
          loadSessions()
        },
        (error) => {
          console.error('Stream error:', error)
          useChatStore.getState().finalizeStreamingMessage(assistantMsgId, sources)
          setIsStreaming(false)
        }
      )
    } catch (error) {
      console.error('Chat error:', error)
      useChatStore.getState().finalizeStreamingMessage(assistantMsgId, sources)
      setIsStreaming(false)
    }
  }, [])

  const handleNewChat = () => {
    resetChat()
    setSidebarOpen(false)
  }

  const handleSwitchSession = async (sid: string) => {
    await switchSession(sid)
    setSidebarOpen(false)
  }

  const handleDeleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation()
    await removeSession(sid)
  }

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000)
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    if (isToday) {
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }
    return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="flex h-screen gradient-mesh overflow-hidden">
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed lg:relative z-30 h-full transition-all duration-300 ease-in-out ${
          sidebarOpen ? 'w-72 translate-x-0' : 'w-0 -translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="h-full w-72 glass-dark text-white flex flex-col shadow-2xl">
          <div className="p-5 border-b border-white/10">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl gradient-primary flex items-center justify-center shadow-lg shadow-primary-500/30">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <div>
                <h2 className="text-sm font-semibold">对话历史</h2>
                <p className="text-xs text-white/50">漏洞智能客服</p>
              </div>
            </div>
          </div>

          <div className="p-4">
            <button
              onClick={handleNewChat}
              className="w-full px-4 py-2.5 bg-white/10 hover:bg-white/20 rounded-xl text-sm font-medium transition-all duration-200 flex items-center justify-center gap-2 border border-white/10"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              新建对话
            </button>
          </div>

          <div className="flex-1 overflow-y-auto scrollbar-thin px-3 pb-3 space-y-1">
            {sessions.length === 0 && (
              <p className="text-xs text-white/30 text-center py-6">暂无对话记录</p>
            )}
            {sessions.map((s) => (
              <div
                key={s.session_id}
                onClick={() => handleSwitchSession(s.session_id)}
                className={`group flex items-start gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-150 ${
                  sessionId === s.session_id
                    ? 'bg-white/15 border border-white/20'
                    : 'hover:bg-white/8 border border-transparent'
                }`}
              >
                <svg className="w-4 h-4 text-white/40 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white/90 truncate leading-snug">
                    {s.title || '未命名对话'}
                  </p>
                  <p className="text-[10px] text-white/30 mt-0.5">
                    {formatTime(s.updated_at)}
                  </p>
                </div>
                <button
                  onClick={(e) => handleDeleteSession(e, s.session_id)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-white/10 rounded-lg transition-all shrink-0"
                  title="删除对话"
                >
                  <svg className="w-3.5 h-3.5 text-white/50 hover:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            ))}
          </div>

          <div className="p-4 border-t border-white/10">
            <p className="text-xs text-white/30 text-center">RAG + Milvus 漏洞智能客服</p>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="glass border-b border-white/30 px-5 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 hover:bg-white/50 rounded-xl transition-colors"
            >
              <svg className="w-5 h-5 text-surface-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg gradient-primary flex items-center justify-center shadow-md shadow-primary-500/20">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <div>
                <h1 className="text-sm font-semibold text-surface-800">漏洞智能客服</h1>
                <p className="text-xs text-surface-400">基于 RAG 的漏洞安全问答</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-600 rounded-full text-xs font-medium">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse-soft" />
              在线
            </div>
          </div>
        </header>

        <MessageList messages={messages} isLoading={isStreaming} />

        <ChatInput onSend={handleSend} disabled={isStreaming} />
      </div>
    </div>
  )
}
