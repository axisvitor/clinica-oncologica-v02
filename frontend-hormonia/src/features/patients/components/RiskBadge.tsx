import React from 'react'
import { Badge } from '@/components/ui/badge'

interface RiskBadgeProps {
    level: string
    className?: string
}

export function RiskBadge({ level, className }: RiskBadgeProps) {
    const variants: Record<string, 'destructive' | 'default'> = {
        critical: 'destructive',
        high: 'destructive',
        medium: 'default',
        low: 'default'
    }

    const colors: Record<string, string> = {
        critical: 'bg-red-500 text-white border-red-600 hover:bg-red-600',
        high: 'bg-orange-500 text-white border-orange-600 hover:bg-orange-600',
        medium: 'bg-yellow-500 text-gray-900 border-yellow-600 hover:bg-yellow-600',
        low: 'bg-green-500 text-white border-green-600 hover:bg-green-600'
    }

    const normalizedLevel = level.toLowerCase()

    return (
        <Badge
            variant={variants[normalizedLevel] || 'default'}
            className={`${colors[normalizedLevel] || ''} ${className || ''}`}
        >
            {level.toUpperCase()}
        </Badge>
    )
}
