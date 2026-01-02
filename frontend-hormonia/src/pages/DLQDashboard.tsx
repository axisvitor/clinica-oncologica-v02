/**
 * DLQ Dashboard - Dead Letter Queue Management
 *
 * Dashboard administrativo para gerenciamento de mensagens com falha.
 *
 * Features:
 * - Visualização de métricas em tempo real
 * - Lista de mensagens na DLQ
 * - Ações de retry e descarte
 * - Filtros por categoria, status e data
 * - Paginação
 */

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
  RefreshCw,
  Trash2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Clock,
  Filter,
  Search,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { apiClient } from "@/lib/api-client";

// ============================================================================
// Types
// ============================================================================

interface DLQMessage {
  id: string;
  message_id: string;
  patient_id: string;
  patient_name?: string;
  error_message: string;
  error_type: string;
  failure_reason: "webhook" | "whatsapp" | "flow" | "quiz" | "notification" | "other";
  status:
  | "pending"
  | "retrying"
  | "retry_scheduled"
  | "resolved"
  | "discarded"
  | "max_retries_exceeded";
  retry_count: number;
  created_at: string;
  last_retry_at?: string;
  resolved_at?: string;
  metadata?: Record<string, unknown>;
}

interface DLQStats {
  total_messages: number;
  pending: number;
  retrying: number;
  retry_scheduled: number;
  resolved: number;
  discarded: number;
  max_retries_exceeded: number;
  by_category: Record<string, number>;
  avg_retry_count: number;
  oldest_message_age_hours: number;
}

interface DLQListResponse {
  messages: DLQMessage[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// ============================================================================
// API Functions
// ============================================================================

const fetchDLQStats = async (): Promise<DLQStats> => {
  const response = await apiClient.get("/admin/dlq/stats");
  return response as DLQStats;
};

const fetchDLQMessages = async (
  page: number,
  size: number,
  status?: string,
  category?: string,
  search?: string,
): Promise<DLQListResponse> => {
  const params = new URLSearchParams({
    page: page.toString(),
    size: size.toString(),
  });

  if (status && status !== "all") params.append("status", status);
  if (category && category !== "all") params.append("category", category);
  if (search) params.append("search", search);

  const response = await apiClient.get(`/admin/dlq/messages?${params}`);
  return response as DLQListResponse;
};

const retryDLQMessage = async (messageId: string): Promise<void> => {
  await apiClient.post(`/admin/dlq/messages/${messageId}/retry`);
};

const discardDLQMessage = async (messageId: string): Promise<void> => {
  await apiClient.post(`/admin/dlq/messages/${messageId}/discard`);
};

// ============================================================================
// Component
// ============================================================================

export function DLQDashboard() {
  // State
  const [page, setPage] = useState(1);
  const [size] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [messageToRetry, setMessageToRetry] = useState<string | null>(null);
  const [messageToDiscard, setMessageToDiscard] = useState<string | null>(null);

  const queryClient = useQueryClient();

  // Queries
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useQuery({
    queryKey: ["dlq-stats"],
    queryFn: fetchDLQStats,
    refetchInterval: 30000, // Refresh every 30s
  });

  const {
    data: messagesData,
    isLoading: messagesLoading,
    error: messagesError,
  } = useQuery({
    queryKey: ["dlq-messages", page, size, statusFilter, categoryFilter, searchTerm],
    queryFn: () => fetchDLQMessages(page, size, statusFilter, categoryFilter, searchTerm),
    refetchInterval: 30000,
  });

  // Mutations
  const retryMutation = useMutation({
    mutationFn: retryDLQMessage,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dlq-stats"] });
      queryClient.invalidateQueries({ queryKey: ["dlq-messages"] });
      setMessageToRetry(null);
    },
  });

  const discardMutation = useMutation({
    mutationFn: discardDLQMessage,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dlq-stats"] });
      queryClient.invalidateQueries({ queryKey: ["dlq-messages"] });
      setMessageToDiscard(null);
    },
  });

  // Handlers
  const handleRetry = (messageId: string) => {
    setMessageToRetry(messageId);
  };

  const handleDiscard = (messageId: string) => {
    setMessageToDiscard(messageId);
  };

  const confirmRetry = () => {
    if (messageToRetry) {
      retryMutation.mutate(messageToRetry);
    }
  };

  const confirmDiscard = () => {
    if (messageToDiscard) {
      discardMutation.mutate(messageToDiscard);
    }
  };

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["dlq-stats"] });
    queryClient.invalidateQueries({ queryKey: ["dlq-messages"] });
  };

  // Helpers
  const getStatusBadge = (status: string) => {
    const variants: Record<
      string,
      { variant: "default" | "secondary" | "destructive" | "outline"; icon: any }
    > = {
      pending: { variant: "outline", icon: Clock },
      retrying: { variant: "default", icon: RefreshCw },
      retry_scheduled: { variant: "secondary", icon: Clock },
      resolved: { variant: "default", icon: CheckCircle2 },
      discarded: { variant: "destructive", icon: Trash2 },
      max_retries_exceeded: { variant: "destructive", icon: XCircle },
    };

    const config = variants[status] || { variant: "outline", icon: AlertCircle };
    const Icon = config.icon;

    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <Icon className="h-3 w-3" />
        {status.replace(/_/g, " ")}
      </Badge>
    );
  };

  const getCategoryBadge = (category: string) => {
    const colors: Record<string, string> = {
      webhook: "bg-blue-100 text-blue-800",
      whatsapp: "bg-green-100 text-green-800",
      flow: "bg-purple-100 text-purple-800",
      quiz: "bg-yellow-100 text-yellow-800",
      notification: "bg-pink-100 text-pink-800",
      other: "bg-gray-100 text-gray-800",
    };

    return <Badge className={colors[category] || colors["other"]}>{category}</Badge>;
  };

  // ============================================================================
  // Render
  // ============================================================================

  if (statsError || messagesError) {
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>Erro ao carregar dados da DLQ. Tente novamente.</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dead Letter Queue</h1>
          <p className="text-muted-foreground mt-1">Gerenciamento de mensagens com falha</p>
        </div>
        <Button onClick={handleRefresh} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Atualizar
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total na DLQ</CardTitle>
            <AlertCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <>
                <div className="text-2xl font-bold">{stats?.total_messages || 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {stats?.pending || 0} pendentes
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Resolvidas</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <>
                <div className="text-2xl font-bold text-green-600">{stats?.resolved || 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  <TrendingUp className="h-3 w-3 inline mr-1" />
                  Sucesso no retry
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Max Retries</CardTitle>
            <XCircle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <>
                <div className="text-2xl font-bold text-red-600">
                  {stats?.max_retries_exceeded || 0}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  <TrendingDown className="h-3 w-3 inline mr-1" />
                  Requer intervenção
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Média de Retries</CardTitle>
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {stats?.avg_retry_count?.toFixed(1) || "0.0"}
                </div>
                <p className="text-xs text-muted-foreground mt-1">Tentativas por mensagem</p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Filtros</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  name="dlqSearch"
                  placeholder="Buscar por ID ou paciente..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>

            <Select name="statusFilter" value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full md:w-[200px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="pending">Pendente</SelectItem>
                <SelectItem value="retrying">Retrying</SelectItem>
                <SelectItem value="retry_scheduled">Agendado</SelectItem>
                <SelectItem value="resolved">Resolvido</SelectItem>
                <SelectItem value="discarded">Descartado</SelectItem>
                <SelectItem value="max_retries_exceeded">Max Retries</SelectItem>
              </SelectContent>
            </Select>

            <Select name="categoryFilter" value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-full md:w-[200px]">
                <SelectValue placeholder="Categoria" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                <SelectItem value="webhook">Webhook</SelectItem>
                <SelectItem value="whatsapp">WhatsApp</SelectItem>
                <SelectItem value="flow">Flow</SelectItem>
                <SelectItem value="quiz">Quiz</SelectItem>
                <SelectItem value="notification">Notificação</SelectItem>
                <SelectItem value="other">Outros</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Messages Table */}
      <Card>
        <CardHeader>
          <CardTitle>Mensagens na DLQ</CardTitle>
          <CardDescription>{messagesData?.total || 0} mensagens encontradas</CardDescription>
        </CardHeader>
        <CardContent>
          {messagesLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : messagesData?.messages.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">Nenhuma mensagem na DLQ</h3>
              <p className="text-muted-foreground">Tudo funcionando perfeitamente! 🎉</p>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Categoria</TableHead>
                    <TableHead>Paciente</TableHead>
                    <TableHead>Erro</TableHead>
                    <TableHead>Retries</TableHead>
                    <TableHead>Criado em</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {messagesData?.messages.map((message) => (
                    <TableRow key={message.id}>
                      <TableCell>{getStatusBadge(message.status)}</TableCell>
                      <TableCell>{getCategoryBadge(message.failure_reason)}</TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-medium">
                            {message.patient_name || "Desconhecido"}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            ID: {message.patient_id.substring(0, 8)}...
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="max-w-xs">
                          <p className="text-sm font-medium">{message.error_type}</p>
                          <p className="text-xs text-muted-foreground truncate">
                            {message.error_message}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{message.retry_count}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col text-sm">
                          <span>
                            {format(new Date(message.created_at), "dd/MM/yyyy", {
                              locale: ptBR,
                            })}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {format(new Date(message.created_at), "HH:mm", {
                              locale: ptBR,
                            })}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          {!["resolved", "discarded"].includes(message.status) && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleRetry(message.id)}
                                disabled={retryMutation.isPending}
                              >
                                <RefreshCw className="h-4 w-4" />
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => handleDiscard(message.id)}
                                disabled={discardMutation.isPending}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {messagesData && messagesData.pages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    Página {messagesData.page} de {messagesData.pages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={messagesData.page === 1}
                    >
                      Anterior
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setPage((p) => p + 1)}
                      disabled={messagesData.page === messagesData.pages}
                    >
                      Próximo
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Retry Confirmation Dialog */}
      <AlertDialog open={!!messageToRetry} onOpenChange={() => setMessageToRetry(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar Retry</AlertDialogTitle>
            <AlertDialogDescription>
              Deseja realmente tentar reprocessar esta mensagem? A mensagem será enviada novamente
              para o sistema.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={confirmRetry}>Confirmar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Discard Confirmation Dialog */}
      <AlertDialog open={!!messageToDiscard} onOpenChange={() => setMessageToDiscard(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar Descarte</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja descartar esta mensagem? Esta ação não pode ser desfeita e a
              mensagem não será mais processada.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDiscard}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Descartar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default DLQDashboard;
