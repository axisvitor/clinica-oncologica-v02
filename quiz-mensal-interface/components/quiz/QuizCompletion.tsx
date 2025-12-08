import { Card } from "@/components/ui/card"
import { CheckCircle } from "lucide-react"
import { memo } from "react"

interface QuizCompletionProps {
  expiresAt: string
}

export const QuizCompletion = memo(function QuizCompletion({ expiresAt }: QuizCompletionProps) {
  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md mx-auto space-y-6">
        <Card className="p-8 text-center space-y-6">
          <div className="w-20 h-20 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto">
            <CheckCircle className="w-12 h-12 text-green-600 dark:text-green-400" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-bold">Questionário Concluído!</h2>
            <p className="text-muted-foreground">
              Obrigado por responder ao questionário mensal. Suas respostas foram registradas com sucesso.
            </p>
          </div>
          <div className="pt-4 border-t space-y-2">
            <p className="text-sm text-muted-foreground">
              Suas respostas ajudam nossa equipe a acompanhar seu bem-estar e oferecer o melhor cuidado possível.
            </p>
          </div>
        </Card>
      </div>
    </div>
  )
})
