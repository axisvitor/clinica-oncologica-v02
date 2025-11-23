import React from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  MessageSquare,
  FileText,
  TriangleAlert as AlertTriangle,
  Settings,
  ChartBar as BarChart3,
  ClipboardList,
  Shield,
  Calendar,
  X,
  AlertOctagon,
  Workflow,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/app/providers/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRoleGuard, PermissionGate } from "@/features/auth/ProtectedRoute";
import { getRoleLabel, getRoleColor, type RolePermissions } from "@/types/shared";

interface NavigationItem {
  name: string;
  href: string;
  icon: React.ElementType;
  requiredPermission?: keyof RolePermissions;
  badge?: string;
  badgeVariant?: "default" | "secondary" | "destructive" | "outline";
}

/**
 * Navigation items available to all authenticated users
 */
const baseNavigation: NavigationItem[] = [
  {
    name: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    name: "Pacientes",
    href: "/patients",
    icon: Users,
    requiredPermission: "canManagePatients",
  },
  {
    name: "Mensagens",
    href: "/messages",
    icon: MessageSquare,
  },
  {
    name: "Questionários",
    href: "/quiz",
    icon: ClipboardList,
  },
  {
    name: "Quiz Mensal",
    href: "/monthly-quiz",
    icon: Calendar,
  },
  {
    name: "Relatórios",
    href: "/reports",
    icon: FileText,
    requiredPermission: "canViewReports",
  },
  {
    name: "Alertas",
    href: "/alerts",
    icon: AlertTriangle,
  },
  {
    name: "Análises",
    href: "/analytics",
    icon: BarChart3,
  },
];

/**
 * Admin-only navigation items
 */
const adminNavigation: NavigationItem[] = [
  {
    name: "Administração",
    href: "/admin",
    icon: Shield,
    requiredPermission: "canAccessAdmin",
    badge: "Admin",
    badgeVariant: "destructive",
  },
  {
    name: "Configurações",
    href: "/settings",
    icon: Settings,
    requiredPermission: "canManageSettings",
  },
  {
    name: "Flows",
    href: "/flows",
    icon: Workflow,
    requiredPermission: "canManageFlows",
  },
  {
    name: "Dead Letter Queue",
    href: "/dlq",
    icon: AlertOctagon,
    requiredPermission: "canAccessAdmin",
    badge: "Dev",
    badgeVariant: "outline",
  },
];

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const location = useLocation();
  const { user } = useAuth();
  const { permissions, userRole, isAdmin } = useRoleGuard();

  /**
   * Filter navigation items based on user permissions
   */
  const getFilteredNavigation = (): NavigationItem[] => {
    const allItems = [...baseNavigation, ...adminNavigation];

    return allItems.filter((item) => {
      // If no permission required, show to everyone
      if (!item.requiredPermission) {
        return true;
      }

      // Check if user has the required permission
      return permissions[item.requiredPermission];
    });
  };

  const filteredNavigation = getFilteredNavigation();

  /**
   * Get role badge color classes
   */
  const getRoleBadgeClasses = () => {
    return getRoleColor(userRole);
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "flex flex-col w-64 bg-white border-r border-gray-200 fixed lg:static inset-y-0 left-0 z-50 transform transition-transform duration-300 ease-in-out",
          isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
        aria-label="Navegação principal"
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-4 md:px-6 border-b border-gray-200">
          <div className="flex-1" />
          <img
            src="/images/logo_system.svg"
            alt="Neoplasias Litoral Logo"
            className="h-14 w-auto"
          />
          <div className="flex-1 flex justify-end">
            {/* Close button (mobile only) */}
            <Button
              variant="ghost"
              size="sm"
              className="lg:hidden"
              onClick={onClose}
              aria-label="Fechar menu"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>
        </div>

        {/* User Info with Role Badge */}
        {user && (
          <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {user["full_name"] || user["email"]}
                </p>
                <p className="text-xs text-gray-500 truncate">{user["email"]}</p>
              </div>
              <Badge
                variant={isAdmin ? "default" : "secondary"}
                className={cn("ml-2 shrink-0", getRoleBadgeClasses())}
              >
                {getRoleLabel(userRole)}
              </Badge>
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav
          className="flex-1 px-3 md:px-4 py-4 md:py-6 space-y-1 overflow-y-auto"
          aria-label="Menu de navegação"
        >
          {filteredNavigation.map((item) => {
            const isActive =
              location.pathname === item.href ||
              (item.href !== "/dashboard" && location.pathname.startsWith(item.href));

            return (
              <NavLink
                key={item.name}
                to={item.href}
                onClick={() => onClose()}
                className={cn(
                  "flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg transition-colors group",
                  isActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-700 hover:bg-gray-50 hover:text-gray-900",
                )}
                aria-current={isActive ? "page" : undefined}
              >
                <div className="flex items-center min-w-0 flex-1">
                  <item.icon
                    className={cn(
                      "mr-3 h-5 w-5 shrink-0",
                      isActive ? "text-blue-700" : "text-gray-400 group-hover:text-gray-600",
                    )}
                  />
                  <span className="truncate">{item.name}</span>
                </div>

                {/* Optional badge */}
                {item.badge && (
                  <Badge
                    variant={item.badgeVariant || "secondary"}
                    className="ml-2 text-xs shrink-0"
                  >
                    {item.badge}
                  </Badge>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Permission Summary (visible in dev mode or for admins) */}
        {isAdmin && (
          <div className="px-4 py-3 border-t border-gray-200 bg-gray-50">
            <details className="group">
              <summary className="text-xs font-medium text-gray-700 cursor-pointer hover:text-gray-900 flex items-center justify-between">
                <span>Permissões</span>
                <span className="text-gray-400 group-open:rotate-90 transition-transform">▶</span>
              </summary>
              <div className="mt-2 space-y-1 text-xs">
                {Object.entries(permissions).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between py-1">
                    <span className="text-gray-600 truncate flex-1">{key.replace(/^can/, "")}</span>
                    <span className={value ? "text-green-600" : "text-red-600"}>
                      {value ? "✓" : "✗"}
                    </span>
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}

        {/* Footer */}
        <div className="p-3 md:p-4 border-t border-gray-200">
          <div className="text-xs text-gray-500 text-center space-y-1">
            <p className="font-medium">Neoplasias Litoral</p>
            <p>Sistema de Oncologia v1.0.0</p>
            <PermissionGate permission="canAccessAdmin">
              <p className="text-blue-600 font-medium">🛡️ Admin Mode</p>
            </PermissionGate>
          </div>
        </div>
      </aside>
    </>
  );
}
