import React from 'react'
import type { LucideIcon } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface MetricCardProps {
  title: string
  value: string | number
  change?: number
  icon: LucideIcon
  trend?: 'up' | 'down'
  variant?: 'default' | 'warning' | 'success'
  description?: string
  format?: string
}

export function MetricCard({
  title,
  value,
  change,
  icon: Icon,
  trend = 'up',
  variant = 'default',
  description,
  format
}: MetricCardProps) {
  const formatChange = (change: number) => {
    const sign = change >= 0 ? '+' : ''
    return `${sign}${change}`
  }

  const getChangeColor = (change: number, trend: 'up' | 'down') => {
    if (change === 0) return 'text-gray-500'
    
    const isPositive = change > 0
    const isGoodChange = (trend === 'up' && isPositive) || (trend === 'down' && !isPositive)
    
    return isGoodChange ? 'text-green-600' : 'text-red-600'
  }

  const getVariantStyles = (variant: string) => {
    switch (variant) {
      case 'warning':
        return 'border-orange-200 bg-orange-50'
      case 'success':
        return 'border-green-200 bg-green-50'
      default:
        return ''
    }
  }

  return (
    <Card className={cn('transition-all hover:shadow-md', getVariantStyles(variant))}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-gray-600">
          {title}
        </CardTitle>
        <Icon className={cn(
          'h-4 w-4',
          variant === 'warning' ? 'text-orange-600' : 
          variant === 'success' ? 'text-green-600' : 
          'text-gray-400'
        )} />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-gray-900 font-mono tabular-nums">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
        {change !== undefined && (
          <div className="flex items-center mt-2">
            <Badge
              variant="outline"
              className={cn(
                'text-xs font-mono tabular-nums',
                getChangeColor(change, trend)
              )}
            >
              {formatChange(change)}
            </Badge>
            <span className="text-xs text-gray-500 ml-2">
              vs. período anterior
            </span>
          </div>
        )}
        {description && (
          <div className="text-xs text-gray-500 mt-1">
            {description}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
