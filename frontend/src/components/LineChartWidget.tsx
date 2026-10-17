import React from 'react';
import { LineChartSpec } from '../types/copilot';

export const LineChartWidget: React.FC<{ spec: LineChartSpec }> = ({ spec }) => {
  const data = spec.data_points || [];
  if (data.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-4 text-xs text-slate-500 shadow-sm">
        No temperature data available.
      </div>
    );
  }

  const maxTemp = Math.max(...data.map(d => Math.max(d.wellhead_temp_c || 0, d.ambient_temp_c || 0, d.temp_delta_c || 0)), 45);
  const minTemp = Math.min(...data.map(d => Math.min(d.wellhead_temp_c || 0, d.ambient_temp_c || 0, d.temp_delta_c || 0)), 0);
  const range = maxTemp - minTemp || 1;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <div>
          <h4 className="font-semibold text-xs text-slate-900 uppercase tracking-wider">{spec.title}</h4>
          {spec.subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{spec.subtitle}</p>}
        </div>
        <span className="text-[10px] text-slate-600 font-mono bg-slate-100 px-2 py-0.5 rounded border border-slate-200 font-medium">
          13 Weeks &bull; Limit: {spec.threshold_line?.value || 15}&deg;C
        </span>
      </div>

      {/* SVG Line Chart Visualizer */}
      <div className="h-56 relative w-full border border-slate-100 rounded-lg p-2 bg-slate-50/60">
        <svg className="w-full h-full overflow-visible" viewBox="0 0 500 200" preserveAspectRatio="none">
          {/* Threshold line */}
          {spec.threshold_line && (
            <line
              x1="0"
              y1={200 - (((spec.threshold_line.value || 15) - minTemp) / range) * 200}
              x2="500"
              y2={200 - (((spec.threshold_line.value || 15) - minTemp) / range) * 200}
              stroke="#ef4444"
              strokeDasharray="4 4"
              strokeWidth="1.5"
            />
          )}

          {/* Wellhead Temperature Line (Sky Blue) */}
          <polyline
            fill="none"
            stroke="#0284c7"
            strokeWidth="2.5"
            points={data.map((d, i) => {
              const x = (i / Math.max(data.length - 1, 1)) * 500;
              const y = 200 - (((d.wellhead_temp_c || 0) - minTemp) / range) * 200;
              return `${x},${y}`;
            }).join(' ')}
          />

          {/* Ambient Temperature Line (Slate Gray) */}
          <polyline
            fill="none"
            stroke="#94a3b8"
            strokeDasharray="3 3"
            strokeWidth="1.5"
            points={data.map((d, i) => {
              const x = (i / Math.max(data.length - 1, 1)) * 500;
              const y = 200 - (((d.ambient_temp_c || 0) - minTemp) / range) * 200;
              return `${x},${y}`;
            }).join(' ')}
          />

          {/* Delta Temperature Line (Amber) */}
          <polyline
            fill="none"
            stroke="#d97706"
            strokeWidth="2"
            points={data.map((d, i) => {
              const x = (i / Math.max(data.length - 1, 1)) * 500;
              const y = 200 - (((d.temp_delta_c || 0) - minTemp) / range) * 200;
              return `${x},${y}`;
            }).join(' ')}
          />

          {/* Data Points & Non-producing Markers */}
          {data.map((d, i) => {
            const x = (i / Math.max(data.length - 1, 1)) * 500;
            const y = 200 - (((d.temp_delta_c || 0) - minTemp) / range) * 200;
            const dateStr = d.date_str || (d as any).inspection_date || '';
            const isNonProducing = (spec.non_producing_markers || []).includes(dateStr);

            return (
              <g key={i}>
                <circle
                  cx={x}
                  cy={y}
                  r={isNonProducing ? 5 : 3.5}
                  fill={isNonProducing ? '#ef4444' : '#d97706'}
                  stroke="#ffffff"
                  strokeWidth="1.5"
                />
                {isNonProducing && (
                  <text x={x} y={y - 8} fill="#ef4444" fontSize="9" textAnchor="middle" fontWeight="bold">
                    OFFLINE
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center justify-center gap-5 text-[11px] text-slate-600 pt-1">
        <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-sky-600"></span> Wellhead Temp</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-slate-400 border-dashed"></span> Ambient Temp</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-amber-600"></span> Delta T</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-red-500 border-dashed"></span> Threshold (15&deg;C)</span>
      </div>
    </div>
  );
};
