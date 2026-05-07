import { useState, useCallback, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Message } from '../stores/chatStore'
import MermaidChart from './MermaidChart'

interface Props {
  message: Message
}

interface ParsedThinking {
  thinking: string
  answer: string
  isThinking: boolean
}

function parseThinkingContent(content: string): ParsedThinking {
  const thinkStartTag = '<think&gt;'
  const thinkEndTag = '</think&gt;'

  const startIdx = content.indexOf(thinkStartTag)
  if (startIdx === -1) {
    return { thinking: '', answer: content, isThinking: false }
  }

  const endIdx = content.indexOf(thinkEndTag)
  if (endIdx === -1) {
    const thinking = content.slice(startIdx + thinkStartTag.length)
    return { thinking, answer: '', isThinking: true }
  }

  const thinking = content.slice(startIdx + thinkStartTag.length, endIdx)
  const answer = content.slice(endIdx + thinkEndTag.length).replace(/^\n+/, '')
  return { thinking, answer, isThinking: false }
}

function ThinkingBlock({ content, defaultCollapsed = true }: { content: string; defaultCollapsed?: boolean }) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)

  return (
    <div className="mb-3">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-1.5 text-xs text-surface-400 hover:text-primary-500 transition-colors py-1"
      >
        <svg
          className={`w-3.5 h-3.5 transition-transform duration-200 ${collapsed ? '' : 'rotate-90'}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        <span>思考过程</span>
      </button>
      {!collapsed && (
        <div className="mt-2 pl-3 border-l-2 border-surface-200 text-xs text-surface-500 whitespace-pre-wrap leading-relaxed animate-fade-in">
          {content.trim()}
        </div>
      )}
    </div>
  )
}

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2 py-2">
      <div className="flex gap-1">
        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-1.5 h-1.5 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
      <span className="text-xs text-surface-400">思考中...</span>
    </div>
  )
}

function StreamingText({ content }: { content: string }) {
  if (!content) {
    return (
      <div className="loading-dots">
        <span></span>
        <span></span>
        <span></span>
      </div>
    )
  }

  const { thinking, answer, isThinking } = parseThinkingContent(content)

  return (
    <div>
      {isThinking && <ThinkingIndicator />}
      {thinking && !isThinking && (
        <ThinkingBlock content={thinking} defaultCollapsed={true} />
      )}
      {answer ? (
        <div className="whitespace-pre-wrap break-words leading-relaxed text-surface-700 text-sm">
          {answer}
          <span className="inline-block w-[2px] h-[1em] bg-primary-500 ml-[1px] align-middle animate-blink-cursor" />
        </div>
      ) : !isThinking && thinking && (
        <div className="flex items-center gap-2 text-xs text-surface-400">
          <span className="animate-pulse">●</span>
          生成回答中...
        </div>
      )}
    </div>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [text])

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs text-surface-400 hover:text-primary-500 hover:bg-primary-50 transition-all duration-200"
      title="复制回答"
    >
      {copied ? (
        <>
          <svg className="w-3.5 h-3.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-emerald-500">已复制</span>
        </>
      ) : (
        <>
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <span>复制</span>
        </>
      )}
    </button>
  )
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const [sourcesExpanded, setSourcesExpanded] = useState(false)

  const parsed = useMemo(() => parseThinkingContent(message.content), [message.content])
  const displayContent = parsed.answer || message.content
  const thinkingContent = parsed.thinking

  return (
    <div className={`flex gap-3 py-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div className="shrink-0 mt-0.5">
        {isUser ? (
          <div className="w-8 h-8 rounded-xl gradient-primary flex items-center justify-center shadow-md shadow-primary-500/20">
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
            </svg>
          </div>
        ) : (
          <div className="w-8 h-8 rounded-xl bg-white shadow-md border border-surface-100 flex items-center justify-center">
            <svg className="w-4 h-4 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
            </svg>
          </div>
        )}
      </div>

      <div className={`max-w-[75%] min-w-0 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'gradient-primary text-white rounded-tr-md shadow-md shadow-primary-500/15'
              : 'glass rounded-tl-md shadow-sm'
          }`}
        >
          {message.streaming ? (
            <StreamingText content={message.content} />
          ) : (
          <>
            {thinkingContent && !isUser && (
              <ThinkingBlock content={thinkingContent} defaultCollapsed={true} />
            )}
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              className={`prose prose-sm max-w-none ${
                isUser ? 'prose-invert' : 'text-surface-700'
              }`}
              components={{
                h1: ({ children }) => (
                  <h1 className={`text-lg font-bold mt-4 mb-2 first:mt-0 pb-2 border-b ${
                    isUser ? 'border-white/20' : 'border-surface-200'
                  }`}>{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className={`text-base font-bold mt-3 mb-2 first:mt-0 pb-1.5 border-b ${
                    isUser ? 'border-white/20' : 'border-surface-200'
                  }`}>{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-sm font-bold mt-2 mb-1 first:mt-0">{children}</h3>
                ),
                p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
                ul: ({ children }) => <ul className="list-disc ml-4 mb-2 space-y-0.5">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal ml-4 mb-2 space-y-0.5">{children}</ol>,
                li: ({ children }) => <li className="mb-0.5">{children}</li>,
                strong: ({ children }) => <strong className={isUser ? 'text-white font-semibold' : 'text-surface-900 font-semibold'}>{children}</strong>,
                table: ({ children }) => (
                  <div className="my-2 overflow-x-auto rounded-lg border border-surface-200">
                    <table className="min-w-full text-xs">{children}</table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className={isUser ? 'bg-white/10' : 'bg-surface-50'}>{children}</thead>
                ),
                th: ({ children }) => (
                  <th className={`px-3 py-2 text-left font-semibold whitespace-nowrap ${
                    isUser ? 'text-white/90' : 'text-surface-700'
                  }`}>{children}</th>
                ),
                td: ({ children }) => (
                  <td className={`px-3 py-2 border-t ${
                    isUser ? 'border-white/10' : 'border-surface-100'
                  }`}>{children}</td>
                ),
                blockquote: ({ children }) => (
                  <blockquote className={`border-l-3 pl-3 my-2 ${
                    isUser ? 'border-white/40 text-white/80' : 'border-primary-400 text-surface-500'
                  }`}>{children}</blockquote>
                ),
                hr: () => (
                  <hr className={`my-3 ${isUser ? 'border-white/20' : 'border-surface-200'}`} />
                ),
                code: ({ children, className }) => {
                  const isInline = !className
                  const lang = className?.replace('language-', '') || ''
                  const codeText = String(children).replace(/\n$/, '')

                  if (lang === 'mermaid') {
                    return <MermaidChart chart={codeText} />
                  }

                  return isInline ? (
                    <code
                      className={`${
                        isUser ? 'bg-white/20' : 'bg-surface-100'
                      } rounded px-1.5 py-0.5 text-xs font-mono`}
                    >
                      {children}
                    </code>
                  ) : (
                    <div className={`relative my-2 rounded-lg overflow-hidden ${
                      isUser ? 'bg-white/10' : 'bg-surface-800'
                    }`}>
                      <div className={`flex items-center justify-between px-3 py-1.5 text-xs ${
                        isUser ? 'bg-white/5 text-white/50' : 'bg-surface-900/50 text-surface-400'
                      }`}>
                        <span>{lang || 'code'}</span>
                        <CopyButton text={codeText} />
                      </div>
                      <pre className="p-3 overflow-x-auto">
                        <code className={`text-xs font-mono ${
                          isUser ? 'text-white/90' : 'text-surface-100'
                        }`}>{children}</code>
                      </pre>
                    </div>
                  )
                },
              }}
            >
              {displayContent}
            </ReactMarkdown>
          </>
          )}
        </div>

        {!isUser && !message.streaming && (
          <div className="flex items-center gap-1 mt-1.5 px-1">
            <CopyButton text={displayContent} />
          </div>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2">
            <button
              onClick={() => setSourcesExpanded(!sourcesExpanded)}
              className="flex items-center gap-1.5 text-xs text-surface-400 hover:text-primary-500 transition-colors px-1"
            >
              <svg
                className={`w-3.5 h-3.5 transition-transform ${sourcesExpanded ? 'rotate-90' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <span>参考文档 ({message.sources.length})</span>
            </button>

            {sourcesExpanded && (
              <div className="mt-2 space-y-2 animate-fade-in">
                {message.sources.map((source, i) => (
                  <div
                    key={i}
                    className="glass rounded-lg px-3 py-2 flex items-start gap-2 group hover:shadow-sm transition-shadow"
                  >
                    <svg
                      className="w-4 h-4 text-primary-400 mt-0.5 shrink-0"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-surface-600 truncate">{source.source}</p>
                      <p className="text-xs text-surface-400 mt-0.5 line-clamp-2">{source.content}</p>
                    </div>
                    {source.score !== undefined && (
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full shrink-0 ${
                        source.score > 0.8 ? 'bg-emerald-50 text-emerald-600' :
                        source.score > 0.5 ? 'bg-amber-50 text-amber-600' :
                        'bg-surface-100 text-surface-500'
                      }`}>
                        {(source.score * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
