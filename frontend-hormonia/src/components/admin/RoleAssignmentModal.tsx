import React, { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Shield, Users, Settings, BarChart3, FileText, Database, Save } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { AdminUser } from "@/types/admin";
import { UserRole } from "@/types/shared";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useToast } from "@/components/ui/use-toast";
import { LoadingSpinner } from "@/components/ui/loading-spinner";

interface RoleAssignmentModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: AdminUser | null;
}

interface PermissionGroup {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  permissions: {
    id: string;
    name: string;
    description: string;
    level: "read" | "write" | "admin";
  }[];
}

const PERMISSION_GROUPS: PermissionGroup[] = [
  {
    id: "users",
    name: "Gerenciamento de Usuários",
    description: "Controle de usuários do sistema",
    icon: <Users className="h-4 w-4" />,
    permissions: [
      {
        id: "admin.users.read",
        name: "Visualizar Usuários",
        description: "Ver lista e detalhes de usuários",
        level: "read",
      },
      {
        id: "admin.users.create",
        name: "Criar Usuários",
        description: "Adicionar novos usuários ao sistema",
        level: "write",
      },
      {
        id: "admin.users.update",
        name: "Editar Usuários",
        description: "Modificar informações de usuários",
        level: "write",
      },
      {
        id: "admin.users.delete",
        name: "Excluir Usuários",
        description: "Remover usuários do sistema",
        level: "admin",
      },
      {
        id: "admin.users.permissions",
        name: "Gerenciar Permissões",
        description: "Atribuir e remover permissões de usuários",
        level: "admin",
      },
    ],
  },
  {
    id: "patients",
    name: "Gerenciamento de Pacientes",
    description: "Controle de dados de pacientes",
    icon: <Shield className="h-4 w-4" />,
    permissions: [
      {
        id: "admin.patients.read",
        name: "Visualizar Pacientes",
        description: "Ver lista e detalhes de pacientes",
        level: "read",
      },
      {
        id: "admin.patients.create",
        name: "Criar Pacientes",
        description: "Adicionar novos pacientes ao sistema",
        level: "write",
      },
      {
        id: "admin.patients.update",
        name: "Editar Pacientes",
        description: "Modificar informações de pacientes",
        level: "write",
      },
      {
        id: "admin.patients.delete",
        name: "Excluir Pacientes",
        description: "Remover pacientes do sistema",
        level: "admin",
      },
      {
        id: "admin.patients.history",
        name: "Histórico Médico",
        description: "Acessar histórico completo de pacientes",
        level: "read",
      },
    ],
  },
  {
    id: "flows",
    name: "Fluxos de Tratamento",
    description: "Controle de fluxos e automações",
    icon: <Database className="h-4 w-4" />,
    permissions: [
      {
        id: "admin.flows.read",
        name: "Visualizar Fluxos",
        description: "Ver fluxos de tratamento",
        level: "read",
      },
      {
        id: "admin.flows.create",
        name: "Criar Fluxos",
        description: "Criar novos fluxos de tratamento",
        level: "write",
      },
      {
        id: "admin.flows.update",
        name: "Editar Fluxos",
        description: "Modificar fluxos existentes",
        level: "write",
      },
      {
        id: "admin.flows.delete",
        name: "Excluir Fluxos",
        description: "Remover fluxos do sistema",
        level: "admin",
      },
      {
        id: "admin.flows.execute",
        name: "Executar Fluxos",
        description: "Iniciar e parar fluxos de tratamento",
        level: "write",
      },
    ],
  },
  {
    id: "analytics",
    name: "Analytics e Relatórios",
    description: "Acesso a dados e relatórios",
    icon: <BarChart3 className="h-4 w-4" />,
    permissions: [
      {
        id: "admin.analytics.read",
        name: "Visualizar Analytics",
        description: "Ver dashboards e métricas",
        level: "read",
      },
      {
        id: "admin.analytics.export",
        name: "Exportar Dados",
        description: "Exportar relatórios e dados",
        level: "write",
      },
      {
        id: "admin.reports.create",
        name: "Criar Relatórios",
        description: "Gerar novos relatórios",
        level: "write",
      },
      {
        id: "admin.reports.schedule",
        name: "Agendar Relatórios",
        description: "Programar relatórios automáticos",
        level: "write",
      },
    ],
  },
  {
    id: "system",
    name: "Configurações do Sistema",
    description: "Controle de configurações globais",
    icon: <Settings className="h-4 w-4" />,
    permissions: [
      {
        id: "admin.settings.read",
        name: "Visualizar Configurações",
        description: "Ver configurações do sistema",
        level: "read",
      },
      {
        id: "admin.settings.update",
        name: "Editar Configurações",
        description: "Modificar configurações do sistema",
        level: "admin",
      },
      {
        id: "admin.audit.read",
        name: "Visualizar Auditoria",
        description: "Acessar logs de auditoria",
        level: "read",
      },
      {
        id: "admin.backup.create",
        name: "Criar Backups",
        description: "Gerar backups do sistema",
        level: "admin",
      },
      {
        id: "admin.maintenance.execute",
        name: "Modo Manutenção",
        description: "Ativar/desativar modo manutenção",
        level: "admin",
      },
    ],
  },
];

type RoleKey =
  | "super_admin"
  | "admin"
  | "doctor"
  | "nurse"
  | "patient"
  | "researcher"
  | "coordinator";

interface RoleTemplate {
  name: string;
  description: string;
  permissions: string[];
}

const ROLE_TEMPLATES: Record<RoleKey, RoleTemplate> = {
  super_admin: {
    name: "Super Administrador",
    description: "Acesso completo ao sistema",
    permissions: [
      "admin.users.read",
      "admin.users.create",
      "admin.users.update",
      "admin.users.delete",
      "admin.users.permissions",
      "admin.patients.read",
      "admin.patients.create",
      "admin.patients.update",
      "admin.patients.delete",
      "admin.flows.read",
      "admin.flows.create",
      "admin.flows.update",
      "admin.flows.delete",
      "admin.flows.execute",
      "admin.analytics.read",
      "admin.analytics.export",
      "admin.reports.create",
      "admin.reports.read",
      "admin.audit.read",
      "admin.settings.read",
      "admin.settings.update",
    ],
  },
  admin: {
    name: "Administrador",
    description: "Acesso administrativo padrão",
    permissions: [
      "admin.users.read",
      "admin.patients.read",
      "admin.patients.create",
      "admin.patients.update",
      "admin.flows.read",
      "admin.flows.create",
      "admin.flows.update",
      "admin.flows.execute",
      "admin.analytics.read",
      "admin.analytics.export",
      "admin.reports.create",
      "admin.reports.read",
      "admin.audit.read",
      "admin.settings.read",
    ],
  },
  doctor: {
    name: "Médico",
    description: "Acesso médico especializado",
    permissions: [
      "admin.patients.read",
      "admin.patients.create",
      "admin.patients.update",
      "admin.flows.read",
      "admin.flows.execute",
      "admin.analytics.read",
      "admin.reports.read",
    ],
  },
  nurse: {
    name: "Enfermeiro(a)",
    description: "Acesso para enfermagem",
    permissions: [
      "admin.patients.read",
      "admin.patients.update",
      "admin.flows.read",
      "admin.flows.execute",
      "admin.reports.read",
    ],
  },
  patient: {
    name: "Paciente",
    description: "Acesso limitado aos próprios dados",
    permissions: ["admin.flows.execute"],
  },
  researcher: {
    name: "Pesquisador(a)",
    description: "Acesso a dados anonimizados",
    permissions: [
      "admin.patients.read",
      "admin.analytics.read",
      "admin.analytics.export",
      "admin.reports.read",
    ],
  },
  coordinator: {
    name: "Coordenador(a)",
    description: "Coordenação de equipes e processos",
    permissions: [
      "admin.users.read",
      "admin.patients.read",
      "admin.patients.create",
      "admin.patients.update",
      "admin.flows.read",
      "admin.flows.create",
      "admin.flows.update",
      "admin.analytics.read",
      "admin.reports.read",
    ],
  },
};

export function RoleAssignmentModal({ open, onOpenChange, user }: RoleAssignmentModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [selectedRole, setSelectedRole] = useState<string>("doctor");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [hasChanges, setHasChanges] = useState(false);

  // Load user data when user changes
  useEffect(() => {
    if (user) {
      setSelectedRole(user["role"]);
      setSelectedPermissions(user.permissions);
      setHasChanges(false);
    }
  }, [user]);

  // Track changes
  useEffect(() => {
    if (!user) return;

    const roleChanged = selectedRole !== user["role"];
    const permissionsChanged =
      selectedPermissions.length !== user.permissions.length ||
      selectedPermissions.some((p) => !user.permissions.includes(p)) ||
      user.permissions.some((p) => !selectedPermissions.includes(p));

    setHasChanges(roleChanged || permissionsChanged);
  }, [selectedRole, selectedPermissions, user]);

  const updateRoleMutation = useMutation({
    mutationFn: async ({ id, role }: { id: string; role: string }) => {
      return apiClient.adminUsers.updateRole(id, role);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-user", user?.id] });
      toast({
        title: "Função atualizada com sucesso",
        description: "A função do usuário foi alterada.",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Erro ao atualizar função",
        description: error.data?.message || "Ocorreu um erro inesperado.",
        variant: "destructive",
      });
    },
  });

  const updatePermissionsMutation = useMutation({
    mutationFn: async ({ id, permissions }: { id: string; permissions: string[] }) => {
      // WARNING: Backend endpoint is currently a placeholder and doesn't persist permissions
      // TODO: Implement actual permissions storage in backend (see backend-hormonia/app/api/v2/admin/users.py:830-885)
      return apiClient.adminUsers.updatePermissions(id, permissions);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-user", user?.id] });
      toast({
        title: "⚠️ Permissões atualizadas (temporário)",
        description: "Nota: Backend ainda não persiste permissões. Implementação pendente.",
        variant: "default",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Erro ao atualizar permissões",
        description: error.data?.message || "Ocorreu um erro inesperado.",
        variant: "destructive",
      });
    },
  });

  const handleRoleChange = (role: string) => {
    setSelectedRole(role);
    const roleTemplate = ROLE_TEMPLATES[role as RoleKey];
    if (roleTemplate) {
      setSelectedPermissions(roleTemplate.permissions);
    }
  };

  const togglePermission = (permissionId: string) => {
    setSelectedPermissions((prev) =>
      prev.includes(permissionId)
        ? prev.filter((p) => p !== permissionId)
        : [...prev, permissionId],
    );
  };

  const toggleGroupPermissions = (group: PermissionGroup, enable: boolean) => {
    const groupPermissionIds = group.permissions.map((p) => p.id);

    if (enable) {
      setSelectedPermissions((prev) => [
        ...prev.filter((p) => !groupPermissionIds.includes(p)),
        ...groupPermissionIds,
      ]);
    } else {
      setSelectedPermissions((prev) => prev.filter((p) => !groupPermissionIds.includes(p)));
    }
  };

  const handleSave = async () => {
    if (!user) return;

    try {
      // Update role if changed
      if (selectedRole !== user["role"]) {
        await updateRoleMutation.mutateAsync({ id: user["id"], role: selectedRole });
      }

      // Update permissions if changed
      const permissionsChanged =
        selectedPermissions.length !== user.permissions.length ||
        selectedPermissions.some((p) => !user.permissions.includes(p)) ||
        user.permissions.some((p) => !selectedPermissions.includes(p));

      if (permissionsChanged) {
        await updatePermissionsMutation.mutateAsync({
          id: user["id"],
          permissions: selectedPermissions,
        });
      }

      onOpenChange(false);
    } catch (error) {
      // Errors are handled by the mutations
    }
  };

  const getPermissionLevelBadge = (level: "read" | "write" | "admin") => {
    const variants = {
      read: { variant: "secondary" as const, label: "Leitura" },
      write: { variant: "default" as const, label: "Escrita" },
      admin: { variant: "destructive" as const, label: "Admin" },
    };

    const { variant, label } = variants[level];
    return (
      <Badge variant={variant} className="text-xs">
        {label}
      </Badge>
    );
  };

  const isGroupFullySelected = (group: PermissionGroup) => {
    return group.permissions.every((p) => selectedPermissions.includes(p.id));
  };

  const isGroupPartiallySelected = (group: PermissionGroup) => {
    const selectedInGroup = group.permissions.filter((p) => selectedPermissions.includes(p.id));
    return selectedInGroup.length > 0 && selectedInGroup.length < group.permissions.length;
  };

  if (!user) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Gerenciar Função e Permissões</DialogTitle>
          <DialogDescription>
            Atribua função e permissões específicas para {user["full_name"]}
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="role" className="space-y-4">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="role">Função</TabsTrigger>
            <TabsTrigger value="permissions">Permissões Detalhadas</TabsTrigger>
          </TabsList>

          <TabsContent value="role" className="space-y-4">
            <div className="space-y-4">
              <div>
                <Label>Função do Usuário</Label>
                <p className="text-sm text-muted-foreground">
                  Selecione uma função que define automaticamente as permissões básicas
                </p>
              </div>

              <Select value={selectedRole} onValueChange={handleRoleChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Administrador</SelectItem>
                  <SelectItem value="doctor">Médico</SelectItem>
                </SelectContent>
              </Select>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(ROLE_TEMPLATES).map(([roleKey, template]) => (
                  <Card
                    key={roleKey}
                    className={`cursor-pointer transition-colors ${
                      selectedRole === roleKey ? "border-blue-500 bg-blue-50" : "hover:bg-gray-50"
                    }`}
                    onClick={() => handleRoleChange(roleKey)}
                  >
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">{template.name}</CardTitle>
                      <CardDescription className="text-sm">{template.description}</CardDescription>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="flex justify-between items-center">
                        <Badge variant="outline">{template.permissions.length} permissões</Badge>
                        {selectedRole === roleKey && (
                          <Badge className="bg-blue-600">Selecionado</Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <Alert>
                <Shield className="h-4 w-4" />
                <AlertDescription>
                  <strong>Função Atual:</strong>{" "}
                  {ROLE_TEMPLATES[selectedRole as RoleKey]?.name || "Não definido"}
                  <br />
                  Esta função inclui {selectedPermissions.length} permissões automaticamente.
                </AlertDescription>
              </Alert>
            </div>
          </TabsContent>

          <TabsContent value="permissions" className="space-y-4">
            <div className="space-y-4">
              <div>
                <Label>Permissões Específicas</Label>
                <p className="text-sm text-muted-foreground">
                  Personalize as permissões específicas para este usuário
                </p>
              </div>

              <div className="space-y-6">
                {PERMISSION_GROUPS.map((group) => {
                  const isFullySelected = isGroupFullySelected(group);
                  const isPartiallySelected = isGroupPartiallySelected(group);

                  return (
                    <Card key={group.id}>
                      <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {group.icon}
                            <CardTitle className="text-base">{group.name}</CardTitle>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">
                              {
                                group.permissions.filter((p) => selectedPermissions.includes(p.id))
                                  .length
                              }
                              /{group.permissions.length}
                            </Badge>
                            <Checkbox
                              checked={isFullySelected}
                              ref={(el) => {
                                if (el) {
                                  const element = el as any;
                                  (element as any).indeterminate = isPartiallySelected;
                                }
                              }}
                              onCheckedChange={(checked) =>
                                toggleGroupPermissions(group, !!checked)
                              }
                            />
                          </div>
                        </div>
                        <CardDescription>{group.description}</CardDescription>
                      </CardHeader>
                      <CardContent className="pt-0">
                        <div className="space-y-3">
                          {group.permissions.map((permission) => (
                            <div
                              key={permission.id}
                              className="flex items-center justify-between p-3 border rounded-lg"
                            >
                              <div className="flex items-center space-x-3">
                                <Checkbox
                                  checked={selectedPermissions.includes(permission.id)}
                                  onCheckedChange={() => togglePermission(permission.id)}
                                />
                                <div className="flex-1">
                                  <div className="flex items-center gap-2">
                                    <span className="font-medium text-sm">{permission.name}</span>
                                    {getPermissionLevelBadge(permission.level)}
                                  </div>
                                  <p className="text-xs text-muted-foreground mt-1">
                                    {permission.description}
                                  </p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Resumo das Permissões</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {selectedPermissions.length > 0 ? (
                      selectedPermissions.map((permission) => (
                        <Badge key={permission} variant="outline" className="text-xs">
                          {permission}
                        </Badge>
                      ))
                    ) : (
                      <p className="text-sm text-muted-foreground">Nenhuma permissão selecionada</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={updateRoleMutation.isPending || updatePermissionsMutation.isPending}
          >
            Cancelar
          </Button>
          <Button
            onClick={handleSave}
            disabled={
              !hasChanges || updateRoleMutation.isPending || updatePermissionsMutation.isPending
            }
          >
            {updateRoleMutation.isPending || updatePermissionsMutation.isPending ? (
              <>
                <LoadingSpinner size="sm" className="mr-2" />
                Salvando...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                Salvar Alterações
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
