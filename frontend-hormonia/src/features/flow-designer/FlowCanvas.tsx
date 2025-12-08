import React, { useRef, useCallback, useState, useEffect } from 'react'
import {
  FlowDesign,
  FlowNode,
  FlowConnection,
  DesignerMode,
  FlowValidationResult
} from '@/types/flow-designer'
import { FlowNodeComponent } from './FlowNodeComponent'
import { FlowConnectionComponent } from './FlowConnectionComponent'

interface FlowCanvasProps {
  design: FlowDesign
  selectedNodes: string[]
  selectedConnections: string[]
  zoom: number
  pan: { x: number; y: number }
  mode: DesignerMode
  onNodeSelect: (nodeId: string, multiSelect?: boolean) => void
  onConnectionSelect: (connectionId: string) => void
  onNodeUpdate: (nodeId: string, updates: Partial<FlowNode>) => void
  onAddConnection: (source: string, target: string) => void
  onPanChange: (pan: { x: number; y: number }) => void
  validation?: FlowValidationResult | null
}

export function FlowCanvas({
  design,
  selectedNodes,
  selectedConnections,
  zoom,
  pan,
  mode,
  onNodeSelect,
  onConnectionSelect,
  onNodeUpdate,
  onAddConnection,
  onPanChange,
  validation
}: FlowCanvasProps) {
  const canvasRef = useRef<HTMLDivElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [connecting, setConnecting] = useState<{ from: string; to?: string } | null>(null)

  // Handle canvas mouse events
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (mode === DesignerMode.PAN) {
      setIsDragging(true)
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
    }
  }, [mode, pan])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDragging && mode === DesignerMode.PAN) {
      onPanChange({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      })
    }
  }, [isDragging, mode, dragStart, onPanChange])

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  // Handle node drag
  const handleNodeDrag = useCallback((nodeId: string, position: { x: number; y: number }) => {
    onNodeUpdate(nodeId, { position })
  }, [onNodeUpdate])

  // Handle connection creation
  const handleConnectionStart = useCallback((nodeId: string) => {
    if (mode === DesignerMode.CONNECT) {
      setConnecting({ from: nodeId })
    }
  }, [mode])

  const handleConnectionEnd = useCallback((nodeId: string) => {
    if (connecting && connecting.from !== nodeId) {
      onAddConnection(connecting.from, nodeId)
      setConnecting(null)
    }
  }, [connecting, onAddConnection])

  // Handle canvas click (deselect)
  const handleCanvasClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onNodeSelect('', false) // Deselect all
    }
  }, [onNodeSelect])

  // Get node validation errors
  const getNodeErrors = useCallback((nodeId: string) => {
    if (!validation) return []
    return validation.errors.filter(error => error.node_id === nodeId)
  }, [validation])

  // Get connection validation errors
  const getConnectionErrors = useCallback((connectionId: string) => {
    if (!validation) return []
    return validation.errors.filter(error => error.connection_id === connectionId)
  }, [validation])

  return (
    <div
      ref={canvasRef}
      className="relative w-full h-full bg-gray-50 overflow-hidden cursor-crosshair"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onClick={handleCanvasClick}
      style={{
        backgroundImage: `
          radial-gradient(circle, #e5e7eb 1px, transparent 1px)
        `,
        backgroundSize: `${20 * zoom}px ${20 * zoom}px`,
        backgroundPosition: `${pan.x}px ${pan.y}px`
      }}
    >
      {/* Canvas Transform Container */}
      <div
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: '0 0',
          width: '100%',
          height: '100%',
          position: 'relative'
        }}
      >
        {/* Render Connections */}
        <svg
          className="absolute inset-0 pointer-events-none"
          style={{ width: '100%', height: '100%', overflow: 'visible' }}
        >
          {design.connections.map(connection => (
            <FlowConnectionComponent
              key={connection.id}
              connection={connection}
              nodes={design.nodes}
              selected={selectedConnections.includes(connection.id)}
              errors={getConnectionErrors(connection.id)}
              onSelect={() => onConnectionSelect(connection.id)}
            />
          ))}
          
          {/* Temporary connection while connecting */}
          {connecting && (
            <line
              x1={getNodePosition(connecting.from)?.x || 0}
              y1={getNodePosition(connecting.from)?.y || 0}
              x2={getNodePosition(connecting.from)?.x || 0}
              y2={getNodePosition(connecting.from)?.y || 0}
              stroke="#3b82f6"
              strokeWidth="2"
              strokeDasharray="5,5"
              className="pointer-events-none"
            />
          )}
        </svg>

        {/* Render Nodes */}
        {design.nodes.map(node => (
          <FlowNodeComponent
            key={node.id}
            node={node}
            selected={selectedNodes.includes(node.id)}
            errors={getNodeErrors(node.id)}
            mode={mode}
            onSelect={(multiSelect) => onNodeSelect(node.id, multiSelect)}
            onDrag={(position) => handleNodeDrag(node.id, position)}
            onConnectionStart={() => handleConnectionStart(node.id)}
            onConnectionEnd={() => handleConnectionEnd(node.id)}
          />
        ))}
      </div>

      {/* Mode Indicator */}
      <div className="absolute top-4 left-4 bg-white rounded-lg shadow-sm border px-3 py-2">
        <div className="flex items-center gap-2 text-sm">
          <div className={`w-2 h-2 rounded-full ${getModeColor(mode)}`} />
          <span>{getModeLabel(mode)}</span>
        </div>
      </div>

      {/* Zoom Indicator */}
      <div className="absolute bottom-4 right-4 bg-white rounded-lg shadow-sm border px-3 py-2">
        <span className="text-sm font-medium">{Math.round(zoom * 100)}%</span>
      </div>

      {/* Validation Summary */}
      {validation && !validation.isValid && (
        <div className="absolute top-4 right-4 bg-red-50 border border-red-200 rounded-lg p-3 max-w-sm">
          <div className="text-sm font-medium text-red-800 mb-1">
            Erros de Validação ({validation.errors.length})
          </div>
          <div className="text-xs text-red-600 space-y-1">
            {validation.errors.slice(0, 3).map(error => (
              <div key={error.id}>{error.message}</div>
            ))}
            {validation.errors.length > 3 && (
              <div>... e mais {validation.errors.length - 3} erro(s)</div>
            )}
          </div>
        </div>
      )}
    </div>
  )

  // Helper function to get node position
  function getNodePosition(nodeId: string) {
    const node = design.nodes.find(n => n.id === nodeId)
    return node?.position
  }
}

// Helper functions
function getModeColor(mode: DesignerMode): string {
  switch (mode) {
    case DesignerMode.SELECT:
      return 'bg-blue-500'
    case DesignerMode.CONNECT:
      return 'bg-green-500'
    case DesignerMode.PAN:
      return 'bg-purple-500'
    default:
      return 'bg-gray-500'
  }
}

function getModeLabel(mode: DesignerMode): string {
  switch (mode) {
    case DesignerMode.SELECT:
      return 'Selecionar'
    case DesignerMode.CONNECT:
      return 'Conectar'
    case DesignerMode.PAN:
      return 'Navegar'
    default:
      return 'Desconhecido'
  }
}
