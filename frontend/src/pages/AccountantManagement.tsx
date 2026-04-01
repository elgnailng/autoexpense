import { useState } from 'react'
import { useAccountants, useInviteAccountant, useUpdateAccountant, useRevokeAccountant } from '../hooks/useApi'

export default function AccountantManagement() {
  const { data: accountants, isLoading } = useAccountants()
  const inviteMutation = useInviteAccountant()
  const updateMutation = useUpdateAccountant()
  const revokeMutation = useRevokeAccountant()

  const [email, setEmail] = useState('')
  const [permission, setPermission] = useState('view')
  const [error, setError] = useState<string | null>(null)

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await inviteMutation.mutateAsync({ email: email.trim(), permission })
      setEmail('')
      setPermission('view')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to invite')
    }
  }

  const handleTogglePermission = async (acctEmail: string, currentPermission: string) => {
    const newPermission = currentPermission === 'view' ? 'view_flag' : 'view'
    try {
      await updateMutation.mutateAsync({ email: acctEmail, permission: newPermission })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update')
    }
  }

  const handleRevoke = async (acctEmail: string) => {
    if (!confirm(`Revoke access for ${acctEmail}?`)) return
    try {
      await revokeMutation.mutateAsync(acctEmail)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke')
    }
  }

  return (
    <div className="p-4 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Manage Accountants</h1>

      {/* Invite form */}
      <form onSubmit={handleInvite} className="mb-8 bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide mb-3">Invite Accountant</h2>
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="accountant@email.com"
            required
            className="flex-1 rounded-lg bg-gray-900 border border-gray-600 text-sm text-gray-200 px-3 py-2.5 focus:outline-none focus:border-blue-500"
          />
          <select
            value={permission}
            onChange={(e) => setPermission(e.target.value)}
            className="rounded-lg bg-gray-900 border border-gray-600 text-sm text-gray-200 px-3 py-2.5 focus:outline-none focus:border-blue-500"
          >
            <option value="view">View only</option>
            <option value="view_flag">View + Flag</option>
          </select>
          <button
            type="submit"
            disabled={inviteMutation.isPending || !email.trim()}
            className="rounded-lg px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white disabled:bg-blue-900 disabled:text-blue-400 transition-colors"
          >
            {inviteMutation.isPending ? 'Inviting...' : 'Invite'}
          </button>
        </div>
        {error && (
          <div className="mt-3 rounded-lg p-2.5 bg-red-900/30 border border-red-700 text-xs text-red-300">
            {error}
          </div>
        )}
      </form>

      {/* Accountant list */}
      <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide mb-3">Invited Accountants</h2>
      {isLoading ? (
        <div className="text-gray-500">Loading...</div>
      ) : !accountants || accountants.length === 0 ? (
        <div className="text-gray-500">No accountants invited yet.</div>
      ) : (
        <div className="space-y-3">
          {accountants.map((acct) => (
            <div
              key={acct.email}
              className={`bg-gray-800 rounded-lg p-4 border ${acct.status === 'revoked' ? 'border-red-900/50 opacity-60' : 'border-gray-700'}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-gray-200">{acct.email}</div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                    <span>Invited: {acct.invited_at ? new Date(acct.invited_at).toLocaleDateString() : 'N/A'}</span>
                    {acct.last_login && <span>Last login: {new Date(acct.last_login).toLocaleDateString()}</span>}
                    <span className={acct.status === 'active' ? 'text-green-400' : 'text-red-400'}>
                      {acct.status}
                    </span>
                  </div>
                </div>
                {acct.status === 'active' && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleTogglePermission(acct.email, acct.permission)}
                      disabled={updateMutation.isPending}
                      className="rounded-lg px-3 py-1.5 text-xs font-medium bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
                    >
                      {acct.permission === 'view' ? 'View only' : 'View + Flag'}
                    </button>
                    <button
                      onClick={() => handleRevoke(acct.email)}
                      disabled={revokeMutation.isPending}
                      className="rounded-lg px-3 py-1.5 text-xs font-medium bg-red-900/50 hover:bg-red-800/50 text-red-400 border border-red-800 transition-colors"
                    >
                      Revoke
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
