import type { QuizQuestion, SingleAnswer, MultipleAnswer } from "@/types/quiz"
import { SingleChoice } from "./SingleChoice"
import { MultipleChoice } from "./MultipleChoice"
import { Scale } from "./Scale"
import { YesNo } from "./YesNo"
import { TextQuestion } from "./TextQuestion"

interface QuestionRendererProps {
  question: QuizQuestion
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  otherText: string
  onAnswerChange: (value: SingleAnswer | MultipleAnswer) => void
  onOtherTextChange: (text: string, otherOptionValue: string) => void
}

export function QuestionRenderer({
  question,
  selectedAnswer,
  otherText,
  onAnswerChange,
  onOtherTextChange,
}: QuestionRendererProps) {
  switch (question.type) {
    case "single_choice":
      return (
        <SingleChoice
          question={question}
          selectedAnswer={selectedAnswer}
          otherText={otherText}
          onAnswerChange={onAnswerChange}
          onOtherTextChange={onOtherTextChange}
        />
      )

    case "multiple_choice":
      return (
        <MultipleChoice
          question={question}
          selectedAnswer={selectedAnswer}
          otherText={otherText}
          onAnswerChange={onAnswerChange}
          onOtherTextChange={onOtherTextChange}
        />
      )

    case "scale":
      return (
        <Scale
          question={question}
          selectedAnswer={selectedAnswer}
          onAnswerChange={onAnswerChange}
        />
      )

    case "yes_no":
      return (
        <YesNo
          selectedAnswer={selectedAnswer}
          onAnswerChange={onAnswerChange}
        />
      )

    case "text":
      return (
        <TextQuestion
          selectedAnswer={selectedAnswer}
          onAnswerChange={onAnswerChange}
        />
      )

    default:
      return <p>Tipo de questão não suportado</p>
  }
}
