import { Route, Routes } from 'react-router-dom'

import { Sidebar } from '@/components/layout/Sidebar'
import { OverviewPage } from '@/pages/OverviewPage'
import { RepositoriesPage } from '@/pages/RepositoriesPage'
import { RepositoryPage } from '@/pages/RepositoryPage'
import { QualityPage } from '@/pages/QualityPage'
import { ReleasesPage } from '@/pages/ReleasesPage'
import { ReviewDetailPage } from '@/pages/ReviewDetailPage'
import { ReviewSetupPage } from '@/pages/ReviewSetupPage'
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
            <Route path="/repositories" element={<RepositoriesPage />} />
            <Route path="/repositories/:projectId" element={<RepositoryPage />} />
            <Route path="/reviews" element={<ReviewsPage />} />
            <Route path="/reviews/new" element={<ReviewSetupPage />} />
            <Route path="/reviews/:reviewId" element={<ReviewDetailPage />} />
            <Route path="/quality" element={<QualityPage />} />
            <Route path="/releases" element={<ReleasesPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
