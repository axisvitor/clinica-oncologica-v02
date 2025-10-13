import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../ui/card'
import { Progress } from '../../ui/progress'
import { Badge } from '../../ui/badge'
import {
  Database,
  Cpu,
  HardDrive,
  Wifi,
  Activity,
  Clock
} from 'lucide-react'
import { AdminDashboardStats } from '../../../types/admin'

interface SystemHealthCardsProps {
  stats: AdminDashboardStats
  className?: string
}

export const SystemHealthCards: React.FC<SystemHealthCardsProps> = ({ 
  stats, 
  className = '' 
}) => {
  const formatUptime = (seconds: number): string => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    
    if (days > 0) {
      return `${days}d ${hours}h ${minutes}m`
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`
    } else {
      return `${minutes}m`
    }
  }

  const getHealthStatus = (usage: number) => {
    if (usage < 50) return { status: 'healthy', color: 'bg-green-500' }
    if (usage < 80) return { status: 'warning', color: 'bg-yellow-500' }
    return { status: 'critical', color: 'bg-red-500' }
  }

  const systemHealthCards = [
    {
      title: 'System Uptime',
      value: formatUptime(stats.systemUptime),
      icon: Clock,
      description: 'System has been running',
      status: 'healthy'
    },
    {
      title: 'Memory Usage',
      value: `${stats.memoryUsage.toFixed(1)}%`,
      icon: Database,
      description: 'RAM utilization',
      progress: stats.memoryUsage,
      status: getHealthStatus(stats.memoryUsage).status
    },
    {
      title: 'CPU Usage',
      value: `${stats.cpuUsage.toFixed(1)}%`,
      icon: Cpu,
      description: 'Processor utilization',
      progress: stats.cpuUsage,
      status: getHealthStatus(stats.cpuUsage).status
    },
    {
      title: 'Disk Usage',
      value: `${stats.diskUsage.toFixed(1)}%`,
      icon: HardDrive,
      description: 'Storage utilization',
      progress: stats.diskUsage,
      status: getHealthStatus(stats.diskUsage).status
    }
  ]

  return (
    <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 ${className}`}>
      {systemHealthCards.map((card, index) => {
        const IconComponent = card.icon
        const statusColor = card.status === 'healthy' ? 'text-green-600' : 
                           card.status === 'warning' ? 'text-yellow-600' : 'text-red-600'
        
        return (
          <Card key={index} className="relative overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {card.title}
              </CardTitle>
              <IconComponent className={`h-4 w-4 ${statusColor}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold mb-1">
                {card.value}
              </div>
              <p className="text-xs text-muted-foreground mb-2">
                {card.description}
              </p>
              
              {card.progress !== undefined && (
                <div className="space-y-2">
                  <Progress 
                    value={card.progress} 
                    className="h-2"
                  />
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>0%</span>
                    <span>100%</span>
                  </div>
                </div>
              )}
              
              <Badge 
                variant={card.status === 'healthy' ? 'default' : 
                        card.status === 'warning' ? 'secondary' : 'destructive'}
                className="mt-2"
              >
                {card.status === 'healthy' ? 'Healthy' : 
                 card.status === 'warning' ? 'Warning' : 'Critical'}
              </Badge>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

export default SystemHealthCards