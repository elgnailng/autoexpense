import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import OwnerOnly from './components/OwnerOnly'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Transactions from './pages/Transactions'
import ReviewQueue from './pages/ReviewQueue'
import Pipeline from './pages/Pipeline'
import Configuration from './pages/Configuration'
import AccountantManagement from './pages/AccountantManagement'
import AccountantExport from './pages/AccountantExport'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <QueryClientProvider client={queryClient}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<Dashboard />} />
                <Route path="/transactions" element={<Transactions />} />
                <Route path="/review" element={<OwnerOnly><ReviewQueue /></OwnerOnly>} />
                <Route path="/pipeline" element={<OwnerOnly><Pipeline /></OwnerOnly>} />
                <Route path="/config" element={<OwnerOnly><Configuration /></OwnerOnly>} />
                <Route path="/accountants" element={<OwnerOnly><AccountantManagement /></OwnerOnly>} />
                <Route path="/export" element={<AccountantExport />} />
              </Route>
            </Route>
          </Routes>
        </QueryClientProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
