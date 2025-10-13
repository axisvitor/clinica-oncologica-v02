import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../ui/tabs'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Area,
  AreaChart,
  PieChart,
  Pie,
  Cell
} from 'recharts'
import { Shield, TrendingUp, AlertTriangle } from 'lucide-react'
import { AdminDashboardStats } from '../../../types/admin'

interface SecurityTrendChartProps {
  stats: AdminDashboardStats
  className?: string
}

// Mock data for charts - in real app this would come from props or API
const mockSecurityTrends = [
  { date: '2024-01-01', logins: 45, failedLogins: 2, blockedIPs: 0 },
  { date: '2024-01-02', logins: 52, failedLogins: 1, blockedIPs: 1 },
  { date: '2024-01-03', logins: 38, failedLogins: 4, blockedIPs: 0 },
  { date: '2024-01-04', logins: 61, failedLogins: 3, blockedIPs: 2 },
  { date: '2024-01-05', logins: 49, failedLogins: 1, blockedIPs: 0 },
  { date: '2024-01-06', logins: 55, failedLogins: 2, blockedIPs: 1 },
  { date: '2024-01-07', logins: 43, failedLogins: 5, blockedIPs: 3 }
]

const mockUserActivity = [
  { hour: '00:00', active: 5 },
  { hour: '04:00', active: 2 },
  { hour: '08:00', active: 25 },
  { hour: '12:00', active: 45 },
  { hour: '16:00', active: 38 },
  { hour: '20:00', active: 15 }
]

const mockSecurityEvents = [
  { name: 'Successful Logins', value: 85, color: '#10b981' },
  { name: 'Failed Logins', value: 12, color: '#ef4444' },
  { name: 'Blocked Access', value: 3, color: '#f59e0b' }
]

export const SecurityTrendChart: React.FC<SecurityTrendChartProps> = ({ 
  stats, 
  className = '' 
}) => {
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('pt-BR', { 
      month: 'short', 
      day: 'numeric' 
    })
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-background border rounded-lg shadow-lg p-3">
          <p className="font-medium">{formatDate(label)}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} style={{ color: entry.color }}>
              {entry.dataKey}: {entry.value}
            </p>
          ))}
        </div>
      )
    }
    return null
  }

  const RADIAN = Math.PI / 180
  const renderCustomizedLabel = ({
    cx, cy, midAngle, innerRadius, outerRadius, percent
  }: any) => {
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5
    const x = cx + radius * Math.cos(-midAngle * RADIAN)
    const y = cy + radius * Math.sin(-midAngle * RADIAN)

    return (
      <text 
        x={x} 
        y={y} 
        fill="white" 
        textAnchor={x > cx ? 'start' : 'end'} 
        dominantBaseline="central"
        fontSize={12}
        fontWeight="bold"
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    )
  }

  return (
    <div className={className}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Security Trends
          </CardTitle>
          <CardDescription>
            Security metrics and activity patterns over time
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="trends" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="trends">Login Trends</TabsTrigger>
              <TabsTrigger value="activity">User Activity</TabsTrigger>
              <TabsTrigger value="events">Security Events</TabsTrigger>
            </TabsList>
            
            <TabsContent value="trends" className="space-y-4">
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={mockSecurityTrends}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="date" 
                      tickFormatter={formatDate}
                      fontSize={12}
                    />
                    <YAxis fontSize={12} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="logins"
                      stackId="1"
                      stroke="#10b981"
                      fill="#10b981"
                      fillOpacity={0.6}
                      name="Successful Logins"
                    />
                    <Area
                      type="monotone"
                      dataKey="failedLogins"
                      stackId="2"
                      stroke="#ef4444"
                      fill="#ef4444"
                      fillOpacity={0.6}
                      name="Failed Logins"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-green-600">
                    {mockSecurityTrends.reduce((sum, day) => sum + day.logins, 0)}
                  </div>
                  <div className="text-xs text-muted-foreground">Total Logins (7d)</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-600">
                    {mockSecurityTrends.reduce((sum, day) => sum + day.failedLogins, 0)}
                  </div>
                  <div className="text-xs text-muted-foreground">Failed Logins (7d)</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-yellow-600">
                    {mockSecurityTrends.reduce((sum, day) => sum + day.blockedIPs, 0)}
                  </div>
                  <div className="text-xs text-muted-foreground">Blocked IPs (7d)</div>
                </div>
              </div>
            </TabsContent>
            
            <TabsContent value="activity" className="space-y-4">
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={mockUserActivity}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="hour" fontSize={12} />
                    <YAxis fontSize={12} />
                    <Tooltip 
                      labelFormatter={(value) => `Time: ${value}`}
                      formatter={(value) => [`${value} users`, 'Active Users']}
                    />
                    <Line
                      type="monotone"
                      dataKey="active"
                      stroke="#3b82f6"
                      strokeWidth={3}
                      dot={{ fill: '#3b82f6', strokeWidth: 2, r: 4 }}
                      activeDot={{ r: 6, stroke: '#3b82f6', strokeWidth: 2 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {Math.max(...mockUserActivity.map(d => d.active))}
                </div>
                <div className="text-xs text-muted-foreground">Peak Active Users</div>
              </div>
            </TabsContent>
            
            <TabsContent value="events" className="space-y-4">
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={mockSecurityEvents}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={renderCustomizedLabel}
                      outerRadius={100}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {mockSecurityEvents.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip 
                      formatter={(value, name) => [`${value}`, name]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              
              <div className="grid grid-cols-3 gap-4">
                {mockSecurityEvents.map((event, index) => (
                  <div key={index} className="text-center">
                    <div 
                      className="w-4 h-4 rounded-full mx-auto mb-2"
                      style={{ backgroundColor: event.color }}
                    />
                    <div className="text-sm font-medium">{event.value}</div>
                    <div className="text-xs text-muted-foreground">{event.name}</div>
                  </div>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}

export default SecurityTrendChart