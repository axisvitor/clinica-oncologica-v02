import * as React from "react"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Avatar } from "@/components/ui/avatar"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

// Base Skeleton Component
interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'card' | 'table' | 'list' | 'form' | 'chart'
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl'
  shape?: 'rectangular' | 'circular' | 'rounded' | 'pill'
  animation?: 'pulse' | 'wave' | 'shimmer' | 'breathing' | 'none'
  intensity?: 'subtle' | 'normal' | 'strong'
}

function Skeleton({
  className,
  variant = 'default',
  size = 'md',
  shape = 'rectangular',
  animation = 'pulse',
  intensity = 'normal',
  ...props
}: SkeletonProps) {
  const baseClasses = "bg-muted"

  const sizeClasses = {
    xs: "h-3",
    sm: "h-4",
    md: "h-6",
    lg: "h-8",
    xl: "h-12",
    "2xl": "h-16"
  }

  const shapeClasses = {
    rectangular: "rounded-none",
    circular: "rounded-full",
    rounded: "rounded-md",
    pill: "rounded-full"
  }

  const animationClasses = {
    pulse: "animate-pulse motion-reduce:animate-none",
    wave: "animate-skeleton-wave motion-reduce:animate-none relative overflow-hidden bg-gradient-to-r from-muted via-muted/50 to-muted bg-[length:200%_100%]",
    shimmer: "animate-shimmer motion-reduce:animate-none bg-gradient-to-r from-muted via-muted/50 to-muted bg-[length:200%_100%]",
    breathing: "animate-breathing motion-reduce:animate-none",
    none: ""
  }

  const intensityClasses = {
    subtle: "opacity-60",
    normal: "opacity-80",
    strong: "opacity-100"
  }

  return (
    <div
      className={cn(
        baseClasses,
        sizeClasses[size],
        shapeClasses[shape],
        animationClasses[animation],
        intensityClasses[intensity],
        className
      )}
      {...props}
    />
  )
}

// Text Skeleton
interface TextSkeletonProps {
  lines?: number
  className?: string
  size?: 'sm' | 'md' | 'lg'
  animation?: 'pulse' | 'wave' | 'shimmer'
}

function TextSkeleton({
  lines = 1,
  className,
  size = 'md',
  animation = 'shimmer'
}: TextSkeletonProps) {
  const heights = {
    sm: 'h-3',
    md: 'h-4',
    lg: 'h-5'
  }

  const widths = ['w-full', 'w-5/6', 'w-4/5', 'w-3/4', 'w-2/3']

  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton
          key={index}
          className={cn(
            heights[size],
            index === lines - 1 && lines > 1 ? widths[index % widths.length] : 'w-full'
          )}
          animation={animation}
          shape="rounded"
        />
      ))}
    </div>
  )
}

// Avatar Skeleton
function AvatarSkeleton({
  size = 'md',
  className
}: {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
}) {
  const sizes = {
    sm: 'h-6 w-6',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
    xl: 'h-16 w-16'
  }

  return (
    <Skeleton
      className={cn(sizes[size], className)}
      shape="circular"
      animation="shimmer"
    />
  )
}

// Button Skeleton
function ButtonSkeleton({
  size = 'md',
  variant = 'default',
  className
}: {
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'outline' | 'ghost'
  className?: string
}) {
  const sizes = {
    sm: 'h-8 w-16',
    md: 'h-10 w-20',
    lg: 'h-12 w-24'
  }

  const variants = {
    default: 'bg-muted',
    outline: 'bg-muted border border-muted-foreground/20',
    ghost: 'bg-muted/50'
  }

  return (
    <div
      className={cn(
        'rounded-md',
        sizes[size],
        variants[variant],
        'animate-pulse',
        className
      )}
    />
  )
}

// Badge Skeleton
function BadgeSkeleton({ className }: { className?: string }) {
  return (
    <Skeleton
      className={cn("h-5 w-16 rounded-full", className)}
      animation="shimmer"
    />
  )
}

// Patient Card Skeleton
function PatientCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("hover:shadow-md transition-shadow", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <AvatarSkeleton size="lg" />
            <div className="space-y-2">
              <Skeleton className="h-5 w-32" animation="shimmer" shape="rounded" />
              <Skeleton className="h-4 w-24" animation="shimmer" shape="rounded" />
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <BadgeSkeleton />
            <Skeleton className="h-8 w-8" shape="rounded" animation="pulse" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center space-x-2">
          <Skeleton className="h-3 w-3" shape="rounded" />
          <Skeleton className="h-4 w-40" shape="rounded" animation="shimmer" />
        </div>

        <div className="flex items-center space-x-2">
          <Skeleton className="h-3 w-3" shape="rounded" />
          <Skeleton className="h-4 w-28" shape="rounded" animation="shimmer" />
        </div>

        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-20" shape="rounded" />
          <Skeleton className="h-4 w-8" shape="rounded" animation="shimmer" />
        </div>

        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-24" shape="rounded" />
          <Skeleton className="h-4 w-16" shape="rounded" animation="shimmer" />
        </div>

        <div className="flex space-x-2 pt-2">
          <ButtonSkeleton size="sm" className="flex-1" />
          <ButtonSkeleton size="sm" className="flex-1" />
        </div>
      </CardContent>
    </Card>
  )
}

// Table Skeleton
interface TableSkeletonProps {
  rows?: number
  columns?: number
  showHeader?: boolean
  className?: string
}

function TableSkeleton({
  rows = 5,
  columns = 6,
  showHeader = true,
  className
}: TableSkeletonProps) {
  const columnWidths = ['w-48', 'w-32', 'w-24', 'w-20', 'w-28', 'w-16']

  return (
    <div className={cn("space-y-4", className)}>
      <Table>
        {showHeader && (
          <TableHeader>
            <TableRow>
              {Array.from({ length: columns }).map((_, index) => (
                <TableHead key={index}>
                  <Skeleton
                    className="h-4 w-20"
                    shape="rounded"
                    animation="shimmer"
                  />
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
        )}
        <TableBody>
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <TableRow key={rowIndex}>
              {Array.from({ length: columns }).map((_, colIndex) => (
                <TableCell key={colIndex}>
                  {colIndex === 0 ? (
                    // First column with avatar and name
                    <div className="flex items-center space-x-3">
                      <AvatarSkeleton size="sm" />
                      <div className="space-y-1">
                        <Skeleton className="h-4 w-32" shape="rounded" animation="shimmer" />
                        <Skeleton className="h-3 w-24" shape="rounded" animation="shimmer" />
                      </div>
                    </div>
                  ) : colIndex === columns - 1 ? (
                    // Last column (actions)
                    <Skeleton className="h-8 w-8" shape="rounded" />
                  ) : colIndex === 3 ? (
                    // Status column with badge
                    <BadgeSkeleton />
                  ) : (
                    // Regular content
                    <Skeleton
                      className={cn(
                        "h-4",
                        columnWidths[colIndex] || "w-20"
                      )}
                      shape="rounded"
                      animation="shimmer"
                    />
                  )}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

// List Skeleton
interface ListSkeletonProps {
  items?: number
  showAvatar?: boolean
  showBadge?: boolean
  className?: string
}

function ListSkeleton({
  items = 5,
  showAvatar = true,
  showBadge = false,
  className
}: ListSkeletonProps) {
  return (
    <div className={cn("space-y-4", className)}>
      {Array.from({ length: items }).map((_, index) => (
        <div key={index} className="flex items-center space-x-4 p-4 rounded-lg border">
          {showAvatar && <AvatarSkeleton size="md" />}
          <div className="flex-1 space-y-2">
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-48" shape="rounded" animation="shimmer" />
              {showBadge && <BadgeSkeleton />}
            </div>
            <Skeleton className="h-4 w-64" shape="rounded" animation="shimmer" />
            <Skeleton className="h-3 w-32" shape="rounded" animation="shimmer" />
          </div>
          <div className="flex space-x-2">
            <ButtonSkeleton size="sm" />
            <Skeleton className="h-8 w-8" shape="rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}

// Patient List Skeleton (specific for patient lists)
function PatientListSkeleton({
  items = 8,
  className
}: {
  items?: number
  className?: string
}) {
  return (
    <div className={cn("grid gap-6 md:grid-cols-2 lg:grid-cols-3", className)}>
      {Array.from({ length: items }).map((_, index) => (
        <PatientCardSkeleton key={index} />
      ))}
    </div>
  )
}

// Metric Card Skeleton
function MetricCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-4 w-24" shape="rounded" animation="shimmer" />
            <Skeleton className="h-8 w-16" shape="rounded" animation="shimmer" />
          </div>
          <Skeleton className="h-8 w-8" shape="rounded" />
        </div>
        <div className="mt-4">
          <Skeleton className="h-3 w-32" shape="rounded" animation="shimmer" />
        </div>
      </CardContent>
    </Card>
  )
}

export {
  Skeleton,
  TextSkeleton,
  AvatarSkeleton,
  ButtonSkeleton,
  BadgeSkeleton,
  PatientCardSkeleton,
  TableSkeleton,
  ListSkeleton,
  PatientListSkeleton,
  MetricCardSkeleton
}