import React from 'react';
import { TableSpec } from '../types/copilot';

export const TableWidget: React.FC<{ spec: TableSpec }> = ({ spec }) => {
  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
        <div>
          <h4 className="font-semibold text-xs text-slate-900 uppercase tracking-wider">{spec.title}</h4>
          {spec.subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{spec.subtitle}</p>}
        </div>
        <span className="text-[10px] text-slate-500 font-mono bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
          {spec.rows.length} Rows
        </span>
      </div>
      <div className="overflow-x-auto max-h-80">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200 sticky top-0 backdrop-blur z-10">
            <tr>
              {spec.columns.map((c) => (
                <th key={c.key} className={`px-3 py-2.5 text-${c.align || 'left'} tracking-wide`}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {spec.rows.map((row, idx) => (
              <tr key={idx} className="hover:bg-slate-50/80 transition">
                {spec.columns.map((c) => (
                  <td key={c.key} className={`px-3 py-2 font-mono text-slate-800 text-${c.align || 'left'}`}>
                    {String(row[c.key] ?? '-')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {spec.footer_summary && (
        <div className="px-4 py-2 border-t border-slate-100 bg-slate-50/50 text-[11px] text-slate-500 text-right font-medium">
          {spec.footer_summary}
        </div>
      )}
    </div>
  );
};
