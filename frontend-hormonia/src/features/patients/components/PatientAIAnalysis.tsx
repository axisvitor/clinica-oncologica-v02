import React from 'react'
import { Brain } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { AIChatInterface } from '@/features/ai/AIChatInterface'
import { TabsContent } from '@/components/ui/tabs'

interface PatientAIAnalysisProps {
  patientId: string
  patientName: string
  showChat?: boolean
}

export function PatientAIAnalysis({
  patientId,
  patientName,
  showChat = true
}: PatientAIAnalysisProps) {
  if (!showChat) {
    return null
  }

  return (
    <TabsContent value="ai-chat" className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Chat com IA - Contexto do Paciente
          </CardTitle>
          <CardDescription>
            Tire dúvidas e obtenha orientações sobre {patientName}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {patientId && <AIChatInterface patientId={patientId} />}
        </CardContent>
      </Card>
    </TabsContent>
  )
}
