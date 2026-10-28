import { Route, Routes } from 'react-router-dom'

import { Sidebar } from '@/components/layout/Sidebar'
import { OverviewPage } from '@/pages/OverviewPage'
import { QualityPage } from '@/pages/QualityPage'
import { ReleasesPage } from '@/pages/ReleasesPage'
import { ReviewsPage } from '@/pages/ReviewsPage'
import { SettingsPage } from '@/pages/SettingsPage'

export function AppShell() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-5xl px-8 py-8">
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/reviews" element={<ReviewsPage />} />
            <Route path="/quality" element={<QualityPage />} />
            <Route path="/releases" element={<ReleasesPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
