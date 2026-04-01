import { useState, useRef, useCallback } from 'react'

export interface SwipeState {
  x: number
  y: number
  isDragging: boolean
  direction: 'right' | 'left' | 'up' | 'down' | null
}

interface UseSwipeOptions {
  onSwipeRight?: () => void
  onSwipeLeft?: () => void
  onSwipeUp?: () => void
  onSwipeDown?: () => void
  threshold?: number
  velocityThreshold?: number
}

interface TrackingRef {
  startX: number
  startY: number
  startTime: number
  pointerId: number | null
}

function getDirection(dx: number, dy: number): 'right' | 'left' | 'up' | 'down' | null {
  if (Math.abs(dx) < 5 && Math.abs(dy) < 5) return null
  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx > 0 ? 'right' : 'left'
  }
  return dy > 0 ? 'down' : 'up'
}

export function useSwipe(options: UseSwipeOptions = {}) {
  const {
    onSwipeRight,
    onSwipeLeft,
    onSwipeUp,
    onSwipeDown,
    threshold = 100,
    velocityThreshold = 0.5,
  } = options

  const [state, setState] = useState<SwipeState>({
    x: 0,
    y: 0,
    isDragging: false,
    direction: null,
  })

  const tracking = useRef<TrackingRef>({
    startX: 0,
    startY: 0,
    startTime: 0,
    pointerId: null,
  })

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    // Only track primary pointer (left mouse / single touch)
    if (e.button !== 0) return

    const target = e.currentTarget as HTMLElement
    target.setPointerCapture(e.pointerId)

    tracking.current = {
      startX: e.clientX,
      startY: e.clientY,
      startTime: Date.now(),
      pointerId: e.pointerId,
    }

    setState({
      x: 0,
      y: 0,
      isDragging: true,
      direction: null,
    })
  }, [])

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (tracking.current.pointerId !== e.pointerId) return

    const dx = e.clientX - tracking.current.startX
    const dy = e.clientY - tracking.current.startY
    const direction = getDirection(dx, dy)

    setState({
      x: dx,
      y: dy,
      isDragging: true,
      direction,
    })
  }, [])

  const handlePointerEnd = useCallback((e: React.PointerEvent) => {
    if (tracking.current.pointerId !== e.pointerId) return

    const dx = e.clientX - tracking.current.startX
    const dy = e.clientY - tracking.current.startY
    const elapsed = Date.now() - tracking.current.startTime
    const distance = Math.sqrt(dx * dx + dy * dy)
    const velocity = elapsed > 0 ? distance / elapsed : 0

    tracking.current.pointerId = null

    const meetsThreshold = Math.abs(dx) > threshold || Math.abs(dy) > threshold
    const meetsVelocity = velocity > velocityThreshold && distance > 30

    if (meetsThreshold || meetsVelocity) {
      const direction = getDirection(dx, dy)
      if (direction === 'right') onSwipeRight?.()
      else if (direction === 'left') onSwipeLeft?.()
      else if (direction === 'up') onSwipeUp?.()
      else if (direction === 'down') onSwipeDown?.()
    }

    setState({
      x: 0,
      y: 0,
      isDragging: false,
      direction: null,
    })
  }, [threshold, velocityThreshold, onSwipeRight, onSwipeLeft, onSwipeUp, onSwipeDown])

  const onPointerUp = handlePointerEnd

  const onPointerCancel = useCallback((e: React.PointerEvent) => {
    if (tracking.current.pointerId !== e.pointerId) return
    tracking.current.pointerId = null
    setState({ x: 0, y: 0, isDragging: false, direction: null })
  }, [])

  return {
    state,
    handlers: {
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel,
    },
  }
}
