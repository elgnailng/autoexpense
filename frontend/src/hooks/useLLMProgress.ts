import { useState, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { LLMProgressEvent, PipelineResult } from '../types'

export interface LLMRunOptions {
  provider?: string
  model?: string
  apiKey?: string
  dryRun?: boolean
  force?: boolean
}

export function useLLMProgress() {
  const [progress, setProgress] = useState<LLMProgressEvent | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const cancelRef = useRef<(() => void) | null>(null)
  const queryClient = useQueryClient()

  const start = useCallback(
    (onComplete?: (result: PipelineResult) => void, options?: LLMRunOptions) => {
      // Clean up any existing stream
      cancelRef.current?.()

      setIsStreaming(true)
      setProgress(null)

      // Invalidate status so other pages see pipeline_running=true
      queryClient.invalidateQueries({ queryKey: ['status'] })

      const cleanup = api.streamLLMCategorize(
        (event) => {
          if (event.type === 'heartbeat') return

          setProgress(event)

          if (event.type === 'complete') {
            setIsStreaming(false)
            cancelRef.current = null
            queryClient.invalidateQueries()
            if (onComplete && event.step && event.success !== undefined) {
              onComplete({
                step: event.step,
                success: event.success,
                stats: event.stats || {},
                message: event.message || '',
              })
            }
          }

          if (event.type === 'error') {
            setIsStreaming(false)
            cancelRef.current = null
            queryClient.invalidateQueries({ queryKey: ['status'] })
            if (onComplete) {
              onComplete({
                step: 'llm-categorize',
                success: false,
                stats: {},
                message: event.message || 'Unknown error',
              })
            }
          }
        },
        options,
      )

      cancelRef.current = cleanup
    },
    [queryClient],
  )

  const cancel = useCallback(() => {
    cancelRef.current?.()
    cancelRef.current = null
    setIsStreaming(false)
    setProgress(null)
    queryClient.invalidateQueries({ queryKey: ['status'] })
  }, [queryClient])

  return { progress, isStreaming, start, cancel }
}
