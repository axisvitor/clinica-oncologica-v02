import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { QuizQuestion, SingleAnswer, MultipleAnswer, OtherAnswer } from "@/types/quiz"
import { memo } from "react"

interface SingleChoiceProps {
  question: QuizQuestion
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  otherText: string
  onAnswerChange: (value: SingleAnswer | MultipleAnswer) => void
  onOtherTextChange: (text: string, otherOptionValue: string) => void
}

export const SingleChoice = memo(function SingleChoice({
  question,
  selectedAnswer,
  otherText,
  onAnswerChange,
  onOtherTextChange,
}: SingleChoiceProps) {
  const singleValue = typeof selectedAnswer === 'object' && selectedAnswer && 'value' in selectedAnswer
    ? selectedAnswer.value
    : (selectedAnswer as string || "")

  // Find the "other" option value dynamically
  const otherOption = question.options?.find(opt => {
    if (typeof opt === 'string') return false
    return opt.allow_other === true ||
           opt.value.toLowerCase() === 'other' ||
           opt.value.toLowerCase() === 'outro' ||
           opt.value.toLowerCase() === 'outra'
  })
  const otherOptionValue = typeof otherOption === 'object' ? otherOption.value : 'other'

  return (
    <div className="space-y-3">
      <RadioGroup
        value={singleValue}
        onValueChange={(value) => {
          if (value === otherOptionValue) {
            onAnswerChange({ value: otherOptionValue, customText: otherText } as OtherAnswer)
          } else {
            onAnswerChange(value)
          }
        }}
        className="space-y-3"
      >
        {question.options?.map((option, index) => {
          const optionValue = typeof option === 'string' ? option : option.value
          const optionText = typeof option === 'string' ? option : option.text
          return (
            <div
              key={typeof option === 'string' ? index : option.id}
              className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer"
            >
              <RadioGroupItem value={optionValue} id={`option-${index}`} />
              <Label
                htmlFor={`option-${index}`}
                className="flex-1 cursor-pointer font-medium"
              >
                {optionText}
              </Label>
            </div>
          )
        })}

        {/* "Outra" option if allowed */}
        {question.allow_other && (
          <div className="space-y-3">
            <div className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer">
              <RadioGroupItem value={otherOptionValue} id="option-other" />
              <Label
                htmlFor="option-other"
                className="flex-1 cursor-pointer font-medium"
              >
                Outra
              </Label>
            </div>

            {/* Show text input when "Outra" is selected */}
            {singleValue === otherOptionValue && (
              <Textarea
                value={otherText}
                onChange={(e) => onOtherTextChange(e.target.value, otherOptionValue)}
                placeholder="Digite sua resposta personalizada..."
                className="min-h-24 resize-none ml-7"
                required
              />
            )}
          </div>
        )}
      </RadioGroup>
    </div>
  )
})
