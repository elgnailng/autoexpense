import { useCategories } from '../hooks/useApi'

interface CategorySelectProps {
  value: string
  onChange: (value: string) => void
  className?: string
  disabled?: boolean
}

export default function CategorySelect({
  value,
  onChange,
  className = '',
  disabled = false,
}: CategorySelectProps) {
  const { data: categories, isLoading } = useCategories()

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={isLoading || disabled}
      className={`bg-gray-800 border border-gray-600 text-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
    >
      <option value="">Select category...</option>
      {categories?.map((cat) => (
        <option key={cat} value={cat}>
          {cat}
        </option>
      ))}
    </select>
  )
}
