import { useState } from 'react'
import ChangeHistorySection from '../components/configuration/ChangeHistorySection'
import ConfigurationTabs, { type ConfigurationTab } from '../components/configuration/ConfigurationTabs'
import CategoriesSection from '../components/configuration/CategoriesSection'
import DeductionRulesSection from '../components/configuration/DeductionRulesSection'
import KeywordRulesSection from '../components/configuration/KeywordRulesSection'
import { useStatus } from '../hooks/useApi'

export default function Configuration() {
  const [tab, setTab] = useState<ConfigurationTab>('keyword')
  const { data: status } = useStatus()
  const pipelineRunning = status?.pipeline_running ?? false

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Configuration</h1>

      {pipelineRunning && (
        <div className="mb-4 rounded-lg border border-yellow-700 bg-yellow-900/20 p-3 text-sm text-yellow-300 flex items-center gap-2">
          <span className="inline-block w-4 h-4 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
          Configuration is locked while a pipeline step is running.
        </div>
      )}

      <ConfigurationTabs currentTab={tab} onTabChange={setTab} />

      {tab === 'keyword' && <KeywordRulesSection locked={pipelineRunning} />}
      {tab === 'deduction' && <DeductionRulesSection locked={pipelineRunning} />}
      {tab === 'categories' && <CategoriesSection />}
      {tab === 'history' && <ChangeHistorySection />}
    </div>
  )
}
