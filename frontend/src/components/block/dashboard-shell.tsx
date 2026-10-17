'use client';

import React, { useState, useEffect, ElementType, ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { LucideIcon, AlertTriangle } from 'lucide-react';

export interface DashboardShellNavItem {
  id: string;
  label: string;
  icon?: LucideIcon | ElementType;
  color?: string;
  count?: number;
  href?: string;
  badge?: string;
}

export interface DashboardShellNavSection {
  id: string;
  title?: string;
  items: DashboardShellNavItem[];
}

export interface DashboardShellProps {
  title?: ReactNode;
  headingLevel?: 1 | 2 | 3;
  status?: string;
  statusTone?: 'success' | 'warning' | 'neutral' | 'danger';
  navigation?: DashboardShellNavSection[];
  secondaryNavigation?: DashboardShellNavItem[];
  sidebarFooter?: ReactNode;
  activeItemId?: string;
  defaultActiveItemId?: string;
  onActiveItemChange?: (id: string) => void;
  headerActions?: ReactNode;
  tabs?: { value: string; label: string; icon?: LucideIcon | ElementType }[];
  tab?: string;
  defaultTab?: string;
  onTabChange?: (value: string) => void;
  filters?: ReactNode;
  toolbarActions?: ReactNode;
  children?: ReactNode;
  sidebarWidth?: number;
  defaultSidebarWidth?: number;
  onSidebarWidthChange?: (width: number) => void;
  minSidebarWidth?: number;
  maxSidebarWidth?: number;
  navigationLabel?: string;
  className?: string;
}

export const DashboardShell: React.FC<DashboardShellProps> = ({
  title = 'Asset Intelligence Copilot',
  status,
  statusTone = 'success',
  navigation = [],
  secondaryNavigation = [],
  sidebarFooter,
  activeItemId: controlledActiveId,
  defaultActiveItemId,
  onActiveItemChange,
  headerActions,
  tabs = [],
  tab: controlledTab,
  defaultTab,
  onTabChange,
  filters,
  toolbarActions,
  children,
  sidebarWidth: controlledWidth,
  defaultSidebarWidth = 240,
  onSidebarWidthChange,
  minSidebarWidth = 190,
  maxSidebarWidth = 380,
  className = '',
}) => {
  const [internalActiveId, setInternalActiveId] = useState<string>(
    defaultActiveItemId || navigation[0]?.items[0]?.id || ''
  );
  const activeId = controlledActiveId !== undefined ? controlledActiveId : internalActiveId;

  const [internalTab, setInternalTab] = useState<string>(defaultTab || tabs[0]?.value || '');
  const activeTab = controlledTab !== undefined ? controlledTab : internalTab;

  const [sidebarWidth, setSidebarWidth] = useState<number>(controlledWidth || defaultSidebarWidth);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);

  // Resize handler
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const newWidth = Math.max(minSidebarWidth, Math.min(e.clientX, maxSidebarWidth));
      setSidebarWidth(newWidth);
    };

    const handleMouseUp = () => {
      if (isDragging) {
        setIsDragging(false);
        onSidebarWidthChange?.(sidebarWidth);
      }
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, minSidebarWidth, maxSidebarWidth, onSidebarWidthChange, sidebarWidth]);

  const handleItemClick = (id: string) => {
    setInternalActiveId(id);
    onActiveItemChange?.(id);
  };

  const handleTabClick = (val: string) => {
    setInternalTab(val);
    onTabChange?.(val);
  };

  const statusToneColors = {
    success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    warning: 'bg-amber-50 text-amber-700 border-amber-200',
    neutral: 'bg-slate-100 text-slate-700 border-slate-200',
    danger: 'bg-rose-50 text-rose-700 border-rose-200',
  };

  return (
    <div className={`h-dvh flex flex-col bg-slate-50 text-slate-900 overflow-hidden font-sans ${className}`}>
      {/* Top Header */}
      <header className="h-14 border-b border-slate-200 bg-white px-4 flex items-center justify-between z-30 flex-shrink-0 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition"
            title="Toggle Sidebar"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {/* Clean Title Without Logo */}
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm tracking-tight text-slate-900">{title}</span>
          </div>

          {/* Status Pill */}
          {status && (
            <div
              className={`hidden sm:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-[11px] font-medium ${
                statusToneColors[statusTone]
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
              <span>{status}</span>
            </div>
          )}
        </div>

        {/* Right Header Actions */}
        {headerActions && <div className="flex items-center gap-2">{headerActions}</div>}
      </header>

      {/* Tabs Row with Sliding Pill */}
      {tabs.length > 0 && (
        <nav className="h-11 border-b border-slate-200 bg-white/95 px-4 flex items-center justify-between z-20 flex-shrink-0">
          <div className="flex items-center gap-1 p-0.5 rounded-lg bg-slate-100 border border-slate-200/80 text-xs relative">
            {tabs.map((t) => {
              const isActive = activeTab === t.value;
              const Icon = t.icon;
              return (
                <button
                  key={t.value}
                  onClick={() => handleTabClick(t.value)}
                  className={`relative px-3 py-1 rounded-md text-xs font-medium transition flex items-center gap-1.5 z-10 ${
                    isActive ? 'text-slate-900 font-semibold' : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {isActive && (
                    <motion.div
                      layoutId="active-tab-indicator"
                      className="absolute inset-0 bg-white border border-slate-200 shadow-sm rounded-md"
                      transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                    />
                  )}
                  {Icon && <Icon className="w-3.5 h-3.5 relative z-10 text-sky-600" />}
                  <span className="relative z-10">{t.label}</span>
                </button>
              );
            })}
          </div>

          {/* Toolbar Stats or Actions on the right of tabs */}
          {toolbarActions && <div className="flex items-center gap-2">{toolbarActions}</div>}
        </nav>
      )}

      {/* Sub-toolbar (Filters & Secondary Actions) */}
      {filters && (
        <div className="px-4 py-2 border-b border-slate-200 bg-white flex items-center justify-between text-xs z-10">
          <div className="flex items-center gap-2">{filters}</div>
        </div>
      )}

      {/* Main Shell Body */}
      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        {/* Resizable Sidebar */}
        <AnimatePresence initial={false}>
          {isSidebarOpen && (
            <aside
              style={{ width: `${sidebarWidth}px` }}
              className="border-r border-slate-200 bg-[#f8fafc] flex flex-col flex-shrink-0 relative z-10 overflow-hidden transition-[width] duration-75 select-none"
            >
              {/* Nav Items Scroll */}
              <div className="flex-1 overflow-y-auto p-3 space-y-4 text-xs">
                {navigation.map((sec) => (
                  <div key={sec.id} className="space-y-1">
                    {sec.title && (
                      <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 px-2 block mb-1">
                        {sec.title}
                      </span>
                    )}
                    <div className="space-y-0.5">
                      {sec.items.map((item) => {
                        const Icon = item.icon;
                        const isCurrent = activeId === item.id;
                        return (
                          <button
                            key={item.id}
                            onClick={() => handleItemClick(item.id)}
                            className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-left transition group ${
                              isCurrent
                                ? 'bg-white text-slate-900 font-semibold border border-slate-200 shadow-sm'
                                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
                            }`}
                          >
                            <span className="flex items-center gap-2 truncate">
                              {Icon && (
                                <Icon
                                  className={`w-4 h-4 flex-shrink-0 transition ${
                                    isCurrent ? 'text-sky-600' : 'text-slate-400 group-hover:text-slate-600'
                                  }`}
                                />
                              )}
                              {item.color && (
                                <span
                                  className="w-2 h-2 rounded-full flex-shrink-0"
                                  style={{ backgroundColor: item.color }}
                                />
                              )}
                              <span className="truncate">{item.label}</span>
                            </span>
                            {item.count !== undefined && (
                              <span className="text-[10px] font-mono text-slate-500 font-medium">{item.count}</span>
                            )}
                            {item.badge && (
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-sky-50 text-sky-700 border border-sky-200 font-medium">
                                {item.badge}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}

                {/* Secondary navigation if any */}
                {secondaryNavigation.length > 0 && (
                  <div className="pt-2 border-t border-slate-200 space-y-0.5">
                    {secondaryNavigation.map((item) => {
                      const Icon = item.icon;
                      return (
                        <button
                          key={item.id}
                          onClick={() => handleItemClick(item.id)}
                          className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-200/50 text-left transition"
                        >
                          <span className="flex items-center gap-2">
                            {Icon && <Icon className="w-4 h-4 text-slate-400" />}
                            <span>{item.label}</span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Sidebar Footer */}
              {sidebarFooter && (
                <div className="p-3 border-t border-slate-200 bg-white">{sidebarFooter}</div>
              )}

              {/* Resizer Handle */}
              <div
                onMouseDown={handleMouseDown}
                onDoubleClick={() => setSidebarWidth(defaultSidebarWidth)}
                className="absolute top-0 right-0 w-1.5 h-full cursor-col-resize hover:bg-sky-500 active:bg-sky-600 transition-colors z-20"
                title="Drag to resize, double click to reset"
              />
            </aside>
          )}
        </AnimatePresence>

        {/* Scrolling Page Content */}
        <main className="flex-1 flex flex-col min-w-0 bg-[#f8fafc] relative overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
};

/* Complementary Components */

export interface DashboardButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'muted' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'icon';
}

export const DashboardButton: React.FC<DashboardButtonProps> = ({
  children,
  variant = 'secondary',
  size = 'sm',
  className = '',
  ...props
}) => {
  const variantStyles = {
    primary: 'bg-slate-900 hover:bg-slate-800 text-white shadow-sm',
    secondary: 'bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-sm',
    muted: 'bg-slate-100 hover:bg-slate-200 text-slate-600 border border-slate-200',
    ghost: 'hover:bg-slate-100 text-slate-600 hover:text-slate-900',
    danger: 'bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200',
  };

  const sizeStyles = {
    sm: 'px-2.5 py-1 text-xs rounded-lg',
    md: 'px-3.5 py-2 text-sm rounded-lg',
    icon: 'p-1.5 rounded-lg',
  };

  return (
    <button
      className={`font-medium transition flex items-center justify-center gap-1.5 disabled:opacity-50 ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
};

export interface DashboardFilterMenuProps {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onValueChange: (val: string) => void;
}

export const DashboardFilterMenu: React.FC<DashboardFilterMenuProps> = ({
  label,
  value,
  options,
  onValueChange,
}) => {
  return (
    <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg px-2.5 py-1 text-xs shadow-sm">
      <span className="text-slate-500 text-[11px] font-medium">{label}:</span>
      <select
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        className="bg-transparent font-medium text-slate-800 outline-none cursor-pointer"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} className="bg-white text-slate-900">
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
};

export interface DashboardConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  tone?: 'danger' | 'neutral';
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
}

export const DashboardConfirmDialog: React.FC<DashboardConfirmDialogProps> = ({
  open,
  onOpenChange,
  title,
  description,
  tone = 'neutral',
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
}) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
      <div className="bg-white border border-slate-200 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
        <div className="flex items-center gap-3">
          <div
            className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm ${
              tone === 'danger'
                ? 'bg-rose-50 text-rose-600 border border-rose-200'
                : 'bg-sky-50 text-sky-600 border border-sky-200'
            }`}
          >
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 text-sm">{title}</h3>
            <p className="text-xs text-slate-500 mt-0.5">{description}</p>
          </div>
        </div>

        <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
          <DashboardButton variant="secondary" onClick={() => onOpenChange(false)}>
            {cancelLabel}
          </DashboardButton>
          <DashboardButton
            variant={tone === 'danger' ? 'danger' : 'primary'}
            onClick={() => {
              onConfirm();
              onOpenChange(false);
            }}
          >
            {confirmLabel}
          </DashboardButton>
        </div>
      </div>
    </div>
  );
};
