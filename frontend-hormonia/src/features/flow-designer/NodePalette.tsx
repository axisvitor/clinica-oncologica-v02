import React from 'react'
import { 
  MessageSquare, 
  GitBranch, 
  Clock, 
  Zap, 
  Play, 
  Square,
  Bot,
  HelpCircle,
  Webhook
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { FlowNodeType } from '@/types/flow-designer'

interface NodePaletteProps {
  onAddNode: (nodeType: string, position: { x: number; y: number }) => void
}

interface NodeTypeInfo {
  type: FlowNodeType
  label: string
  description: string
  icon: React.ReactNode
  color: string
}

const nodeTypes: NodeTypeInfo[] = [
  {
    type: FlowNodeType.START,
    label: 'Início',
    description: 'Ponto de entrada do fluxo',
    icon: <Play className="h-4 w-4" />,
    color: 'text-green-600'
  },
  {
    type: FlowNodeType.MESSAGE,
    label: 'Mensagem',
    description: 'Enviar mensagem para o paciente',
    icon: <MessageSquare className="h-4 w-4" />,
    color: 'text-blue-600'
  },
  {
    type: FlowNodeType.CONDITION,
    label: 'Condição',
    description: 'Decisão baseada em condições',
    icon: <GitBranch className="h-4 w-4" />,
    color: 'text-yellow-600'
  },
  {
    type: FlowNodeType.DELAY,
    label: 'Atraso',
    description: 'Aguardar por um período',
    icon: <Clock className="h-4 w-4" />,
    color: 'text-purple-600'
  },
  {
    type: FlowNodeType.ACTION,
    label: 'Ação',
    description: 'Executar uma ação específica',
    icon: <Zap className="h-4 w-4" />,
    color: 'text-orange-600'
  },
  {
    type: FlowNodeType.AI_RESPONSE,
    label: 'Resposta IA',
    description: 'Gerar resposta com IA',
    icon: <Bot className="h-4 w-4" />,
    color: 'text-indigo-600'
  },
  {
    type: FlowNodeType.QUIZ,
    label: 'Quiz',
    description: 'Questionário para o paciente',
    icon: <HelpCircle className="h-4 w-4" />,
    color: 'text-pink-600'
  },
  {
    type: FlowNodeType.WEBHOOK,
    label: 'Webhook',
    description: 'Chamar API externa',
    icon: <Webhook className="h-4 w-4" />,
    color: 'text-gray-600'
  },
  {
    type: FlowNodeType.END,
    label: 'Fim',
    description: 'Finalizar o fluxo',
    icon: <Square className="h-4 w-4" />,
    color: 'text-red-600'
  }
]

export function NodePalette({ onAddNode }: NodePaletteProps) {
  const handleDragStart = (e: React.DragEvent, nodeType: string) => {
    e.dataTransfer.setData('application/node-type', nodeType)
    e.dataTransfer.effectAllowed = 'copy'
  }

  const handleAddNodeClick = (nodeType: string) => {
    // Add node at a default position (center of canvas)
    onAddNode(nodeType, { x: 300, y: 200 })
  }

  return (
    <Card className="h-full rounded-none border-t-0 border-l-0 border-b-0">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Componentes</CardTitle>
      </CardHeader>
      
      <CardContent className="p-0">
        <div className="space-y-1">
          {nodeTypes.map((nodeType) => (
            <div
              key={nodeType.type}
              className="group"
            >
              <Button
                variant="ghost"
                className="w-full justify-start h-auto p-3 hover:bg-gray-50"
                draggable
                onDragStart={(e) => handleDragStart(e, nodeType.type)}
                onClick={() => handleAddNodeClick(nodeType.type)}
              >
                <div className="flex items-start gap-3 w-full">
                  <div className={`flex-shrink-0 ${nodeType.color}`}>
                    {nodeType.icon}
                  </div>
                  <div className="flex-1 text-left">
                    <div className="font-medium text-sm">
                      {nodeType.label}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {nodeType.description}
                    </div>
                  </div>
                </div>
              </Button>
            </div>
          ))}
        </div>

        {/* Instructions */}
        <div className="p-4 mt-6 border-t">
          <div className="text-xs text-muted-foreground space-y-2">
            <div className="font-medium">Como usar:</div>
            <div>• Clique para adicionar ao canvas</div>
            <div>• Arraste para posicionar</div>
            <div>• Use modo "Conectar" para ligar nós</div>
          </div>
        </div>

        {/* Quick Templates */}
        <div className="p-4 border-t">
          <div className="text-xs font-medium text-muted-foreground mb-2">
            Templates Rápidos
          </div>
          <div className="space-y-1">
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs"
              onClick={() => {
                // Add a simple message flow
                onAddNode(FlowNodeType.START, { x: 100, y: 100 })
                setTimeout(() => {
                  onAddNode(FlowNodeType.MESSAGE, { x: 100, y: 200 })
                }, 100)
                setTimeout(() => {
                  onAddNode(FlowNodeType.END, { x: 100, y: 300 })
                }, 200)
              }}
            >
              Fluxo Simples
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs"
              onClick={() => {
                // Add a conditional flow
                onAddNode(FlowNodeType.START, { x: 100, y: 100 })
                setTimeout(() => {
                  onAddNode(FlowNodeType.MESSAGE, { x: 100, y: 200 })
                }, 100)
                setTimeout(() => {
                  onAddNode(FlowNodeType.CONDITION, { x: 100, y: 300 })
                }, 200)
                setTimeout(() => {
                  onAddNode(FlowNodeType.MESSAGE, { x: 50, y: 400 })
                }, 300)
                setTimeout(() => {
                  onAddNode(FlowNodeType.MESSAGE, { x: 150, y: 400 })
                }, 400)
              }}
            >
              Fluxo Condicional
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs"
              onClick={() => {
                // Add an AI flow
                onAddNode(FlowNodeType.START, { x: 100, y: 100 })
                setTimeout(() => {
                  onAddNode(FlowNodeType.MESSAGE, { x: 100, y: 200 })
                }, 100)
                setTimeout(() => {
                  onAddNode(FlowNodeType.AI_RESPONSE, { x: 100, y: 300 })
                }, 200)
                setTimeout(() => {
                  onAddNode(FlowNodeType.END, { x: 100, y: 400 })
                }, 300)
              }}
            >
              Fluxo com IA
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
