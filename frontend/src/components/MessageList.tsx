import { useRef, useEffect } from 'react'
import { Message } from '../stores/chatStore'
import MessageBubble from './MessageBubble'

interface Props {
  messages: Message[]
  isLoading: boolean
}

const SUGGESTIONS = [
  { icon: '�', text: '有哪些SQL注入漏洞？' },
  { icon: '�️', text: '如何修复XSS跨站脚本漏洞？' },
  { icon: '⚠️', text: '高危漏洞有哪些？' },
  { icon: '�', text: '1039家校通有什么漏洞？' },
]

export default function MessageList({ messages, isLoading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  return (
    <div className="flex-1 overflow-y-auto scrollbar-thin">
      {messages.length === 0 && !isLoading ? (
        <div className="flex flex-col items-center justify-center h-full px-6 animate-fade-in">
          {/* Hero Section */}
          <div className="text-center max-w-lg">
            <div className="w-20 h-20 mx-auto mb-6 rounded-2xl gradient-primary flex items-center justify-center shadow-xl shadow-primary-500/25">
              <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-surface-800 mb-2">你好，有什么可以帮你的？</h2>
            <p className="text-surface-400 text-sm mb-8">我是基于 RAG 技术的漏洞智能客服，可以查询和解答安全漏洞相关问题</p>

            {/* Suggestion Cards */}
            <div className="grid grid-cols-2 gap-3">
              {SUGGESTIONS.map((s, i) => (
                <div
                  key={i}
                  className="group glass rounded-xl p-4 text-left cursor-pointer hover:shadow-lg hover:shadow-primary-500/10 hover:-translate-y-0.5 transition-all duration-200"
                  style={{ animationDelay: `${i * 100}ms` }}
                >
                  <span className="text-2xl mb-2 block">{s.icon}</span>
                  <p className="text-sm text-surface-600 group-hover:text-primary-600 transition-colors">{s.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-1">
          {messages.map((msg) => (
            <div key={msg.id} className="animate-slide-up">
              <MessageBubble message={msg} />
            </div>
          ))}

          {isLoading && messages.length > 0 && messages[messages.length - 1].role === 'user' && (
            <div className="flex justify-start animate-fade-in">
              <div className="glass rounded-2xl rounded-bl-md px-5 py-3.5 shadow-sm">
                <div className="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
