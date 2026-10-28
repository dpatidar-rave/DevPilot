import { BrowserRouter } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'

export function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
