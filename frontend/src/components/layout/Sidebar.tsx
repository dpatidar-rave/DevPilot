import {
  FileText,
  FolderGit2,
  GitPullRequest,
  LayoutDashboard,
  ShieldCheck,
  SlidersHorizontal,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

const items = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/repositories', label: 'Repositories', icon: FolderGit2, end: false },
  { to: '/reviews', label: 'Reviews', icon: GitPullRequest, end: false },
  { to: '/quality', label: 'Quality checks', icon: ShieldCheck, end: false },
  { to: '/releases', label: 'Release reports', icon: FileText, end: false },
  { to: '/settings', label: 'Settings', icon: SlidersHorizontal, end: false },
]

export function Sidebar() {
  return (
    <aside className="flex w-64 shrink-0 flex-col bg-sidebar text-sidebar-foreground">
      <div className="px-5 pb-4 pt-6">
        <p className="font-serif text-2xl tracking-tight">DevPilot</p>
        <p className="mt-1 text-xs text-sidebar-muted">Local review for this machine</p>
      </div>
      <ScrollArea className="flex-1 px-3">
        <nav aria-label="Primary" className="flex flex-col gap-1 pb-6">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                  isActive && 'bg-white/10 text-sidebar-foreground',
                )
              }
            >
              <item.icon aria-hidden="true" className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </ScrollArea>
      <p className="border-t border-white/10 px-5 py-4 text-xs leading-5 text-sidebar-muted">
        Source code, diffs, and review data stay on this machine.
      </p>
    </aside>
  )
}
