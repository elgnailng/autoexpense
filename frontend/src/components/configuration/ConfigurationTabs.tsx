export type ConfigurationTab = 'keyword' | 'deduction' | 'categories' | 'history'

interface ConfigurationTabsProps {
  currentTab: ConfigurationTab
  onTabChange: (tab: ConfigurationTab) => void
}

const TAB_OPTIONS: Array<{ key: ConfigurationTab; label: string }> = [
  { key: 'keyword', label: 'Keyword Rules' },
  { key: 'deduction', label: 'Deduction Rules' },
  { key: 'categories', label: 'Categories' },
  { key: 'history', label: 'Change History' },
]

export default function ConfigurationTabs({ currentTab, onTabChange }: ConfigurationTabsProps) {
  return (
    <div className="flex gap-1 mb-6 bg-gray-900 rounded-lg p-1">
      {TAB_OPTIONS.map(({ key, label }) => (
        <button
          key={key}
          onClick={() => onTabChange(key)}
          className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
            currentTab === key
              ? 'bg-gray-700 text-white'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
