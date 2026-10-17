import React from 'react';
import { ConflictAlertCard } from '../types/copilot';

export const ConflictCard: React.FC<{ conflict: ConflictAlertCard }> = ({ conflict }) => {
  return (
    <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-4 text-xs text-amber-950 space-y-2.5 shadow-sm">
      <div className="flex items-center justify-between font-semibold text-amber-900">
        <div className="flex items-center gap-2">
          <span className="px-1.5 py-0.5 rounded bg-amber-100 text-[10px] tracking-wide uppercase border border-amber-300 font-bold text-amber-800">
            {conflict.severity}
          </span>
          <span className="text-sm font-semibold">{conflict.title}</span>
        </div>
        <span className="text-[10px] text-amber-700 font-normal">Audit Contradiction Flag</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] pt-1.5 border-t border-amber-200">
        <div className="bg-white p-2.5 rounded-lg border border-amber-200/60 space-y-1 shadow-xs">
          <strong className="text-amber-900 block font-medium">Claim ({conflict.claim_a_source}):</strong>
          <span className="text-slate-700 italic">&ldquo;{conflict.claim_a_text}&rdquo;</span>
        </div>
        <div className="bg-white p-2.5 rounded-lg border border-amber-200/60 space-y-1 shadow-xs">
          <strong className="text-amber-900 block font-medium">Telemetry Evidence ({conflict.claim_b_source}):</strong>
          <span className="text-slate-700">{conflict.claim_b_text}</span>
        </div>
      </div>

      <div className="text-[11px] text-amber-900 pt-1 font-medium bg-amber-100/60 p-2.5 rounded-lg border border-amber-200">
        <strong>Resolution:</strong> {conflict.resolution_summary}
      </div>
    </div>
  );
};
