import React from 'react';
import { HeatmapSpec } from '../types/copilot';

export const HeatmapWidget: React.FC<{ spec: HeatmapSpec }> = ({ spec }) => {
  const getCellClass = (val: number) => {
    if (val === 0) return 'bg-slate-50 text-slate-400 border border-slate-100';
    if (val <= 2) return 'bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold';
    if (val <= 4) return 'bg-emerald-100 text-emerald-900 border border-emerald-300 font-bold';
    if (val <= 5) return 'bg-emerald-200 text-emerald-950 border border-emerald-400 font-bold';
    if (val <= 6) return 'bg-amber-100 text-amber-900 border border-amber-300 font-bold';
    return 'bg-rose-100 text-rose-900 border border-rose-300 font-bold';
  };

  const columns = spec.x_labels || spec.columns || [];
  const rows = spec.y_labels || spec.rows || [];
  const matrix = spec.matrix || spec.data || [];
  const rowTotals = spec.row_totals || [];

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm space-y-1">
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
        <div>
          <h4 className="font-semibold text-xs text-slate-900 uppercase tracking-wider">{spec.title}</h4>
          {spec.subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{spec.subtitle}</p>}
        </div>
        <span className="text-xs font-semibold text-emerald-700 font-mono bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
          Total: {spec.grand_total} Spills
        </span>
      </div>

      <div className="overflow-x-auto p-4">
        <table className="w-full text-center text-xs border-collapse">
          <thead>
            <tr className="text-slate-500 text-[11px] border-b border-slate-200">
              <th className="text-left py-2 px-3 font-semibold">Area</th>
              {columns.map((col, idx) => (
                <th key={col || idx} className="py-2 px-1 font-mono font-semibold">
                  {col}
                </th>
              ))}
              <th className="py-2 px-3 font-bold text-slate-900">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((rowName, rIdx) => {
              const rowData = matrix[rIdx] || [];
              const total = rowTotals[rIdx] ?? rowData.reduce((acc, curr) => acc + curr, 0);

              return (
                <tr key={rowName || rIdx} className="border-t border-slate-100 hover:bg-slate-50/60 transition">
                  <td className="text-left font-medium text-slate-800 py-2 px-3 text-[11px] whitespace-nowrap">
                    {rowName}
                  </td>
                  {rowData.map((val, cIdx) => (
                    <td key={cIdx} className="p-1">
                      <span
                        className={`inline-block w-7 h-7 leading-7 rounded-md font-mono text-[11px] ${getCellClass(
                          val
                        )}`}
                      >
                        {val}
                      </span>
                    </td>
                  ))}
                  <td className="font-bold text-sky-700 py-2 px-3 font-mono">
                    {total}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {spec.note && (
        <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-100 text-[11px] text-slate-600">
          {spec.note}
        </div>
      )}
    </div>
  );
};
