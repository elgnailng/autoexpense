import { useCategories } from '../../hooks/useApi'

export default function CategoriesSection() {
  const { data: categories, isLoading } = useCategories()

  if (isLoading) return <div className="text-gray-500">Loading categories...</div>

  return (
    <div>
      <div className="bg-blue-900/30 border border-blue-800 rounded-lg p-3 mb-4 text-sm text-blue-300">
        These categories match the CRA T2125 form exactly, including intentional spelling.
        They cannot be modified.
      </div>
      <div className="space-y-1">
        {categories?.map((category) => (
          <div
            key={category}
            className="bg-gray-800 rounded-lg px-4 py-2.5 border border-gray-700 text-sm text-gray-200"
          >
            {category}
          </div>
        ))}
      </div>
    </div>
  )
}
