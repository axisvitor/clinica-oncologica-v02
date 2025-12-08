/**
 * Chart Skeleton Loader
 * 
 * Provides a loading placeholder for charts while lazy components load
 */
import React from 'react';

export function ChartSkeleton({ height = '300px' }: { height?: string }) {
  return (
    <div 
      className="w-full animate-pulse bg-gradient-to-r from-gray-100 via-gray-200 to-gray-100 bg-[length:200%_100%] rounded-lg"
      style={{ height }}
    >
      <div className="h-full flex items-center justify-center">
        <div className="space-y-4 w-full p-6">
          {/* Simulated chart bars */}
          <div className="flex items-end justify-around h-48 gap-2">
            <div className="bg-gray-300 rounded-t w-12 h-32"></div>
            <div className="bg-gray-300 rounded-t w-12 h-40"></div>
            <div className="bg-gray-300 rounded-t w-12 h-24"></div>
            <div className="bg-gray-300 rounded-t w-12 h-36"></div>
            <div className="bg-gray-300 rounded-t w-12 h-28"></div>
          </div>
          
          {/* Simulated axis */}
          <div className="border-t-2 border-gray-300"></div>
        </div>
      </div>
    </div>
  );
}
