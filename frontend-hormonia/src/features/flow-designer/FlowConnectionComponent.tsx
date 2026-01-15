import React from 'react'
import { FlowConnection, FlowNode, FlowValidationError } from '@/types/flow-designer'

interface FlowConnectionComponentProps {
  connection: FlowConnection
  nodes: FlowNode[]
  selected: boolean
  errors: FlowValidationError[]
  onSelect: () => void
}

export function FlowConnectionComponent({
  connection,
  nodes,
  selected,
  errors,
  onSelect
}: FlowConnectionComponentProps) {
  // Find source and target nodes
  const sourceNode = nodes.find(node => node.id === connection.source)
  const targetNode = nodes.find(node => node.id === connection.target)

  if (!sourceNode || !targetNode) {
    return null
  }

  // Calculate connection points
  const sourcePoint = {
    x: sourceNode.position.x + 60, // Assuming node width of 120px
    y: sourceNode.position.y + 40  // Assuming node height of 80px
  }

  const targetPoint = {
    x: targetNode.position.x + 60,
    y: targetNode.position.y + 40
  }

  // Calculate control points for curved line
  const dx = targetPoint.x - sourcePoint.x
  const dy = targetPoint.y - sourcePoint.y
  const distance = Math.sqrt(dx * dx + dy * dy)
  
  // Control points for smooth curve
  const controlOffset = Math.min(distance * 0.3, 100)
  const control1 = {
    x: sourcePoint.x + controlOffset,
    y: sourcePoint.y
  }
  const control2 = {
    x: targetPoint.x - controlOffset,
    y: targetPoint.y
  }

  // Create SVG path
  const pathData = `M ${sourcePoint.x} ${sourcePoint.y} C ${control1.x} ${control1.y}, ${control2.x} ${control2.y}, ${targetPoint.x} ${targetPoint.y}`

  // Calculate midpoint for label
  const midPoint = {
    x: (sourcePoint.x + targetPoint.x) / 2,
    y: (sourcePoint.y + targetPoint.y) / 2
  }

  const hasErrors = errors.length > 0
  const strokeColor = hasErrors ? '#ef4444' : selected ? '#3b82f6' : '#6b7280'
  const strokeWidth = selected ? 3 : 2

  return (
    <g>
      {/* Main connection path */}
      <path
        d={pathData}
        fill="none"
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        strokeDasharray={connection.animated ? '5,5' : 'none'}
        role="button"
        tabIndex={0}
        aria-label="Selecionar conexao"
        className={`
          cursor-pointer transition-colors duration-200
          ${connection.animated ? 'animate-pulse' : ''}
          hover:stroke-blue-500
        `}
        onClick={(e) => {
          e.stopPropagation()
          onSelect()
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            e.stopPropagation()
            onSelect()
          }
        }}
      />

      {/* Arrow head */}
      <defs>
        <marker
          id={`arrowhead-${connection.id}`}
          markerWidth="10"
          markerHeight="7"
          refX="9"
          refY="3.5"
          orient="auto"
        >
          <polygon
            points="0 0, 10 3.5, 0 7"
            fill={strokeColor}
          />
        </marker>
      </defs>
      
      <path
        d={pathData}
        fill="none"
        stroke="transparent"
        strokeWidth="1"
        markerEnd={`url(#arrowhead-${connection.id})`}
      />

      {/* Connection label */}
      {connection.label && (
        <g>
          {/* Label background */}
          <rect
            x={midPoint.x - 30}
            y={midPoint.y - 10}
            width="60"
            height="20"
            fill="white"
            stroke={strokeColor}
            strokeWidth="1"
            rx="10"
            className="cursor-pointer"
            onClick={(e) => {
              e.stopPropagation()
              onSelect()
            }}
          />
          {/* Label text */}
          <text
            x={midPoint.x}
            y={midPoint.y + 4}
            textAnchor="middle"
            className="text-xs font-medium fill-current pointer-events-none"
            style={{ color: strokeColor }}
          >
            {connection.label}
          </text>
        </g>
      )}

      {/* Condition label */}
      {connection.condition && (
        <g>
          {/* Condition background */}
          <rect
            x={midPoint.x - 40}
            y={midPoint.y + 15}
            width="80"
            height="16"
            fill="yellow"
            stroke="#f59e0b"
            strokeWidth="1"
            rx="8"
            className="cursor-pointer opacity-90"
            onClick={(e) => {
              e.stopPropagation()
              onSelect()
            }}
          />
          {/* Condition text */}
          <text
            x={midPoint.x}
            y={midPoint.y + 26}
            textAnchor="middle"
            className="text-xs font-medium fill-current pointer-events-none"
            style={{ color: '#92400e' }}
          >
            {connection.condition}
          </text>
        </g>
      )}

      {/* Error indicator */}
      {hasErrors && (
        <g>
          {/* Error background */}
          <circle
            cx={midPoint.x}
            cy={midPoint.y - 20}
            r="8"
            fill="#fef2f2"
            stroke="#ef4444"
            strokeWidth="2"
            className="cursor-pointer"
            onClick={(e) => {
              e.stopPropagation()
              onSelect()
            }}
          />
          {/* Error icon */}
          <text
            x={midPoint.x}
            y={midPoint.y - 16}
            textAnchor="middle"
            className="text-xs font-bold fill-current pointer-events-none"
            style={{ color: '#ef4444' }}
          >
            !
          </text>
        </g>
      )}

      {/* Selection indicator */}
      {selected && (
        <path
          d={pathData}
          fill="none"
          stroke="#3b82f6"
          strokeWidth="6"
          opacity="0.3"
          className="pointer-events-none"
        />
      )}
    </g>
  )
}
