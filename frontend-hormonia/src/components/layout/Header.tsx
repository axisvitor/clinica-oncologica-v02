import React, { useState } from 'react'
import { Search, User, LogOut, Settings, Menu, X } from 'lucide-react'
import { useAuth } from '@/app/providers/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { TaskHealthIndicator } from '../monitoring/TaskHealthIndicator'
import { NotificationCenter } from './NotificationCenter'
import { Breadcrumb } from './Breadcrumb'

interface HeaderProps {
  onMenuClick: () => void
}

export function Header({ onMenuClick }: HeaderProps) {
  const { user, logout, hasRole } = useAuth()
  const isAdmin = hasRole('admin')
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false)

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  return (
    <header className="bg-white border-b border-gray-200">
      {/* Main header row */}
      <div className="h-16 flex items-center justify-between px-4 md:px-6 gap-2 md:gap-4">
        {/* Mobile menu button */}
        <Button
          variant="ghost"
          size="sm"
          className="lg:hidden"
          onClick={onMenuClick}
          aria-label="Abrir menu"
        >
          <Menu className="h-5 w-5" />
        </Button>

        {/* Search - hidden on mobile, shown on md+ */}
        <div className="hidden md:flex flex-1 max-w-md">
          <div className="relative w-full">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              id="global-search-desktop"
              name="q"
              type="search"
              placeholder="Buscar pacientes, mensagens..."
              className="pl-10 bg-gray-50 border-gray-200"
            />
          </div>
        </div>

        {/* Mobile: Search icon to expand search */}
        <div className="flex-1 md:hidden flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            className="h-11 w-11"
            onClick={() => setMobileSearchOpen(true)}
            aria-label="Buscar"
          >
            <Search className="h-5 w-5" />
          </Button>
        </div>

        {/* Right side */}
        <div className="flex items-center space-x-2 md:space-x-4">
          {/* System Health - Admin only */}
          {isAdmin && <TaskHealthIndicator />}

          {/* Notifications */}
          <NotificationCenter />

          {/* User menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="relative h-8 w-8 rounded-full" aria-label="Menu do usuario">
                <Avatar className="h-8 w-8">
                  <AvatarImage src="" alt={user?.full_name} />
                  <AvatarFallback className="bg-blue-600 text-white">
                    {user?.full_name ? getInitials(user['full_name']) : 'U'}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="end" forceMount>
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium leading-none">
                    {user?.full_name}
                  </p>
                  <p className="text-xs leading-none text-muted-foreground">
                    {user?.email}
                  </p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem>
                <User className="mr-2 h-4 w-4" />
                <span>Perfil</span>
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Settings className="mr-2 h-4 w-4" />
                <span>Configurações</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={logout}>
                <LogOut className="mr-2 h-4 w-4" />
                <span>Sair</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Breadcrumb row - hidden on mobile */}
      <div className="hidden md:block px-4 md:px-6 py-2 md:py-3 bg-gray-50/50 border-t border-gray-100">
        <Breadcrumb
          className="flex"
          showIcons={true}
          showHome={true}
          maxItems={3}
        />
      </div>

      {/* Mobile Search Overlay */}
      {mobileSearchOpen && (
        <div className="md:hidden fixed inset-0 z-50 bg-white">
          <div className="flex items-center h-16 px-4 gap-2 border-b">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                id="global-search-mobile"
                name="q"
                type="search"
                placeholder="Buscar pacientes, mensagens..."
                className="pl-10 bg-gray-50 border-gray-200 h-11"
                autoFocus
              />
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-11 w-11 shrink-0"
              onClick={() => setMobileSearchOpen(false)}
              aria-label="Fechar"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>
          <div className="p-4">
            <p className="text-sm text-gray-500">Digite para buscar pacientes, mensagens ou relatórios...</p>
          </div>
        </div>
      )}
    </header>
  )
}
