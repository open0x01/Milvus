import { useEffect, useRef, useState } from 'react'

interface Props {
  chart: string
}

let mermaidCounter = 0
let mermaidInitialized = false

export default function MermaidChart({ chart }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [svg, setSvg] = useState<string>('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    const render = async () => {
      try {
        const mermaid = (await import('mermaid')).default

        if (!mermaidInitialized) {
          mermaid.initialize({
            startOnLoad: false,
            theme: 'default',
            securityLevel: 'loose',
            fontFamily: 'Inter, -apple-system, sans-serif',
          })
          mermaidInitialized = true
        }

        const id = `mermaid-${++mermaidCounter}`
        const { svg: renderedSvg } = await mermaid.render(id, chart.trim())

        if (!cancelled) {
          setSvg(renderedSvg)
          setError(null)
          setLoading(false)
        }
      } catch (e) {
        if (!cancelled) {
          setError(String(e))
          setLoading(false)
        }
      }
    }
    render()

    return () => {
      cancelled = true
    }
  }, [chart])

  if (loading) {
    return (
      <div className="my-2 flex items-center justify-center rounded-lg bg-white p-6 border border-surface-100">
        <div className="loading-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="my-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2">
        <p className="text-xs text-red-500 font-medium mb-1">Mermaid 渲染失败</p>
        <pre className="text-xs text-red-400 overflow-x-auto whitespace-pre-wrap">{chart}</pre>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="my-2 flex justify-center overflow-x-auto rounded-lg bg-white p-4 border border-surface-100"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
