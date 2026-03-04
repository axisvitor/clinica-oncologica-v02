import React from 'react'

export const HealthStatusMonitor: React.FC = () => {
  return (
    <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
      <div className="flex items-center space-x-2">
        <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
        <span className="text-sm font-medium text-gray-700">System Operational</span>
      </div>
    </div>
  )
}
