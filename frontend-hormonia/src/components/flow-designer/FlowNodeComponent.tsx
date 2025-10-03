import React, { useState, useCallback } from 'react'
import { 
  MessageSquare, 
  GitBranch, 
  Clock, 
  Zap, 
  Play, 
  Square,
  Bot,
  HelpCircle,
  Webhook,
  AlertTriangle
} from 'lucide-react'
import { FlowNode, FlowNodeType, DesignerMode, FlowValidationError } from '../../lib/types/flow-designer'

interface FlowNodeComponentProps {
  node: FlowNode
  selected: boolean
  errors: FlowValidationError[]
  mode: DesignerMode
  onSelect: (multiSelect?: boolean) => void
  onDrag: (position: { x: number; y: number }) => void
  onConnectionStart: () => void
  onConnectionEnd: () => void
}

export function FlowNodeComponent({
  node,
  selected,
  errors,
  mode,
  onSelect,
  onDrag,
  onConnectionStart,
  onConnectionEnd
}: FlowNodeComponentProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    
    if (mode === DesignerMode.SELECT) {
      setIsDragging(true)
      setDragStart({
        x: e.clientX - node.position.x,
        y: e.clientY - node.position.y
      })
      onSelect(e.ctrlKey || e.metaKey)
    } else if (mode === DesignerMode.CONNECT) {
      onConnectionStart()
    }
  }, [mode, node.position, onSelect, onConnectionStart])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDragging && mode === DesignerMode.SELECT) {
      onDrag({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      })
    }
  }, [isDragging, mode, dragStart, onDrag])

  const handleMouseUp = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setIsDragging(false)
    
    if (mode === DesignerMode.CONNECT) {
      onConnectionEnd()
    }
  }, [mode, onConnectionEnd])

  const getNodeIcon = (type: FlowNodeType) => {
    switch (type) {
      case FlowNodeType.START:
        return <Play className="h-4 w-4" />
      case FlowNodeType.MESSAGE:
        return <MessageSquare className="h-4 w-4" />
      case FlowNodeType.CONDITION:
        return <GitBranch className="h-4 w-4" />
      case FlowNodeType.DELAY:
        return <Clock className="h-4 w-4" />
      case FlowNodeType.ACTION:
        return <Zap className="h-4 w-4" />
      case FlowNodeType.END:
        return <Square className="h-4 w-4" />
      case FlowNodeType.AI_RESPONSE:
        return <Bot className="h-4 w-4" />
      case FlowNodeType.QUIZ:
        return <HelpCircle className="h-4 w-4" />
      case FlowNodeType.WEBHOOK:
        return <Webhook className="h-4 w-4" />
      default:
        return <Square className="h-4 w-4" />
    }
  }

  const getNodeColor = (type: FlowNodeType) => {
    switch (type) {
      case FlowNodeType.START:
        return 'bg-green-100 border-green-300 text-green-800'
      case FlowNodeType.MESSAGE:
        return 'bg-blue-100 border-blue-300 text-blue-800'
      case FlowNodeType.CONDITION:
        return 'bg-yellow-100 border-yellow-300 text-yellow-800'
      case FlowNodeType.DELAY:
        return 'bg-purple-100 border-purple-300 text-purple-800'
      case FlowNodeType.ACTION:
        return 'bg-orange-100 border-orange-300 text-orange-800'
      case FlowNodeType.END:
        return 'bg-red-100 border-red-300 text-red-800'
      case FlowNodeType.AI_RESPONSE:
        return 'bg-indigo-100 border-indigo-300 text-indigo-800'
      case FlowNodeType.QUIZ:
        return 'bg-pink-100 border-pink-300 text-pink-800'
      case FlowNodeType.WEBHOOK:
        return 'bg-gray-100 border-gray-300 text-gray-800'
      default:
        return 'bg-gray-100 border-gray-300 text-gray-800'
    }
  }

  const hasErrors = errors.length > 0
  const nodeColorClass = hasErrors 
    ? 'bg-red-100 border-red-500 text-red-800' 
    : getNodeColor(node.type)

  return (
    <div
      className={`
        absolute cursor-pointer select-none transition-all duration-200
        ${isDragging ? 'z-50' : 'z-10'}
        ${mode === DesignerMode.CONNECT ? 'cursor-crosshair' : 'cursor-move'}
      `}
      style={{
        left: node.position.x,
        top: node.position.y,
        transform: isDragging ? 'scale(1.05)' : 'scale(1)'
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      {/* Node Body */}
      <div
        className={`
          relative min-w-[120px] max-w-[200px] p-3 rounded-lg border-2 shadow-sm
          ${nodeColorClass}
          ${selected ? 'ring-2 ring-blue-500 ring-offset-2' : ''}
          ${isDragging ? 'shadow-lg' : ''}
          hover:shadow-md transition-shadow
        `}
      >
        {/* Node Header */}
        <div className="flex items-center gap-2 mb-1">
          {getNodeIcon(node.type)}
          <span className="font-medium text-sm truncate">
            {node.data.label}
          </span>
          {hasErrors && (
            <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0" />
          )}
        </div>

        {/* Node Description */}
        {node.data.description && (
          <div className="text-xs opacity-75 truncate">
            {node.data.description}
          </div>
        )}

        {/* Connection Points */}
        <div className="absolute -top-2 left-1/2 transform -translate-x-1/2">
          <div className="w-3 h-3 bg-white border-2 border-gray-400 rounded-full hover:border-blue-500 transition-colors" />
        </div>
        <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2">
          <div className="w-3 h-3 bg-white border-2 border-gray-400 rounded-full hover:border-blue-500 transition-colors" />
        </div>
        <div className="absolute -left-2 top-1/2 transform -translate-y-1/2">
          <div className="w-3 h-3 bg-white border-2 border-gray-400 rounded-full hover:border-blue-500 transition-colors" />
        </div>
        <div className="absolute -right-2 top-1/2 transform -translate-y-1/2">
          <div className="w-3 h-3 bg-white border-2 border-gray-400 rounded-full hover:border-blue-500 transition-colors" />
        </div>

        {/* Node Type Badge */}
        <div className="absolute -top-1 -right-1">
          <div className="bg-white border border-gray-300 rounded-full p-1 text-xs">
            {node.type.charAt(0).toUpperCase()}
          </div>
        </div>
      </div>

      {/* Error Tooltip */}
      {hasErrors && (
        <div className="absolute top-full left-0 mt-2 p-2 bg-red-50 border border-red-200 rounded-md shadow-lg z-50 min-w-[200px]">
          <div className="text-xs font-medium text-red-800 mb-1">Erros:</div>
          {errors.map(error => (
            <div key={error.id} className="text-xs text-red-600">
              • {error.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
