/**
 * WhatsApp Integration Dashboard
 * Main component that combines instance management, messaging, and statistics
 */
import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import {
  MessageSquare,
  Users,
  Activity,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Clock,
  Phone,
  BarChart3
} from 'lucide-react';
import { WhatsAppInstanceManager } from './WhatsAppInstanceManager';
import { WhatsAppMessageSender } from './WhatsAppMessageSender';
import { whatsAppService } from '../../services/whatsapp/WhatsAppService';
import { useConfig } from '@/lib/config-initializer';
import { createLogger } from '@/lib/logger';

export interface WhatsAppInstance {
  name: string;
  isConnected: boolean;
  phoneNumber?: string;
  profileName?: string;
  status: string;
  createdAt: string;
}

export interface QueueStats {
  pending: number;
  scheduled: number;
  retryScheduled: number;
  deadLetter: number;
}

interface StatCard {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  description?: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
}

const logger = createLogger('WhatsAppDashboard');

export const WhatsAppDashboard: React.FC = () => {
  const { config } = useConfig()
  const [selectedInstance, setSelectedInstance] = useState<WhatsAppInstance | null>(null);
  const [queueStats, setQueueStats] = useState<QueueStats | null>(null);
  const [messageStats, setMessageStats] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEvolutionEnabled, setIsEvolutionEnabled] = useState(false);

  useEffect(() => {
    // Check if Evolution API is enabled
    setIsEvolutionEnabled(config?.VITE_ENABLE_EVOLUTION === 'true');

    if (config?.VITE_ENABLE_EVOLUTION === 'true') {
      loadDashboardData();

      // Refresh data every 30 seconds
      const interval = setInterval(loadDashboardData, 30000);
      return () => clearInterval(interval);
    }

    // Return undefined if Evolution API is disabled
    return undefined;
  }, [config]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load queue statistics
      const queueResponse = await whatsAppService.getQueueStats();
      setQueueStats(queueResponse.queueStatistics);

      // Load message statistics for selected instance
      if (selectedInstance) {
        const statsResponse = await whatsAppService.getMessageStatistics(selectedInstance.name);
        setMessageStats(statsResponse.statistics);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const handleInstanceSelected = (instance: WhatsAppInstance) => {
    setSelectedInstance(instance);
    // Load statistics for the selected instance
    if (instance.isConnected) {
      loadMessageStatistics(instance.name);
    }
  };

  const loadMessageStatistics = async (instanceName: string) => {
    try {
      const response = await whatsAppService.getMessageStatistics(instanceName);
      setMessageStats(response.statistics);
    } catch (err) {
      logger.error('Failed to load message statistics:', err);
    }
  };

  const getStatCards = (): StatCard[] => {
    const cards: StatCard[] = [];

    if (selectedInstance) {
      cards.push({
        title: 'Instance Status',
        value: selectedInstance.isConnected ? 'Connected' : 'Disconnected',
        icon: selectedInstance.isConnected ?
          <CheckCircle className="w-5 h-5 text-green-500" /> :
          <AlertCircle className="w-5 h-5 text-red-500" />,
        description: selectedInstance.phoneNumber || 'No phone number'
      });
    }

    if (queueStats) {
      cards.push(
        {
          title: 'Pending Messages',
          value: queueStats.pending,
          icon: <Clock className="w-5 h-5 text-orange-500" />,
          description: 'Messages in queue'
        },
        {
          title: 'Scheduled Messages',
          value: queueStats.scheduled,
          icon: <TrendingUp className="w-5 h-5 text-blue-500" />,
          description: 'Future deliveries'
        },
        {
          title: 'Failed Messages',
          value: queueStats.deadLetter,
          icon: <AlertCircle className="w-5 h-5 text-red-500" />,
          description: 'Requires attention'
        }
      );
    }

    if (messageStats) {
      cards.push(
        {
          title: 'Total Messages',
          value: messageStats['total'] || 0,
          icon: <MessageSquare className="w-5 h-5 text-blue-500" />,
          description: 'All time'
        },
        {
          title: 'Delivered Today',
          value: messageStats['delivered'] || 0,
          icon: <CheckCircle className="w-5 h-5 text-green-500" />,
          description: 'Successfully delivered'
        },
        {
          title: 'Read Rate',
          value: messageStats && messageStats['total'] && messageStats['total'] > 0 ?
            `${Math.round(((messageStats['read'] || 0) / messageStats['total']) * 100)}%` : '0%',
          icon: <Activity className="w-5 h-5 text-purple-500" />,
          description: 'Message engagement'
        }
      );
    }

    return cards;
  };

  if (!isEvolutionEnabled) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <Phone className="w-16 h-16 mx-auto mb-4 text-gray-400" />
          <h2 className="text-xl font-semibold mb-2">WhatsApp Integration Disabled</h2>
          <p className="text-gray-600 mb-4">
            WhatsApp integration is currently disabled. To enable it, set <code>VITE_ENABLE_EVOLUTION=true</code> in your environment variables.
          </p>
          <Alert>
            <AlertCircle className="w-4 h-4" />
            <AlertDescription>
              Make sure you have Evolution API configured and running before enabling this feature.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">WhatsApp Integration</h1>
          <p className="text-gray-600">Manage WhatsApp instances and send messages to patients</p>
        </div>
        {selectedInstance && (
          <Badge variant={selectedInstance.isConnected ? "default" : "secondary"} className="px-3 py-1">
            {selectedInstance.name} - {selectedInstance.isConnected ? 'Connected' : 'Disconnected'}
          </Badge>
        )}
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Statistics Cards */}
      {getStatCards().length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {getStatCards().map((stat, index) => (
            <Card key={index}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">{stat.title}</p>
                    <p className="text-2xl font-bold">{stat.value}</p>
                    {stat.description && (
                      <p className="text-xs text-gray-500">{stat.description}</p>
                    )}
                  </div>
                  {stat.icon}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Main Content */}
      <Tabs defaultValue="instances" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="instances" className="flex items-center gap-2">
            <Phone className="w-4 h-4" />
            Instances
          </TabsTrigger>
          <TabsTrigger value="messaging" className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            Send Messages
          </TabsTrigger>
          <TabsTrigger value="analytics" className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            Analytics
          </TabsTrigger>
        </TabsList>

        <TabsContent value="instances">
          <WhatsAppInstanceManager onInstanceSelected={handleInstanceSelected} />
        </TabsContent>

        <TabsContent value="messaging">
          {selectedInstance?.isConnected ? (
            <WhatsAppMessageSender
              instanceName={selectedInstance.name}
              onMessageSent={(response) => {
                // Refresh statistics after sending a message
                loadMessageStatistics(selectedInstance.name);
              }}
              onError={setError}
            />
          ) : (
            <Card>
              <CardContent className="p-8 text-center">
                <MessageSquare className="w-16 h-16 mx-auto mb-4 text-gray-400" />
                <h3 className="text-lg font-semibold mb-2">No Connected Instance</h3>
                <p className="text-gray-600">
                  Please select and connect a WhatsApp instance to send messages.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="analytics">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Message Statistics */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5" />
                  Message Statistics
                </CardTitle>
              </CardHeader>
              <CardContent>
                {messageStats ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="text-center p-3 bg-blue-50 rounded">
                        <p className="text-2xl font-bold text-blue-600">{messageStats['total'] || 0}</p>
                        <p className="text-sm text-blue-600">Total Messages</p>
                      </div>
                      <div className="text-center p-3 bg-green-50 rounded">
                        <p className="text-2xl font-bold text-green-600">{messageStats['sent'] || 0}</p>
                        <p className="text-sm text-green-600">Sent</p>
                      </div>
                      <div className="text-center p-3 bg-orange-50 rounded">
                        <p className="text-2xl font-bold text-orange-600">{messageStats['delivered'] || 0}</p>
                        <p className="text-sm text-orange-600">Delivered</p>
                      </div>
                      <div className="text-center p-3 bg-purple-50 rounded">
                        <p className="text-2xl font-bold text-purple-600">{messageStats['read'] || 0}</p>
                        <p className="text-sm text-purple-600">Read</p>
                      </div>
                    </div>

                    {messageStats && messageStats['failed'] && messageStats['failed'] > 0 && (
                      <div className="text-center p-3 bg-red-50 rounded">
                        <p className="text-2xl font-bold text-red-600">{messageStats['failed']}</p>
                        <p className="text-sm text-red-600">Failed Messages</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>No statistics available</p>
                    <p className="text-sm">Send some messages to see analytics</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Queue Status */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="w-5 h-5" />
                  Queue Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                {queueStats ? (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                      <span className="font-medium">Pending</span>
                      <Badge variant="secondary">{queueStats.pending}</Badge>
                    </div>
                    <div className="flex justify-between items-center p-3 bg-blue-50 rounded">
                      <span className="font-medium">Scheduled</span>
                      <Badge variant="default">{queueStats.scheduled}</Badge>
                    </div>
                    <div className="flex justify-between items-center p-3 bg-orange-50 rounded">
                      <span className="font-medium">Retry Queue</span>
                      <Badge variant="outline">{queueStats.retryScheduled}</Badge>
                    </div>
                    {queueStats.deadLetter > 0 && (
                      <div className="flex justify-between items-center p-3 bg-red-50 rounded">
                        <span className="font-medium">Failed</span>
                        <Badge variant="destructive">{queueStats.deadLetter}</Badge>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>Queue statistics unavailable</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default WhatsAppDashboard;