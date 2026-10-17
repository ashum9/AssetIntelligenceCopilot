import React from 'react';
import { MapSpec } from '../types/copilot';

export const MapWidget: React.FC<{ spec: MapSpec }> = ({ spec }) => {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <div>
          <h4 className="font-semibold text-xs text-slate-900 uppercase tracking-wider">{spec.title}</h4>
          {spec.subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{spec.subtitle}</p>}
        </div>
        <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-medium">
          {spec.pins.length} Verified Spills
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
        {spec.pins.map((pin) => (
          <div key={pin.asset_id} className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-1.5 hover:border-slate-300 transition">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-900 text-xs font-mono">{pin.asset_id}</span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  pin.badge_color === 'red'
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : pin.badge_color === 'orange'
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-yellow-50 text-yellow-700 border border-yellow-200'
                }`}
              >
                {pin.volume_bbl} bbl
              </span>
            </div>
            <div className="text-[11px] text-slate-600">Date: {pin.date_str}</div>
            <div className="text-[10px] text-slate-500 font-mono">
              Coord: {Number(pin.lat || 0).toFixed(4)}, {Number(pin.lon || 0).toFixed(4)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
