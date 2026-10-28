import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ConnectionError } from '@/components/ConnectionError'
import { PageHeader } from '@/components/PageHeader'
import { ReleaseReportView } from '@/components/ReleaseReportView'
import { Button } from '@/components/ui/button'
import { downloadReleaseExport, readReleaseReport, type ReleaseReportDetail } from '@/services/api'

export function ReleaseDetailPage() {
  const { reportId = '' } = useParams()
  const [report, setReport] = useState<ReleaseReportDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    readReleaseReport(reportId)
      .then((next) => {
        if (!cancelled) {
          setReport(next)
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : 'The release report could not be read.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [reportId])

  return (
    <>
      <PageHeader
        phase="Phase 4"
        title={report?.title ?? 'Release report'}
        description="This stored snapshot does not approve the release. A technical lead uses the readiness, blockers, warnings, and waivers to decide."
      />
      {error && <ConnectionError message={error} onRetry={() => window.location.reload()} />}
      {report && (
        <>
          <p className="mb-4 text-sm text-muted-foreground">Stored as {report.status}.</p>
          <div className="mb-6 flex gap-3">
            <Button type="button" variant="outline" onClick={() => void downloadReleaseExport(report.id, 'markdown')}>
              Download Markdown
            </Button>
            <Button type="button" variant="outline" onClick={() => void downloadReleaseExport(report.id, 'json')}>
              Download JSON
            </Button>
          </div>
          <ReleaseReportView report={report} />
        </>
      )}
      <p className="mt-6 text-sm">
        <Link to="/releases" className="underline">
          Back to release reports
        </Link>
      </p>
    </>
  )
}
