/**
 * WhatsApp Instance Manager Component
 * Manages WhatsApp instances, QR codes, and connection status
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Phone,
  QrCode,
  RefreshCw,
  Trash2,
  Plus,
  CheckCircle,
  XCircle,
  Clock,
  User,
  Activity
} from 'lucide-react';
import { whatsAppService, WhatsAppInstance } from '../../services/whatsapp/WhatsAppService';
import { createLogger } from '@/lib/logger';
import { useToast } from '@/components/ui/use-toast';

interface WhatsAppInstanceManagerProps {
  onInstanceSelected?: (instance: WhatsAppInstance) => void;
}

const logger = createLogger('WhatsAppInstanceManager');

export const WhatsAppInstanceManager: React.FC<WhatsAppInstanceManagerProps> = ({
  onInstanceSelected
}) => {
  const { toast } = useToast()
  const [instances, setInstances] = useState<WhatsAppInstance[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newInstanceName, setNewInstanceName] = useState('');
  const [creatingInstance, setCreatingInstance] = useState(false);
  const [qrCodes, setQrCodes] = useState<Record<string, string>>({});
  const [selectedInstance, setSelectedInstance] = useState<string | null>(null);
  const [confirmDeleteName, setConfirmDeleteName] = useState<string | null>(null);

  const loadInstances = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await whatsAppService.listInstances();
      setInstances(response.instances);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load instances');
    } finally {
      setLoading(false);
    }
  }, []);

  const createInstance = async () => {
    if (!newInstanceName.trim()) {
      setError('Instance name is required');
      return;
    }

    try {
      setCreatingInstance(true);
      setError(null);

      await whatsAppService.createInstance(newInstanceName.trim());
      setNewInstanceName('');
      await loadInstances();

      // Auto-load QR code for new instance
      setTimeout(() => loadQrCode(newInstanceName.trim()), 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create instance');
    } finally {
      setCreatingInstance(false);
    }
  };

  const deleteInstance = async (instanceName: string) => {
    if (confirmDeleteName === instanceName) {
      setConfirmDeleteName(null)
      try {
        setError(null);
        await whatsAppService.deleteInstance(instanceName);
        await loadInstances();
        setQrCodes(prev => {
          const updated = { ...prev };
          delete updated[instanceName];
          return updated;
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete instance');
      }
      return
    }
    setConfirmDeleteName(instanceName)
    toast({
      title: 'Confirm deletion',
      description: `Click delete again to remove instance "${instanceName}"`,
      variant: 'destructive'
    })
    setTimeout(() => {
      setConfirmDeleteName((prev) => (prev === instanceName ? null : prev))
    }, 3000)
  };

  const restartInstance = async (instanceName: string) => {
    try {
      setError(null);
      await whatsAppService.restartInstance(instanceName);
      await loadInstances();

      // Load QR code after restart
      setTimeout(() => loadQrCode(instanceName), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to restart instance');
    }
  };

  const loadQrCode = async (instanceName: string) => {
    try {
      const response = await whatsAppService.getQrCode(instanceName);
      setQrCodes(prev => ({
        ...prev,
        [instanceName]: response.qr_code
      }));
    } catch (err) {
      // QR code might not be available if already connected
      logger.log(`QR code not available for ${instanceName}:`, err);
    }
  };

  const refreshInstanceStatus = async (instanceName: string) => {
    try {
      const instance = await whatsAppService.getInstanceStatus(instanceName);
      setInstances(prev =>
        prev.map(inst =>
          inst.name === instanceName
            ? { ...inst, ...instance }
            : inst
        )
      );

      if (!instance.isConnected) {
        await loadQrCode(instanceName);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh status');
    }
  };

  const handleInstanceSelect = (instance: WhatsAppInstance) => {
    setSelectedInstance(instance.name);
    onInstanceSelected?.(instance);
  };

  const getStatusBadge = (instance: WhatsAppInstance) => {
    if (instance.isConnected) {
      return <Badge variant="default" className="bg-green-500"><CheckCircle className="w-3 h-3 mr-1" />Connected</Badge>;
    } else if (instance.status === 'created' || instance.status === 'disconnected') {
      return <Badge variant="secondary"><Clock className="w-3 h-3 mr-1" />Waiting</Badge>;
    } else {
      return <Badge variant="destructive"><XCircle className="w-3 h-3 mr-1" />Disconnected</Badge>;
    }
  };

  useEffect(() => {
    loadInstances();

    // Refresh instances every 30 seconds
    const interval = setInterval(loadInstances, 30000);
    return () => clearInterval(interval);
  }, [loadInstances]);

  return (
    <div className="space-y-6">
      {/* Create New Instance */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="w-5 h-5" />
            Create WhatsApp Instance
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="flex gap-2">
            <div className="flex-1">
              <Label htmlFor="instanceName">Instance Name</Label>
              <Input
                id="instanceName"
                value={newInstanceName}
                onChange={(e) => setNewInstanceName(e.target.value)}
                placeholder="e.g., clinic-main, reception-desk"
                disabled={creatingInstance}
              />
            </div>
            <div className="flex items-end">
              <Button
                onClick={createInstance}
                disabled={creatingInstance || !newInstanceName.trim()}
              >
                {creatingInstance ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Create
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Instances List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Phone className="w-5 h-5" />
              WhatsApp Instances ({instances.length})
            </span>
            <Button variant="outline" size="sm" onClick={loadInstances} disabled={loading}>
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading && instances.length === 0 ? (
            <div className="text-center py-8">
              <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2" />
              <p>Loading instances...</p>
            </div>
          ) : instances.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Phone className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No WhatsApp instances found</p>
              <p className="text-sm">Create your first instance to get started</p>
            </div>
          ) : (
            <div className="space-y-4">
              {instances.map((instance) => (
                <Card
                  key={instance.name}
                  className={`cursor-pointer transition-shadow hover:shadow-md ${
                    selectedInstance === instance.name ? 'ring-2 ring-blue-500' : ''
                  }`}
                  onClick={() => handleInstanceSelect(instance)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      handleInstanceSelect(instance)
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  aria-pressed={selectedInstance === instance.name}
                  aria-label={`Selecionar instancia ${instance.name}`}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="flex flex-col">
                          <h3 className="font-medium">{instance.name}</h3>
                          <p className="text-sm text-gray-500">
                            Created {new Date(instance.createdAt).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {getStatusBadge(instance)}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            refreshInstanceStatus(instance.name);
                          }}
                          aria-label="Atualizar status"
                        >
                          <Activity className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>

                    {instance.isConnected && (
                      <div className="flex items-center gap-4 mb-3 p-2 bg-green-50 rounded">
                        <User className="w-4 h-4 text-green-600" />
                        <div className="text-sm">
                          <p className="font-medium">{instance.profileName || 'WhatsApp User'}</p>
                          <p className="text-gray-600">{instance.phoneNumber}</p>
                        </div>
                      </div>
                    )}

                    {!instance.isConnected && qrCodes[instance.name] && (
                      <div className="mb-3 p-4 bg-gray-50 rounded text-center">
                        <QrCode className="w-6 h-6 mx-auto mb-2" />
                        <p className="text-sm font-medium mb-2">Scan QR Code with WhatsApp</p>
                        <div className="bg-white p-2 rounded inline-block">
                          <img
                            src={`data:image/png;base64,${qrCodes[instance.name]}`}
                            alt="QR Code"
                            width={128}
                            height={128}
                            className="w-32 h-32"
                          />
                        </div>
                        <p className="text-xs text-gray-500 mt-2">
                          Open WhatsApp → Settings → Linked Devices → Link a Device
                        </p>
                      </div>
                    )}

                    <div className="flex gap-2 justify-end">
                      {!instance.isConnected && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            loadQrCode(instance.name);
                          }}
                        >
                          <QrCode className="w-3 h-3 mr-1" />
                          Show QR
                        </Button>
                      )}

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          restartInstance(instance.name);
                        }}
                      >
                        <RefreshCw className="w-3 h-3 mr-1" />
                        Restart
                      </Button>

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteInstance(instance.name);
                        }}
                        className="text-red-600 hover:text-red-700"
                      >
                        <Trash2 className="w-3 h-3 mr-1" />
                        Delete
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default WhatsAppInstanceManager;
