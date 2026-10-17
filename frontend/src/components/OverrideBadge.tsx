import React from 'react';
import { OverrideDiffBadge } from '../types/copilot';

export const OverrideBadge: React.FC<{ badge: OverrideDiffBadge }> = ({ badge }) => {
  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 shadow-xs">
      <span className="font-bold uppercase tracking-wider text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200">
        Override [{badge.target_id}]
      </span>
      <span>
        {badge.field_label}: <del className="text-slate-400 font-mono">{badge.old_value_display}</del>{' '}
        &rarr; <strong className="text-emerald-700 font-mono">{badge.new_value_display}</strong>
      </span>
      <span className="text-slate-500 text-[10px]">&bull; {badge.author_name}</span>
    </div>
  );
};
