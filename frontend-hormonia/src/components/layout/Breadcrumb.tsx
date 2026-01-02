import React from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import {
  ChevronRight,
  Home,
  Users,
  MessageSquare,
  Settings,
  User,
  FileText,
  BarChart3,
  AlertTriangle,
  HelpCircle,
  GitBranch,
  ClipboardList,
  Activity
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface BreadcrumbItem {
  label: string;
  href?: string;
  icon?: React.ReactNode;
  isActive?: boolean;
}

interface BreadcrumbProps {
  className?: string;
  items?: BreadcrumbItem[];
  showIcons?: boolean;
  showHome?: boolean;
  separator?: React.ReactNode;
  maxItems?: number;
}

// Comprehensive route mapping with icons and Portuguese labels
const routeConfig: Record<string, { name: string; icon: React.ReactNode }> = {
  dashboard: { name: 'Dashboard', icon: <BarChart3 className="h-4 w-4" /> },
  patients: { name: 'Pacientes', icon: <Users className="h-4 w-4" /> },
  messages: { name: 'Mensagens', icon: <MessageSquare className="h-4 w-4" /> },
  settings: { name: 'Configurações', icon: <Settings className="h-4 w-4" /> },
  profile: { name: 'Perfil', icon: <User className="h-4 w-4" /> },
  reports: { name: 'Relatórios', icon: <FileText className="h-4 w-4" /> },
  analytics: { name: 'Análises', icon: <Activity className="h-4 w-4" /> },
  alerts: { name: 'Alertas', icon: <AlertTriangle className="h-4 w-4" /> },
  help: { name: 'Ajuda', icon: <HelpCircle className="h-4 w-4" /> },
  flows: { name: 'Fluxos', icon: <GitBranch className="h-4 w-4" /> },
  questionarios: { name: 'Questionários', icon: <ClipboardList className="h-4 w-4" /> },
  quiz: { name: 'Quiz', icon: <ClipboardList className="h-4 w-4" /> },
};

// Helper to get patient name from ID (in real app, this would fetch from API/context)
const getPatientName = (id: string): string => {
  // In a real application, you would fetch this from your patient context or API
  // For now, return a formatted ID
  return `Paciente #${id}`;
};

export function Breadcrumb({
  className,
  items,
  showIcons = true,
  showHome = true,
  separator = <ChevronRight className="h-4 w-4 text-muted-foreground/60" />,
  maxItems = 4
}: BreadcrumbProps) {
  const location = useLocation();
  const _params = useParams(); // Used for dynamic route detection, prefixed with _ to mark intentionally unused

  // Generate breadcrumb items from URL path if not provided
  const breadcrumbItems = React.useMemo(() => {
    if (items) return items;

    const paths = location.pathname.split('/').filter(Boolean);
    const generatedItems: BreadcrumbItem[] = [];

    paths.forEach((path, index) => {
      const href = '/' + paths.slice(0, index + 1).join('/');
      const isLastItem = index === paths.length - 1;

      // Handle dynamic routes (e.g., /patients/123)
      if (!isNaN(Number(path))) {
        // Check if this is a patient ID
        const parentPath = paths[index - 1];
        if (parentPath === 'patients') {
          generatedItems.push({
            label: getPatientName(path),
            ...(isLastItem ? {} : { href }),
            ...(showIcons ? { icon: <User className="h-4 w-4" /> } : {}),
            isActive: isLastItem
          });
        } else {
          // Generic ID handling
          generatedItems.push({
            label: `#${path}`,
            ...(isLastItem ? {} : { href }),
            isActive: isLastItem
          });
        }
      } else {
        // Regular route
        const config = routeConfig[path];
        generatedItems.push({
          label: config?.name || path.charAt(0).toUpperCase() + path.slice(1),
          ...(isLastItem ? {} : { href }),
          ...(showIcons && config?.icon ? { icon: config.icon } : {}),
          isActive: isLastItem
        });
      }
    });

    // Implement breadcrumb truncation for long paths
    if (generatedItems.length > maxItems) {
      const firstItem = generatedItems[0];
      const lastItems = generatedItems.slice(-2);
      return [
        firstItem,
        { label: '...', href: undefined, isActive: false },
        ...lastItems
      ];
    }

    return generatedItems;
  }, [location.pathname, items, showIcons, maxItems]);

  if (breadcrumbItems.length === 0 && !showHome) return null;

  return (
    <nav
      aria-label="Navegação estrutural"
      className={cn(
        "flex items-center space-x-1 text-sm",
        className
      )}
      role="navigation"
    >
      {showHome && (
        <>
          <Link
            to="/dashboard"
            className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors rounded-md p-1 hover:bg-accent/50"
            aria-label="Voltar ao dashboard"
          >
            <Home className="h-4 w-4" />
            <span className="hidden sm:inline font-medium">Início</span>
          </Link>
          {breadcrumbItems.length > 0 && (
            <span className="text-muted-foreground/60" aria-hidden="true">
              {separator}
            </span>
          )}
        </>
      )}

      {breadcrumbItems.map((item, index) => (
        <React.Fragment key={`${item?.href || item?.label}-${index}`}>
          {index > 0 && (
            <span className="text-muted-foreground/60" aria-hidden="true">
              {separator}
            </span>
          )}
          {item?.href && !item?.isActive ? (
            <Link
              to={item?.href}
              className={cn(
                "flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors rounded-md p-1 hover:bg-accent/50",
                "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              )}
              aria-current={item?.isActive ? "page" : undefined}
            >
              {item && 'icon' in item && item.icon && (
                <span className="hidden sm:inline" aria-hidden="true">
                  {item.icon}
                </span>
              )}
              <span className="font-medium truncate max-w-[120px] sm:max-w-none">
                {item?.label}
              </span>
            </Link>
          ) : (
            <span
              className={cn(
                "flex items-center gap-1.5",
                item?.isActive
                  ? "text-foreground font-semibold"
                  : "text-muted-foreground"
              )}
              aria-current={item?.isActive ? "page" : undefined}
            >
              {item && 'icon' in item && item.icon && (
                <span className="hidden sm:inline" aria-hidden="true">
                  {item.icon}
                </span>
              )}
              <span className="truncate max-w-[120px] sm:max-w-none">
                {item?.label}
              </span>
            </span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}

// Compact variant for mobile or space-constrained areas
export function BreadcrumbCompact({ className, ...props }: BreadcrumbProps) {
  return (
    <Breadcrumb
      {...props}
      className={cn("space-x-0.5 text-xs", className)}
      showIcons={false}
      separator={<ChevronRight className="h-3 w-3 text-muted-foreground/60" />}
      maxItems={2}
    />
  );
}

// Breadcrumb with dropdown for overflow items
export function BreadcrumbWithDropdown({
  className,
  items,
  showIcons = true,
  maxVisibleItems = 3
}: BreadcrumbProps & { maxVisibleItems?: number }) {
  const location = useLocation();

  const allItems = React.useMemo(() => {
    if (items) return items;

    const paths = location.pathname.split('/').filter(Boolean);
    return paths.map((path, index) => {
      const href = '/' + paths.slice(0, index + 1).join('/');
      const isLastItem = index === paths.length - 1;
      const config = routeConfig[path];

      return {
        label: config?.name || path.charAt(0).toUpperCase() + path.slice(1),
        ...(isLastItem ? {} : { href }),
        ...(showIcons && config?.icon ? { icon: config.icon } : {}),
        isActive: isLastItem
      };
    });
  }, [location.pathname, items, showIcons]);

  if (allItems.length <= maxVisibleItems) {
    return <Breadcrumb {...(className ? { className } : {})} items={allItems} showIcons={showIcons} />;
  }

  const visibleItems = [
    allItems[0],
    ...allItems.slice(-2)
  ];

  return (
    <nav
      aria-label="Navegação estrutural"
      className={cn("flex items-center space-x-1 text-sm", className)}
    >
      <Link
        to="/dashboard"
        className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors rounded-md p-1 hover:bg-accent/50"
      >
        <Home className="h-4 w-4" />
        <span className="hidden sm:inline font-medium">Início</span>
      </Link>

      {visibleItems.map((item, index) => (
        <React.Fragment key={`${item?.href || item?.label}-${index}`}>
          <ChevronRight className="h-4 w-4 text-muted-foreground/60" />
          {item?.href && !item?.isActive ? (
            <Link
              to={item?.href}
              className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors rounded-md p-1 hover:bg-accent/50"
            >
              {item?.icon && <span className="hidden sm:inline">{item?.icon}</span>}
              <span className="font-medium">{item?.label}</span>
            </Link>
          ) : (
            <span className="flex items-center gap-1.5 text-foreground font-semibold">
              {item?.icon && <span className="hidden sm:inline">{item?.icon}</span>}
              <span>{item?.label}</span>
            </span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}

export default Breadcrumb;