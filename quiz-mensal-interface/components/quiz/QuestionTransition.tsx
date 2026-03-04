'use client'

import { ReactNode, useEffect, useState, useRef } from 'react'
import { cn } from '@/lib/utils'

interface QuestionTransitionProps {
  /** Unique identifier for the question - triggers animation on change */
  questionId: string
  /** Content to render with transition */
  children: ReactNode
  /** Navigation direction for slide animation */
  direction?: 'forward' | 'backward'
  /** Duration of animation in milliseconds */
  duration?: number
}

/**
 * QuestionTransition - Smooth animation wrapper for quiz questions
 *
 * IMPORTANT: Does NOT store children in state to prevent remounting
 * which causes input focus loss. Uses CSS-only animations.
 */
export function QuestionTransition({
  questionId,
  children,
  direction = 'forward',
  duration = 200,
}: QuestionTransitionProps) {
  const [animationClass, setAnimationClass] = useState('')
  const prevQuestionId = useRef(questionId)

  // Only trigger animation when questionId actually changes
  useEffect(() => {
    if (questionId !== prevQuestionId.current) {
      // Set animation class based on direction
      const enterClass =
        direction === 'forward'
          ? 'animate-in fade-in-0 slide-in-from-right-4'
          : 'animate-in fade-in-0 slide-in-from-left-4'

      setAnimationClass(enterClass)
      prevQuestionId.current = questionId

      // Clear animation class after duration
      const timeout = setTimeout(() => {
        setAnimationClass('')
      }, duration)

      return () => clearTimeout(timeout)
    }
  }, [questionId, direction, duration])

  return <div className={cn('duration-200', animationClass)}>{children}</div>
}

export default QuestionTransition
