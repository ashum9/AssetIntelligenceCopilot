import React from 'react';
import { BarChartSpec } from '../types/copilot';

export const BarChartWidget: React.FC<{ spec: BarChartSpec }> = ({ spec }) => {
  const bars = spec.bars || [];
  const maxValue = Math.max(...bars.map(b => b.value || 0), 10);

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <div>
          <h4 className="font-semibold text-xs text-slate-900 uppercase tracking-wider">{spec.title}</h4>
          {spec.subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{spec.subtitle}</p>}
        </div>
        <span className="text-[10px] text-slate-600 font-mono bg-slate-100 px-2 py-0.5 rounded border border-slate-200 font-medium">
          Downtime Ranking
        </span>
      </div>

      <div className="space-y-3 pt-1">
        {bars.map((bar, idx) => {
          const pct = Math.min(Math.round((bar.value / maxValue) * 100), 100);
          const colors = ['bg-rose-500', 'bg-amber-500', 'bg-amber-600', 'bg-sky-500'];
          const barColor = colors[idx % colors.length];

          return (
            <div key={bar.asset_id} className="space-y-1">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-slate-900 font-medium flex items-center gap-2">
                  <span className="text-sky-700 font-bold">{bar.asset_id}</span>
                  <span className="text-[10px] text-slate-500 font-normal px-1.5 py-0.2 rounded bg-slate-100 border border-slate-200">
                    {bar.category}
                  </span>
                </span>
                <span className="text-amber-700 font-bold">{bar.value} days</span>
              </div>
              <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200">
                <div
                  className={`h-full ${barColor} rounded-full transition-all duration-500`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
