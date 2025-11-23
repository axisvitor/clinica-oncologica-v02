import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api-client";
import { SystemHealthOverview } from "@/lib/api-client/hive-mind";
import { Activity, AlertTriangle, CheckCircle, Server } from "lucide-react";

export function SystemHealth() {
    const [health, setHealth] = useState<SystemHealthOverview | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchHealth = async () => {
            try {
                const data = await apiClient.hiveMind.health();
                setHealth(data);
            } catch (err) {
                setError("Failed to fetch system health");
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchHealth();
        const interval = setInterval(fetchHealth, 30000); // Refresh every 30s
        return () => clearInterval(interval);
    }, []);

    if (loading) {
        return <SystemHealthSkeleton />;
    }

    if (error) {
        return (
            <Card className="border-red-200 bg-red-50">
                <CardContent className="pt-6 text-red-600">
                    <div className="flex items-center gap-2">
                        <AlertTriangle className="h-5 w-5" />
                        <span>{error}</span>
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (!health) return null;

    const getStatusColor = (status: string) => {
        switch (status) {
            case "healthy": return "bg-green-500";
            case "degraded": return "bg-yellow-500";
            case "down": return "bg-red-500";
            default: return "bg-gray-500";
        }
    };

    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">System Status</CardTitle>
                    <Activity className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-2">
                        <div className={`h-3 w-3 rounded-full ${getStatusColor(health.status)}`} />
                        <div className="text-2xl font-bold capitalize">{health.status}</div>
                    </div>
                    <p className="text-xs text-muted-foreground">
                        Last updated: {new Date(health.timestamp).toLocaleTimeString()}
                    </p>
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Active Agents</CardTitle>
                    <Server className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">
                        {health.system_health.active_agents} / {health.system_health.total_agents}
                    </div>
                    <p className="text-xs text-muted-foreground">
                        Agents online and ready
                    </p>
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Active Alerts</CardTitle>
                    <AlertTriangle className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">
                        {health.system_health.total_active_alerts}
                    </div>
                    <p className="text-xs text-muted-foreground">
                        System alerts requiring attention
                    </p>
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Uptime</CardTitle>
                    <CheckCircle className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">
                        {formatUptime(health.system_health.system_uptime_seconds)}
                    </div>
                    <p className="text-xs text-muted-foreground">
                        Continuous operation time
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}

function formatUptime(seconds: number): string {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    if (days > 0) return `${days}d ${hours}h`;
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
}

function SystemHealthSkeleton() {
    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
                <Card key={i}>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <Skeleton className="h-4 w-[100px]" />
                        <Skeleton className="h-4 w-4" />
                    </CardHeader>
                    <CardContent>
                        <Skeleton className="h-8 w-[60px] mb-2" />
                        <Skeleton className="h-3 w-[120px]" />
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}
