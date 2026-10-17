import React from 'react';
import { StatusCardSpec } from '../types/copilot';

export const StatusCardWidget: React.FC<{ spec: StatusCardSpec }> = ({ spec }) => {
  const isProducing = spec.is_producing;
  const wellhead = spec.wellhead_temp_c ?? spec.effective_wellhead_temp_c ?? 0;
  const ambient = spec.ambient_temp_c ?? spec.effective_ambient_temp_c ?? 0;
  const delta = spec.temp_delta_c ?? spec.effective_temp_delta_c ?? (wellhead - ambient);
  const recordedStatus = spec.recorded_status_display ?? spec.recorded_status ?? 'UNKNOWN';

  return (
    <div className={`bg-white border ${isProducing ? 'border-emerald-200 shadow-emerald-500/5' : 'border-rose-200 shadow-rose-500/5'} rounded-xl p-4 md:p-5 shadow-sm space-y-4`}>
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div>
          <h3 className="text-sm md:text-base font-semibold text-slate-900 flex items-center gap-2">
            {spec.well_name}
            <span className="text-xs font-mono text-slate-500">({spec.asset_id})</span>
            <span className="text-[11px] px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-normal border border-slate-200">
              {spec.well_type}
            </span>
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">{spec.area_name}</p>
        </div>
        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide ${
          isProducing
            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
            : 'bg-rose-50 text-rose-700 border border-rose-200'
        }`}>
          {spec.status_badge_label}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1 font-medium">Wellhead Temp</span>
          <span className="text-base md:text-lg font-bold text-slate-900 font-mono">{Number(wellhead).toFixed(1)} &deg;C</span>
        </div>
        <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1 font-medium">Ambient Temp</span>
          <span className="text-base md:text-lg font-bold text-slate-900 font-mono">{Number(ambient).toFixed(1)} &deg;C</span>
        </div>
        <div className={`bg-slate-50 p-3 rounded-lg border border-slate-100 ${isProducing ? 'text-emerald-700' : 'text-rose-700'}`}>
          <span className="text-[10px] uppercase tracking-wider block mb-1 font-medium">Delta T (&ge;{spec.required_temp_delta_c}&deg;C)</span>
          <span className="text-base md:text-lg font-bold font-mono">{Number(delta).toFixed(1)} &deg;C</span>
        </div>
      </div>

      <div className="space-y-2 text-xs">
        {spec.is_recorded_status_stale && (
          <div className="px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-900">
            <strong>Status Stale:</strong> Master database still records <code className="text-amber-800 font-mono font-semibold">{recordedStatus}</code>, but sensor telemetry proves well is stopped.
          </div>
        )}
        {spec.stop_reason_summary && (
          <div className="px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-slate-700">
            <strong className="text-slate-900">Operating Reason:</strong> {spec.stop_reason_summary}
          </div>
        )}
      </div>

      <div className="text-[11px] text-slate-500 pt-2 border-t border-slate-100 flex items-center justify-between">
        <span>Last Inspected: {spec.latest_inspection_date || 'N/A'} ({spec.latest_inspection_id || 'N/A'})</span>
        <span>Inspector: {spec.inspector_name || 'N/A'}</span>
      </div>
    </div>
  );
};
