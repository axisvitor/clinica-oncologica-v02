import React, { useState, useCallback, useRef, useEffect } from 'react'
import { 
  Play, 
  Save, 
  Download, 
  Upload, 
  Undo, 
  Redo, 
  ZoomIn, 
  ZoomOut, 
  Move,
  MousePointer,
  Link,
  Settings,
  Eye,
  AlertTriangle,
  CheckCircle
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'
import { 
  FlowDesign, 
  FlowNode, 
  FlowConnection, 
  FlowDesignerState, 
  DesignerMode,
  FlowValidationResult
} from '../../lib/types/flow-designer'
import { FlowCanvas } from './FlowCanvas'
import { NodePalette } from './NodePalette'
import { PropertyPanel } from './PropertyPanel'
import { FlowValidator } from './FlowValidator'

interface FlowDesignerProps {
  initialDesign?: FlowDesign
  onSave?: (design: FlowDesign) => void
  onTest?: (design: FlowDesign) => void
  className?: string
}

export function FlowDesigner({ 
  initialDesign, 
  onSave, 
  onTest,
  className 
}: FlowDesignerProps) {
  const [designerState, setDesignerState] = useState<FlowDesignerState>(() => ({
    design: initialDesign || createEmptyDesign(),
    selectedNodes: [],
    selectedConnections: [],
    clipboard: [],
    history: [],
    historyIndex: -1,
    zoom: 1,
    pan: { x: 0, y: 0 },
    mode: DesignerMode.SELECT,
    isModified: false
  }))

  const [validation, setValidation] = useState<FlowValidationResult | null>(null)
  const [showPropertyPanel, setShowPropertyPanel] = useState(true)
  const [showNodePalette, setShowNodePalette] = useState(true)
  const canvasRef = useRef<HTMLDivElement>(null)
  const { toast } = useToast()

  // Validate flow whenever design changes
  useEffect(() => {
    const validator = new FlowValidator()
    const result = validator.validate(designerState.design)
    setValidation(result)
  }, [designerState.design])

  // Handle node selection
  const handleNodeSelect = useCallback((nodeId: string, multiSelect = false) => {
    setDesignerState(prev => ({
      ...prev,
      selectedNodes: multiSelect 
        ? prev.selectedNodes.includes(nodeId)
          ? prev.selectedNodes.filter(id => id !== nodeId)
          : [...prev.selectedNodes, nodeId]
        : [nodeId],
      selectedConnections: []
    }))
  }, [])

  // Handle connection selection
  const handleConnectionSelect = useCallback((connectionId: string) => {
    setDesignerState(prev => ({
      ...prev,
      selectedConnections: [connectionId],
      selectedNodes: []
    }))
  }, [])

  // Add node to canvas
  const handleAddNode = useCallback((nodeType: string, position: { x: number; y: number }) => {
    const newNode: FlowNode = {
      id: `node-${Date.now()}`,
      type: nodeType as any,
      position,
      data: {
        label: `${nodeType} Node`,
        config: getDefaultNodeConfig(nodeType)
      }
    }

    setDesignerState(prev => ({
      ...prev,
      design: {
        ...prev.design,
        nodes: [...prev.design.nodes, newNode]
      },
      isModified: true
    }))

    // Add to history
    addToHistory('Add Node', `Added ${nodeType} node`)
  }, [])

  // Update node
  const handleUpdateNode = useCallback((nodeId: string, updates: Partial<FlowNode>) => {
    setDesignerState(prev => ({
      ...prev,
      design: {
        ...prev.design,
        nodes: prev.design.nodes.map(node =>
          node.id === nodeId ? { ...node, ...updates } : node
        )
      },
      isModified: true
    }))
  }, [])

  // Delete selected items
  const handleDelete = useCallback(() => {
    setDesignerState(prev => {
      const newNodes = prev.design.nodes.filter(
        node => !prev.selectedNodes.includes(node.id)
      )
      const newConnections = prev.design.connections.filter(
        conn => !prev.selectedConnections.includes(conn.id) &&
                !prev.selectedNodes.includes(conn.source) &&
                !prev.selectedNodes.includes(conn.target)
      )

      return {
        ...prev,
        design: {
          ...prev.design,
          nodes: newNodes,
          connections: newConnections
        },
        selectedNodes: [],
        selectedConnections: [],
        isModified: true
      }
    })

    addToHistory('Delete', 'Deleted selected items')
  }, [])

  // Add connection
  const handleAddConnection = useCallback((source: string, target: string) => {
    const newConnection: FlowConnection = {
      id: `conn-${Date.now()}`,
      source,
      target
    }

    setDesignerState(prev => ({
      ...prev,
      design: {
        ...prev.design,
        connections: [...prev.design.connections, newConnection]
      },
      isModified: true
    }))

    addToHistory('Add Connection', `Connected ${source} to ${target}`)
  }, [])

  // Zoom controls
  const handleZoomIn = useCallback(() => {
    setDesignerState(prev => ({
      ...prev,
      zoom: Math.min(prev.zoom * 1.2, 3)
    }))
  }, [])

  const handleZoomOut = useCallback(() => {
    setDesignerState(prev => ({
      ...prev,
      zoom: Math.max(prev.zoom / 1.2, 0.1)
    }))
  }, [])

  const handleZoomReset = useCallback(() => {
    setDesignerState(prev => ({
      ...prev,
      zoom: 1,
      pan: { x: 0, y: 0 }
    }))
  }, [])

  // Mode switching
  const handleModeChange = useCallback((mode: DesignerMode) => {
    setDesignerState(prev => ({
      ...prev,
      mode
    }))
  }, [])

  // Save design
  const handleSave = useCallback(() => {
    if (validation && !validation.isValid) {
      toast({
        title: 'Erro de Validação',
        description: 'Corrija os erros antes de salvar',
        variant: 'destructive'
      })
      return
    }

    onSave?.(designerState.design)
    setDesignerState(prev => ({ ...prev, isModified: false }))
    
    toast({
      title: 'Salvo',
      description: 'Flow salvo com sucesso'
    })
  }, [designerState.design, validation, onSave, toast])

  // Test flow
  const handleTest = useCallback(() => {
    if (validation && !validation.isValid) {
      toast({
        title: 'Erro de Validação',
        description: 'Corrija os erros antes de testar',
        variant: 'destructive'
      })
      return
    }

    onTest?.(designerState.design)
  }, [designerState.design, validation, onTest, toast])

  // History management
  const addToHistory = useCallback((action: string, description: string) => {
    setDesignerState(prev => ({
      ...prev,
      history: [
        ...prev.history.slice(0, prev.historyIndex + 1),
        {
          action,
          timestamp: Date.now(),
          data: prev.design,
          description
        }
      ],
      historyIndex: prev.historyIndex + 1
    }))
  }, [])

  const handleUndo = useCallback(() => {
    if (designerState.historyIndex > 0) {
      const previousState = designerState.history[designerState.historyIndex - 1]
      if (!previousState) return
      setDesignerState(prev => ({
        ...prev,
        design: previousState.data as FlowDesign,
        historyIndex: prev.historyIndex - 1,
        isModified: true
      }))
    }
  }, [designerState.historyIndex, designerState.history])

  const handleRedo = useCallback(() => {
    if (designerState.historyIndex < designerState.history.length - 1) {
      const nextState = designerState.history[designerState.historyIndex + 1]
      if (!nextState) return
      setDesignerState(prev => ({
        ...prev,
        design: nextState.data as FlowDesign,
        historyIndex: prev.historyIndex + 1,
        isModified: true
      }))
    }
  }, [designerState.historyIndex, designerState.history])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case 's':
            e.preventDefault()
            handleSave()
            break
          case 'z':
            e.preventDefault()
            if (e.shiftKey) {
              handleRedo()
            } else {
              handleUndo()
            }
            break
          case 'Delete':
          case 'Backspace':
            e.preventDefault()
            handleDelete()
            break
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave, handleUndo, handleRedo, handleDelete])

  const getValidationStatus = () => {
    if (!validation) return null
    
    if (validation.isValid) {
      return (
        <Badge variant="default" className="bg-green-500">
          <CheckCircle className="h-3 w-3 mr-1" />
          Válido
        </Badge>
      )
    } else {
      return (
        <Badge variant="destructive">
          <AlertTriangle className="h-3 w-3 mr-1" />
          {validation.errors.length} erro(s)
        </Badge>
      )
    }
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Toolbar */}
      <Card className="rounded-none border-x-0 border-t-0">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <CardTitle className="text-lg">Flow Designer</CardTitle>
              {designerState.isModified && (
                <Badge variant="outline">Modificado</Badge>
              )}
              {getValidationStatus()}
            </div>
            
            <div className="flex items-center gap-2">
              {/* Mode Controls */}
              <div className="flex items-center gap-1 border rounded-md p-1">
                <Button
                  variant={designerState.mode === DesignerMode.SELECT ? "default" : "ghost"}
                  size="sm"
                  onClick={() => handleModeChange(DesignerMode.SELECT)}
                >
                  <MousePointer className="h-4 w-4" />
                </Button>
                <Button
                  variant={designerState.mode === DesignerMode.CONNECT ? "default" : "ghost"}
                  size="sm"
                  onClick={() => handleModeChange(DesignerMode.CONNECT)}
                >
                  <Link className="h-4 w-4" />
                </Button>
                <Button
                  variant={designerState.mode === DesignerMode.PAN ? "default" : "ghost"}
                  size="sm"
                  onClick={() => handleModeChange(DesignerMode.PAN)}
                >
                  <Move className="h-4 w-4" />
                </Button>
              </div>

              <Separator orientation="vertical" className="h-6" />

              {/* History Controls */}
              <Button
                variant="ghost"
                size="sm"
                onClick={handleUndo}
                disabled={designerState.historyIndex <= 0}
              >
                <Undo className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRedo}
                disabled={designerState.historyIndex >= designerState.history.length - 1}
              >
                <Redo className="h-4 w-4" />
              </Button>

              <Separator orientation="vertical" className="h-6" />

              {/* Zoom Controls */}
              <Button variant="ghost" size="sm" onClick={handleZoomOut}>
                <ZoomOut className="h-4 w-4" />
              </Button>
              <span className="text-sm min-w-[3rem] text-center">
                {Math.round(designerState.zoom * 100)}%
              </span>
              <Button variant="ghost" size="sm" onClick={handleZoomIn}>
                <ZoomIn className="h-4 w-4" />
              </Button>

              <Separator orientation="vertical" className="h-6" />

              {/* Action Buttons */}
              <Button variant="ghost" size="sm" onClick={handleTest}>
                <Play className="h-4 w-4 mr-2" />
                Testar
              </Button>
              <Button variant="default" size="sm" onClick={handleSave}>
                <Save className="h-4 w-4 mr-2" />
                Salvar
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Node Palette */}
        {showNodePalette && (
          <div className="w-64 border-r bg-background">
            <NodePalette onAddNode={handleAddNode} />
          </div>
        )}

        {/* Canvas */}
        <div className="flex-1 relative" ref={canvasRef}>
          <FlowCanvas
            design={designerState.design}
            selectedNodes={designerState.selectedNodes}
            selectedConnections={designerState.selectedConnections}
            zoom={designerState.zoom}
            pan={designerState.pan}
            mode={designerState.mode}
            onNodeSelect={handleNodeSelect}
            onConnectionSelect={handleConnectionSelect}
            onNodeUpdate={handleUpdateNode}
            onAddConnection={handleAddConnection}
            onPanChange={(pan) => setDesignerState(prev => ({ ...prev, pan }))}
            validation={validation}
          />
        </div>

        {/* Property Panel */}
        {showPropertyPanel && (
          <div className="w-80 border-l bg-background">
            <PropertyPanel
              design={designerState.design}
              selectedNodes={designerState.selectedNodes}
              selectedConnections={designerState.selectedConnections}
              onUpdateNode={handleUpdateNode}
              validation={validation}
            />
          </div>
        )}
      </div>
    </div>
  )
}

// Helper functions
function createEmptyDesign(): FlowDesign {
  return {
    id: `design-${Date.now()}`,
    name: 'Novo Flow',
    description: '',
    version: '1.0.0',
    nodes: [],
    connections: [],
    variables: [],
    metadata: {
      author: 'current-user',
      tags: [],
      category: 'general',
      complexity_level: 'simple'
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
}

function getDefaultNodeConfig(nodeType: string): Record<string, any> {
  switch (nodeType) {
    case 'message':
      return {
        content: 'Nova mensagem',
        message_type: 'text'
      }
    case 'condition':
      return {
        conditions: [],
        operator: 'AND'
      }
    case 'delay':
      return {
        duration: 1,
        unit: 'minutes'
      }
    case 'action':
      return {
        action_type: 'set_variable',
        parameters: {}
      }
    default:
      return {}
  }
}
