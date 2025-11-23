import React, { useEffect, useState } from 'react';
import { Activity, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { QueueStatusV2 } from '@/lib/api-client/types';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';

export function TaskHealthIndicator() {
    const [queues, setQueues] = useState<QueueStatusV2[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    const fetchData = async () => {
        try {
            setLoading(true);
            const data = await apiClient.tasks.getQueueStatus();
            setQueues(data);
            setLastUpdated(new Date());
            setError(null);
        } catch (err) {
            console.error('Failed to fetch queue status:', err);
            setError('Failed to fetch status');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000); // Poll every 30s
        return () => clearInterval(interval);
    }, []);

    // Calculate overall health
    const totalPending = queues.reduce((acc, q) => acc + q.pending_count, 0);
    const totalActive = queues.reduce((acc, q) => acc + q.active_count, 0);

    let statusColor = 'bg-green-500';
    let statusIcon = <CheckCircle className="h-4 w-4 text-green-500" />;

    if (error) {
        statusColor = 'bg-red-500';
        statusIcon = <AlertCircle className="h-4 w-4 text-red-500" />;
    } else if (totalPending > 50) {
        statusColor = 'bg-red-500';
        statusIcon = <AlertCircle className="h-4 w-4 text-red-500" />;
    } else if (totalPending > 10) {
        statusColor = 'bg-yellow-500';
        statusIcon = <Clock className="h-4 w-4 text-yellow-500" />;
    }

    return (
        <Popover>
            <PopoverTrigger asChild>
                <Button variant="ghost" size="sm" className="relative h-8 w-8 rounded-full">
                    <Activity className="h-4 w-4 text-gray-500" />
                    <span className={`absolute top-1 right-1 h-2 w-2 rounded-full ${statusColor} ring-1 ring-white`} />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-80" align="end">
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h4 className="font-medium leading-none">System Tasks</h4>
                        <Button variant="ghost" size="sm" onClick={fetchData} disabled={loading}>
                            Refresh
                        </Button>
                    </div>

                    {error ? (
                        <div className="text-sm text-red-500 bg-red-50 p-2 rounded">
                            {error}
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">Active Tasks:</span>
                                <span className="font-medium">{totalActive}</span>
                            </div>
                            <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">Pending Tasks:</span>
                                <span className="font-medium">{totalPending}</span>
                            </div>

                            <div className="border-t pt-2 mt-2">
                                <h5 className="text-xs font-semibold mb-2 text-muted-foreground">Queue Status</h5>
                                <ScrollArea className="h-[200px]">
                                    <div className="space-y-2">
                                        {queues.map((queue) => (
                                            <div key={queue.queue_name} className="flex items-center justify-between text-sm p-2 bg-gray-50 rounded">
                                                <div>
                                                    <div className="font-medium">{queue.queue_name}</div>
                                                    <div className="text-xs text-muted-foreground">
                                                        {queue.workers.length} workers
                                                    </div>
                                                </div>
                                                <div className="text-right">
                                                    <Badge variant={queue.pending_count > 0 ? "secondary" : "outline"}>
                                                        {queue.pending_count} pending
                                                    </Badge>
                                                </div>
                                            </div>
                                        ))}
                                        {queues.length === 0 && (
                                            <div className="text-sm text-muted-foreground text-center py-4">
                                                No active queues found
                                            </div>
                                        )}
                                    </div>
                                </ScrollArea>
                            </div>
                        </div>
                    )}

                    {lastUpdated && (
                        <div className="text-xs text-muted-foreground text-center border-t pt-2">
                            Last updated: {lastUpdated.toLocaleTimeString()}
                        </div>
                    )}
                </div>
            </PopoverContent>
        </Popover>
    );
}
