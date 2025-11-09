import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { AlertTriangle, Settings } from 'lucide-react'
import { 
  FlowDesign, 
  FlowNode, 
  FlowValidationResult,
  FlowNodeType 
} from '@/lib/types/flow-designer'

interface PropertyPanelProps {
  design: FlowDesign
  selectedNodes: string[]
  selectedConnections: string[]
  onUpdateNode: (nodeId: string, updates: Partial<FlowNode>) => void
  validation?: FlowValidationResult | null
}

export function PropertyPanel({
  design,
  selectedNodes,
  selectedConnections,
  onUpdateNode,
  validation
}: PropertyPanelProps) {
  const selectedNode = selectedNodes.length === 1 
    ? design.nodes.find(node => node.id === selectedNodes[0])
    : null

  const selectedConnection = selectedConnections.length === 1
    ? design.connections.find(conn => conn.id === selectedConnections[0])
    : null

  const nodeErrors = validation?.errors.filter(error => 
    selectedNode && error.node_id === selectedNode.id
  ) || []

  const handleNodeUpdate = (field: string, value: any) => {
    if (!selectedNode) return

    if (field.startsWith('data.')) {
      const dataField = field.replace('data.', '')
      onUpdateNode(selectedNode.id, {
        data: {
          ...selectedNode.data,
          [dataField]: value
        }
      })
    } else if (field.startsWith('data.config.')) {
      const configField = field.replace('data.config.', '')
      onUpdateNode(selectedNode.id, {
        data: {
          ...selectedNode.data,
          config: {
            ...selectedNode.data.config,
            [configField]: value
          }
        }
      })
    } else {
      onUpdateNode(selectedNode.id, { [field]: value })
    }
  }

  if (!selectedNode && !selectedConnection) {
    return (
      <Card className="h-full rounded-none border-t-0 border-r-0 border-b-0">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Propriedades
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center text-muted-foreground py-8">
            <Settings className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Selecione um nó ou conexão para editar suas propriedades</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full rounded-none border-t-0 border-r-0 border-b-0">
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <Settings className="h-4 w-4" />
          Propriedades
          {nodeErrors.length > 0 && (
            <Badge variant="destructive" className="text-xs">
              {nodeErrors.length} erro(s)
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {selectedNode && (
          <>
            {/* Node Errors */}
            {nodeErrors.length > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <div className="flex items-center gap-2 text-red-800 font-medium text-sm mb-2">
                  <AlertTriangle className="h-4 w-4" />
                  Erros de Validação
                </div>
                <div className="space-y-1">
                  {nodeErrors.map(error => (
                    <div key={error.id} className="text-xs text-red-600">
                      • {error.message}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Basic Properties */}
            <div className="space-y-3">
              <div>
                <Label htmlFor="node-label" className="text-xs">Nome do Nó</Label>
                <Input
                  id="node-label"
                  value={selectedNode.data.label}
                  onChange={(e) => handleNodeUpdate('data.label', e.target.value)}
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="node-description" className="text-xs">Descrição</Label>
                <Textarea
                  id="node-description"
                  value={selectedNode.data.description || ''}
                  onChange={(e) => handleNodeUpdate('data.description', e.target.value)}
                  className="mt-1"
                  rows={2}
                />
              </div>

              <div>
                <Label className="text-xs">Tipo</Label>
                <div className="mt-1">
                  <Badge variant="outline">{selectedNode.type}</Badge>
                </div>
              </div>
            </div>

            <Separator />

            {/* Type-specific Properties */}
            {selectedNode.type === FlowNodeType.MESSAGE && (
              <MessageNodeProperties 
                node={selectedNode} 
                onUpdate={handleNodeUpdate} 
              />
            )}

            {selectedNode.type === FlowNodeType.CONDITION && (
              <ConditionNodeProperties 
                node={selectedNode} 
                onUpdate={handleNodeUpdate} 
              />
            )}

            {selectedNode.type === FlowNodeType.DELAY && (
              <DelayNodeProperties 
                node={selectedNode} 
                onUpdate={handleNodeUpdate} 
              />
            )}

            {selectedNode.type === FlowNodeType.ACTION && (
              <ActionNodeProperties 
                node={selectedNode} 
                onUpdate={handleNodeUpdate} 
              />
            )}

            {selectedNode.type === FlowNodeType.AI_RESPONSE && (
              <AIResponseNodeProperties 
                node={selectedNode} 
                onUpdate={handleNodeUpdate} 
              />
            )}

            <Separator />

            {/* Position */}
            <div className="space-y-2">
              <Label className="text-xs">Posição</Label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label htmlFor="node-x" className="text-xs">X</Label>
                  <Input
                    id="node-x"
                    type="number"
                    value={selectedNode.position.x}
                    onChange={(e) => handleNodeUpdate('position', {
                      ...selectedNode.position,
                      x: parseInt(e.target.value) || 0
                    })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="node-y" className="text-xs">Y</Label>
                  <Input
                    id="node-y"
                    type="number"
                    value={selectedNode.position.y}
                    onChange={(e) => handleNodeUpdate('position', {
                      ...selectedNode.position,
                      y: parseInt(e.target.value) || 0
                    })}
                    className="mt-1"
                  />
                </div>
              </div>
            </div>
          </>
        )}

        {selectedConnection && (
          <div className="space-y-3">
            <div>
              <Label htmlFor="conn-label" className="text-xs">Rótulo da Conexão</Label>
              <Input
                id="conn-label"
                value={selectedConnection.label || ''}
                onChange={(e) => {
                  // Handle connection update
                }}
                className="mt-1"
              />
            </div>

            <div>
              <Label htmlFor="conn-condition" className="text-xs">Condição</Label>
              <Input
                id="conn-condition"
                value={selectedConnection.condition || ''}
                onChange={(e) => {
                  // Handle connection update
                }}
                className="mt-1"
                placeholder="ex: response == 'sim'"
              />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// Type-specific property components
function MessageNodeProperties({ node, onUpdate }: { node: FlowNode; onUpdate: (field: string, value: any) => void }) {
  return (
    <div className="space-y-3">
      <div>
        <Label htmlFor="message-content" className="text-xs">Conteúdo da Mensagem</Label>
        <Textarea
          id="message-content"
          value={node.data.config['content'] || ''}
          onChange={(e) => onUpdate('data.config.content', e.target.value)}
          className="mt-1"
          rows={3}
        />
      </div>

      <div>
        <Label htmlFor="message-type" className="text-xs">Tipo de Mensagem</Label>
        <Select
          value={node.data.config['message_type'] || 'text'}
          onValueChange={(value) => onUpdate('data.config.message_type', value)}
        >
          <SelectTrigger className="mt-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="text">Texto</SelectItem>
            <SelectItem value="image">Imagem</SelectItem>
            <SelectItem value="video">Vídeo</SelectItem>
            <SelectItem value="audio">Áudio</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

function ConditionNodeProperties({ node, onUpdate }: { node: FlowNode; onUpdate: (field: string, value: any) => void }) {
  return (
    <div className="space-y-3">
      <div>
        <Label htmlFor="condition-operator" className="text-xs">Operador</Label>
        <Select
          value={node.data.config['operator'] || 'AND'}
          onValueChange={(value) => onUpdate('data.config.operator', value)}
        >
          <SelectTrigger className="mt-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="AND">E (AND)</SelectItem>
            <SelectItem value="OR">OU (OR)</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

function DelayNodeProperties({ node, onUpdate }: { node: FlowNode; onUpdate: (field: string, value: any) => void }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <Label htmlFor="delay-duration" className="text-xs">Duração</Label>
          <Input
            id="delay-duration"
            type="number"
            value={node.data.config['duration'] || 1}
            onChange={(e) => onUpdate('data.config.duration', parseInt(e.target.value) || 1)}
            className="mt-1"
          />
        </div>
        <div>
          <Label htmlFor="delay-unit" className="text-xs">Unidade</Label>
          <Select
            value={node.data.config['unit'] || 'minutes'}
            onValueChange={(value) => onUpdate('data.config.unit', value)}
          >
            <SelectTrigger className="mt-1">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="seconds">Segundos</SelectItem>
              <SelectItem value="minutes">Minutos</SelectItem>
              <SelectItem value="hours">Horas</SelectItem>
              <SelectItem value="days">Dias</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  )
}

function ActionNodeProperties({ node, onUpdate }: { node: FlowNode; onUpdate: (field: string, value: any) => void }) {
  return (
    <div className="space-y-3">
      <div>
        <Label htmlFor="action-type" className="text-xs">Tipo de Ação</Label>
        <Select
          value={node.data.config['action_type'] || 'set_variable'}
          onValueChange={(value) => onUpdate('data.config.action_type', value)}
        >
          <SelectTrigger className="mt-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="set_variable">Definir Variável</SelectItem>
            <SelectItem value="send_notification">Enviar Notificação</SelectItem>
            <SelectItem value="create_task">Criar Tarefa</SelectItem>
            <SelectItem value="update_patient">Atualizar Paciente</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

function AIResponseNodeProperties({ node, onUpdate }: { node: FlowNode; onUpdate: (field: string, value: any) => void }) {
  return (
    <div className="space-y-3">
      <div>
        <Label htmlFor="ai-prompt" className="text-xs">Template do Prompt</Label>
        <Textarea
          id="ai-prompt"
          value={node.data.config['prompt_template'] || ''}
          onChange={(e) => onUpdate('data.config.prompt_template', e.target.value)}
          className="mt-1"
          rows={3}
          placeholder="Digite o template do prompt para a IA..."
        />
      </div>

      <div>
        <Label htmlFor="ai-fallback" className="text-xs">Mensagem de Fallback</Label>
        <Input
          id="ai-fallback"
          value={node.data.config['fallback_message'] || ''}
          onChange={(e) => onUpdate('data.config.fallback_message', e.target.value)}
          className="mt-1"
          placeholder="Mensagem caso a IA falhe"
        />
      </div>
    </div>
  )
}
