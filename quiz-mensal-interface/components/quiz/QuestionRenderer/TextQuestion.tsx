import { Textarea } from '@/components/ui/textarea'
import type { SingleAnswer, MultipleAnswer, QuizQuestion } from '@/types/quiz'
import { memo, useState } from 'react'
import { PenLine } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TextQuestionProps {
  question: QuizQuestion
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  onAnswerChange: (value: SingleAnswer | MultipleAnswer) => void
}

export const TextQuestion = memo(function TextQuestion({
  question,
  selectedAnswer,
  onAnswerChange,
}: TextQuestionProps) {
  const [isFocused, setIsFocused] = useState(false)
  const value = (selectedAnswer as string) || ''
  const maxLength = 1000 // Soft visual limit

  return (
    <div
      className={cn(
        'relative rounded-xl border-2 transition-all duration-300 ease-in-out bg-card overflow-hidden',
        isFocused
          ? 'border-primary shadow-[0_0_0_4px_rgba(var(--primary),0.1)] ring-1 ring-primary/20'
          : 'border-border hover:border-primary/50 hover:bg-muted/10',
      )}
    >
      {/* Header / Label Area */}
      <div className="flex items-center gap-2 px-4 pt-4 pb-2 text-primary/80">
        <PenLine className="w-4 h-4" />
        <span className="text-sm font-medium">Sua Resposta</span>
      </div>

      {/* Text Input Area */}
      <Textarea
        id={`question-${question.id}`}
        name={`question-${question.id}`}
        value={value}
        onChange={(e) => onAnswerChange(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        placeholder="Escreva sua resposta detalhada aqui..."
        className="min-h-32 sm:min-h-40 resize-none border-0 focus-visible:ring-0 shadow-none bg-transparent px-4 text-base leading-relaxed placeholder:text-muted-foreground/50"
      />

      {/* Footer / Character Count */}
      <div className="flex justify-end px-4 py-2 bg-muted/20 border-t border-border/50">
        <span
          className={cn(
            'text-xs font-medium transition-colors',
            value.length > maxLength ? 'text-destructive' : 'text-muted-foreground',
          )}
        >
          {value.length}/{maxLength} caracteres
        </span>
      </div>
    </div>
  )
})
