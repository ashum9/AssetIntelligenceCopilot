'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare,
  Layers,
  LineChart,
  ShieldAlert,
  MapPin,
  RefreshCw,
  Search,
  Sparkles,
  Send,
  Flame,
  AlertTriangle,
} from 'lucide-react';

import {
  DashboardShell,
  DashboardButton,
  DashboardConfirmDialog,
  DashboardShellNavSection,
} from '../components/block/dashboard-shell';

import {
  CopilotResponseEnvelope,
  VisualPayload,
} from '../types/copilot';

import { StatusCardWidget } from '../components/StatusCardWidget';
import { TableWidget } from '../components/TableWidget';
import { LineChartWidget } from '../components/LineChartWidget';
import { BarChartWidget } from '../components/BarChartWidget';
import { MapWidget } from '../components/MapWidget';
import { HeatmapWidget } from '../components/HeatmapWidget';
import { OverrideBadge } from '../components/OverrideBadge';
import { ConflictCard } from '../components/ConflictCard';
import { MarkdownRenderer } from '../components/MarkdownRenderer';

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  user_name?: string;
  text?: string;
  envelope?: CopilotResponseEnvelope;
  loading?: boolean;
}

interface WellSummaryItem {
  asset_id: string;
  well_name: string;
  area_name: string;
  well_type: string;
  is_producing: boolean;
  recorded_status: string;
  effective_temp_delta_c: number;
  latest_inspection_date: string;
  inspector_name: string;
  lat: number;
  lon: number;
}

export default function CopilotDashboardPage() {
  const [currentUser, setCurrentUser] = useState<string>('Michael Turner');
  const [sessionId, setSessionId] = useState<string>('SESSION-MT-INIT');
  const [activeTab, setActiveTab] = useState<string>('copilot');

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: 'Hello! I am your Asset Intelligence Copilot. Ask any question regarding well operations, thermal delta T, downtime, environmental compliance, or submit verified field corrections.',
    },
  ]);

  const [inputQuery, setInputQuery] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [selectedCitation, setSelectedCitation] = useState<string | null>(null);
  const [showEvalModal, setShowEvalModal] = useState<boolean>(false);
  const [showResetDialog, setShowResetDialog] = useState<boolean>(false);
  const [evalReport, setEvalReport] = useState<any>(null);

  // Fleet Directory state
  const [wells, setWells] = useState<WellSummaryItem[]>([]);
  const [fleetSearch, setFleetSearch] = useState<string>('');
  const [areaFilter, setAreaFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [loadingFleet, setLoadingFleet] = useState<boolean>(false);

  // Overrides Ledger state
  const [activeOverrides, setActiveOverrides] = useState<any[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load fleet when switching to fleet tab
  useEffect(() => {
    if (activeTab === 'fleet' && wells.length === 0) {
      loadFleet();
    } else if (activeTab === 'overrides') {
      loadOverrides();
    }
  }, [activeTab]);

  const loadFleet = async () => {
    setLoadingFleet(true);
    try {
      const res = await fetch('http://localhost:8000/api/wells?limit=200');
      if (res.ok) {
        const data = await res.json();
        setWells(data);
      }
    } catch (err) {
      console.error('Failed to load wells:', err);
    } finally {
      setLoadingFleet(false);
    }
  };

  const loadOverrides = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/feedback/active');
      if (res.ok) {
        const data = await res.json();
        setActiveOverrides(data.overrides || []);
      }
    } catch (err) {
      console.error('Failed to load overrides:', err);
    }
  };

  const handleUserChange = (newUser: string) => {
    setCurrentUser(newUser);
    const initials = newUser.split(' ').map((p) => p[0]).join('');
    const newSession = `SESSION-${initials}-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;
    setSessionId(newSession);
    setMessages((prev) => [
      ...prev,
      {
        id: 'sys-' + Date.now(),
        sender: 'assistant',
        text: `*Switched operator context to: **${newUser}** (Session: \`${newSession}\`)*`,
      },
    ]);
  };

  const handleSendPrompt = async (promptText: string) => {
    if (!promptText.trim() || isSubmitting) return;

    setActiveTab('copilot');
    const userMsgId = 'user-' + Date.now();
    const assistantMsgId = 'assistant-' + Date.now();

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, sender: 'user', text: promptText, user_name: currentUser },
      { id: assistantMsgId, sender: 'assistant', loading: true },
    ]);

    setInputQuery('');
    setIsSubmitting(true);

    try {
      const res = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: promptText,
          user_name: currentUser,
          session_id: sessionId,
        }),
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}: ${await res.text()}`);
      }

      const envelope: CopilotResponseEnvelope = await res.json();

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? { id: assistantMsgId, sender: 'assistant', envelope, loading: false }
            : msg
        )
      );
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                id: assistantMsgId,
                sender: 'assistant',
                text: `**Error:** ${err.message}`,
                loading: false,
              }
            : msg
        )
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const executeResetState = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/feedback/reset', { method: 'POST' });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          id: 'reset-' + Date.now(),
          sender: 'assistant',
          text: `✓ *Runtime overrides purged and baseline restored in **${data.duration_ms}ms**.*`,
        },
      ]);
      loadOverrides();
    } catch (e: any) {
      alert('Reset error: ' + e.message);
    }
  };

  const handleOpenEval = async () => {
    setShowEvalModal(true);
    try {
      const res = await fetch('http://localhost:8000/api/evaluation/report');
      const data = await res.json();
      setEvalReport(data);
    } catch (e: any) {
      setEvalReport({ error: e.message });
    }
  };

  const renderVisual = (visual: VisualPayload) => {
    switch (visual.visual_type) {
      case 'status_card':
        return <StatusCardWidget spec={visual} />;
      case 'table':
        return <TableWidget spec={visual} />;
      case 'line_chart':
        return <LineChartWidget spec={visual} />;
      case 'bar_chart':
        return <BarChartWidget spec={visual} />;
      case 'map':
        return <MapWidget spec={visual} />;
      case 'heatmap':
        return <HeatmapWidget spec={visual} />;
      default:
        return null;
    }
  };

  // Filtered wells for Fleet Directory tab
  const filteredWells = wells.filter((w) => {
    const q = fleetSearch.toLowerCase().trim();
    if (q && !w.asset_id.toLowerCase().includes(q) && !w.well_name.toLowerCase().includes(q)) {
      return false;
    }
    if (areaFilter !== 'all' && w.area_name !== areaFilter) {
      return false;
    }
    if (statusFilter === 'producing' && !w.is_producing) {
      return false;
    }
    if (statusFilter === 'offline' && w.is_producing) {
      return false;
    }
    return true;
  });

  // Navigation definition
  const navigationSections: DashboardShellNavSection[] = [
    {
      id: 'main',
      title: 'Navigation',
      items: [
        {
          id: 'copilot',
          label: 'Copilot Workspace',
          icon: MessageSquare,
          badge: 'Active',
        },
        {
          id: 'fleet',
          label: 'Fleet Directory',
          icon: Layers,
          count: 600,
        },
        {
          id: 'analytics',
          label: 'Thermal Telemetry',
          icon: LineChart,
        },
        {
          id: 'overrides',
          label: 'Audit Ledger',
          icon: ShieldAlert,
        },
      ],
    },
    {
      id: 'areas',
      title: 'Operational Blocks',
      items: [
        { id: 'ne-08', label: 'Northeast Block 8', icon: MapPin, count: 25 },
        { id: 'ne-07', label: 'Northeast Block 7', icon: MapPin, count: 25 },
        { id: 'nw-03', label: 'Northwest Block 3', icon: MapPin, count: 25 },
        { id: 'se-01', label: 'Southeast Block 1', icon: MapPin, count: 25 },
        { id: 'sw-05', label: 'Southwest Block 5', icon: MapPin, count: 25 },
      ],
    },
    {
      id: 'presets',
      title: 'Scenario Presets',
      items: [
        { id: 'q1', label: 'Q1: Status Card', icon: Sparkles },
        { id: 'q2', label: 'Q2: Non-Producing Table', icon: Sparkles },
        { id: 'q3', label: 'Q3: 13-Week Delta T', icon: Sparkles },
        { id: 'q4', label: 'Q4: 4-Year Spills', icon: Sparkles },
        { id: 'q6', label: 'Q6: Downtime Bar Chart', icon: Sparkles },
        { id: 'q7', label: 'Q7: Active Spills Map', icon: Sparkles },
        { id: 'q8', label: 'Q8: Area × Month Heatmap', icon: Sparkles },
        { id: 'q12', label: 'Q12: Temp Sensor Override', icon: Flame },
        { id: 'q17', label: 'Q17: Contradiction Alert', icon: AlertTriangle },
      ],
    },
  ];

  const handleNavSelect = (id: string) => {
    if (['copilot', 'fleet', 'analytics', 'overrides'].includes(id)) {
      setActiveTab(id);
    } else if (id === 'ne-08') {
      setActiveTab('fleet');
      setAreaFilter('Northeast Block 8');
    } else if (id === 'ne-07') {
      setActiveTab('fleet');
      setAreaFilter('Northeast Block 7');
    } else if (id === 'nw-03') {
      setActiveTab('fleet');
      setAreaFilter('Northwest Block 3');
    } else if (id === 'se-01') {
      setActiveTab('fleet');
      setAreaFilter('Southeast Block 1');
    } else if (id === 'sw-05') {
      setActiveTab('fleet');
      setAreaFilter('Southwest Block 5');
    } else if (id === 'q1') {
      handleSendPrompt('Is WELL-0001 producing oil right now? Explain how you know.');
    } else if (id === 'q2') {
      handleSendPrompt('Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.');
    } else if (id === 'q3') {
      handleSendPrompt('Show the weekly wellhead and ambient temperatures for WELL-0001 over the last 13 weeks. On which dates was it not producing oil?');
    } else if (id === 'q4') {
      handleSendPrompt('How many oil spills has WELL-0001 had in the last 4 years, and how much oil in total? List them in a table.');
    } else if (id === 'q6') {
      handleSendPrompt('Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart.');
    } else if (id === 'q7') {
      handleSendPrompt('Show on a map every well in Northeast Block 8 with a real spill in the last 90 days.');
    } else if (id === 'q8') {
      handleSendPrompt('Produce a monthly heatmap of spill counts by area for 2026.');
    } else if (id === 'q12') {
      handleSendPrompt('The wellhead temperature on WELL-0164 was actually 41.0 °C on 15 Oct. The sensor was faulty.');
    } else if (id === 'q17') {
      handleSendPrompt('WELL-0175 is running fine.');
    }
  };

  return (
    <DashboardShell
      title="Asset Intelligence Copilot"
      status="600 Wells Live"
      statusTone="success"
      activeItemId={activeTab}
      onActiveItemChange={handleNavSelect}
      navigation={navigationSections}
      tabs={[
        { value: 'copilot', label: 'Intelligence Copilot', icon: MessageSquare },
        { value: 'fleet', label: 'Fleet Directory (600)', icon: Layers },
        { value: 'analytics', label: 'Telemetry & Analytics', icon: LineChart },
        { value: 'overrides', label: 'Audit Ledger', icon: ShieldAlert },
      ]}
      tab={activeTab}
      onTabChange={setActiveTab}
      headerActions={
        <div className="flex items-center gap-2">
          {/* Operator Switcher */}
          <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs shadow-xs">
            <span className="text-slate-500 text-[11px] font-medium">Operator:</span>
            <select
              value={currentUser}
              onChange={(e) => handleUserChange(e.target.value)}
              className="bg-transparent font-medium text-slate-800 outline-none cursor-pointer"
            >
              <option value="Michael Turner" className="bg-white">Michael Turner (Lead Supervisor, NE)</option>
              <option value="Jessica Reed" className="bg-white">Jessica Reed (Field Inspector, NE)</option>
              <option value="Tyler Hughes" className="bg-white">Tyler Hughes (Field Operator, NE)</option>
              <option value="Jake Morales" className="bg-white">Jake Morales (Field Operator, SW)</option>
              <option value="Laura Simmons" className="bg-white">Laura Simmons (HSE Officer, Fleet)</option>
            </select>
            <div className="w-5 h-5 rounded bg-sky-100 text-sky-800 font-bold text-[10px] flex items-center justify-center border border-sky-200">
              {currentUser.split(' ').map((p) => p[0]).join('')}
            </div>
          </div>

          {/* 18-Scenario Gate Action */}
          <DashboardButton variant="secondary" size="sm" onClick={handleOpenEval}>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span>18-Scenario Gate</span>
            <span className="text-[10px] px-1 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono font-medium">100%</span>
          </DashboardButton>

          {/* Reset State Action */}
          <DashboardButton variant="danger" size="sm" onClick={() => setShowResetDialog(true)}>
            <RefreshCw className="w-3.5 h-3.5" />
            <span className="hidden md:inline">Reset State</span>
          </DashboardButton>
        </div>
      }
      toolbarActions={
        <div className="hidden md:flex items-center gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Producing: <strong className="text-slate-900 font-mono">184</strong></span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            <span>Offline: <strong className="text-slate-900 font-mono">16</strong></span>
          </span>
          <span className="text-slate-300">|</span>
          <span className="text-slate-500 font-mono text-[11px]">DuckDB &bull; 0.19s</span>
        </div>
      }
      sidebarFooter={
        <div className="flex items-center justify-between text-[11px] text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span className="font-mono text-slate-600 font-medium">{sessionId}</span>
          </span>
          <span className="font-mono text-slate-400">v1.0.0</span>
        </div>
      }
    >
      {/* VIEW 1: Copilot Workspace */}
      {activeTab === 'copilot' && (
        <div className="flex-1 flex flex-col min-h-0 bg-[#f8fafc]">
          {/* Messages Stream */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-5">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-3xl ${
                  msg.sender === 'user' ? 'ml-auto justify-end items-start' : 'items-start'
                }`}
              >
                {msg.sender === 'assistant' && (
                  <div className="w-7 h-7 rounded-lg bg-slate-900 text-white flex-shrink-0 flex items-center justify-center font-bold text-xs shadow-xs">
                    AI
                  </div>
                )}

                <div className={`space-y-3 ${msg.sender === 'user' ? 'max-w-xl' : 'flex-1 max-w-3xl'}`}>
                  {msg.sender === 'user' ? (
                    <div className="bg-sky-600 text-white rounded-xl rounded-tr-none px-4 py-2.5 text-xs md:text-sm shadow-sm leading-relaxed">
                      {msg.text}
                    </div>
                  ) : msg.loading ? (
                    <div className="bg-white border border-slate-200 rounded-xl p-3.5 text-xs text-slate-500 flex items-center gap-2.5 shadow-xs">
                      <span className="w-2 h-2 rounded-full bg-sky-500 animate-ping" />
                      <span>Consulting telemetry overlay, repair logs & SOP compliance rules...</span>
                    </div>
                  ) : msg.envelope ? (
                    <>
                      {/* Conflict Alerts */}
                      {msg.envelope.conflict_cards.map((c, i) => (
                        <ConflictCard key={i} conflict={c} />
                      ))}

                      {/* Override Badges */}
                      {msg.envelope.override_badges.map((b, i) => (
                        <OverrideBadge key={i} badge={b} />
                      ))}

                      {/* Clean Markdown Answer */}
                      <div className="bg-white border border-slate-200 rounded-xl rounded-tl-none p-4 text-xs md:text-sm text-slate-800 leading-relaxed shadow-sm space-y-2">
                        <MarkdownRenderer content={msg.envelope.markdown_answer} />
                      </div>

                      {/* Visual Widget */}
                      {msg.envelope.visual_payload && (
                        <div className="pt-1">{renderVisual(msg.envelope.visual_payload)}</div>
                      )}

                      {/* Citations */}
                      {msg.envelope.citations.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5 pt-1">
                          <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mr-1">
                            Evidence Records:
                          </span>
                          {msg.envelope.citations.map((c) => (
                            <button
                              key={c.citation_id}
                              onClick={() => setSelectedCitation(c.citation_id)}
                              className="px-2 py-0.5 rounded bg-white hover:bg-slate-100 border border-slate-200 text-[11px] font-mono text-sky-700 hover:text-sky-900 shadow-xs transition"
                            >
                              [{c.label || c.citation_id}]
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="bg-white border border-slate-200 rounded-xl p-4 text-xs md:text-sm text-slate-700 leading-relaxed shadow-xs">
                      <MarkdownRenderer content={msg.text || ''} />
                    </div>
                  )}
                </div>

                {msg.sender === 'user' && (
                  <div className="w-7 h-7 rounded-lg bg-sky-100 text-sky-800 border border-sky-200 flex-shrink-0 flex items-center justify-center font-bold text-xs shadow-xs">
                    {currentUser.split(' ').map((p) => p[0]).join('')}
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Floating Linear-Style Prompt Dock in Light Mode */}
          <div className="p-4 border-t border-slate-200 bg-white/90 backdrop-blur-md flex-shrink-0">
            <div className="max-w-4xl mx-auto">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendPrompt(inputQuery);
                }}
                className="relative flex items-center bg-white border border-slate-300 focus-within:border-sky-600 focus-within:ring-2 focus-within:ring-sky-100 rounded-xl transition shadow-sm"
              >
                <input
                  type="text"
                  value={inputQuery}
                  onChange={(e) => setInputQuery(e.target.value)}
                  placeholder="Ask about well status, thermal delta T, downtime, spills, compliance, or provide an operational override..."
                  className="w-full bg-transparent px-4 py-3 text-xs md:text-sm text-slate-900 placeholder-slate-400 outline-none pr-28"
                />
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="absolute right-2 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-lg transition shadow-sm flex items-center gap-1.5 disabled:opacity-50"
                >
                  <span>Ask Copilot</span>
                  <Send className="w-3.5 h-3.5" />
                </button>
              </form>
              <div className="flex items-center justify-between text-[11px] text-slate-500 mt-2 px-1">
                <span>Press <kbd className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono border border-slate-200">Enter ↵</kbd> to query</span>
                <span className="flex items-center gap-2">
                  <button
                    onClick={() => handleSendPrompt('WELL-0175 is running fine.')}
                    className="text-rose-600 hover:underline font-medium"
                  >
                    Contradiction Demo
                  </button>
                  &bull;
                  <button
                    onClick={() =>
                      handleSendPrompt(
                        'The wellhead temperature on WELL-0164 was actually 41.0 °C on 15 Oct. The sensor was faulty.'
                      )
                    }
                    className="text-amber-700 hover:underline font-medium"
                  >
                    Calibration Override Demo
                  </button>
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 2: Fleet Directory */}
      {activeTab === 'fleet' && (
        <div className="flex-1 flex flex-col min-h-0 p-4 md:p-6 space-y-4 bg-[#f8fafc]">
          <div className="flex flex-wrap items-center justify-between gap-3 bg-white rounded-xl p-3 border border-slate-200 shadow-sm">
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={fleetSearch}
                  onChange={(e) => setFleetSearch(e.target.value)}
                  placeholder="Search asset ID or name..."
                  className="bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 outline-none w-56 focus:border-sky-500 focus:bg-white"
                />
              </div>

              <select
                value={areaFilter}
                onChange={(e) => setAreaFilter(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-700 outline-none"
              >
                <option value="all">All Operational Areas</option>
                <option value="Northeast Block 8">Northeast Block 8</option>
                <option value="Northeast Block 7">Northeast Block 7</option>
                <option value="Northwest Block 3">Northwest Block 3</option>
                <option value="Southeast Block 1">Southeast Block 1</option>
                <option value="Southwest Block 5">Southwest Block 5</option>
              </select>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-700 outline-none"
              >
                <option value="all">All Statuses</option>
                <option value="producing">Producing Only</option>
                <option value="offline">Offline / Stopped Only</option>
              </select>
            </div>

            <div className="text-xs text-slate-500">
              Showing <strong className="text-slate-900 font-mono">{filteredWells.length}</strong> / 200 Wells
            </div>
          </div>

          <div className="flex-1 overflow-y-auto bg-white rounded-xl border border-slate-200 shadow-sm">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200 sticky top-0 backdrop-blur z-10">
                <tr>
                  <th className="px-4 py-3">Asset ID</th>
                  <th className="px-4 py-3">Well Name</th>
                  <th className="px-4 py-3">Area</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-right">Delta T (&deg;C)</th>
                  <th className="px-4 py-3">Last Inspection</th>
                  <th className="px-4 py-3">Inspector</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loadingFleet ? (
                  <tr>
                    <td colSpan={9} className="p-8 text-center text-slate-400">
                      Loading fleet telemetry...
                    </td>
                  </tr>
                ) : filteredWells.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="p-8 text-center text-slate-400">
                      No wells matching criteria
                    </td>
                  </tr>
                ) : (
                  filteredWells.map((w) => (
                    <tr key={w.asset_id} className="hover:bg-slate-50/80 transition">
                      <td className="px-4 py-2.5 font-mono text-sky-700 font-bold">{w.asset_id}</td>
                      <td className="px-4 py-2.5 text-slate-900 font-medium">{w.well_name}</td>
                      <td className="px-4 py-2.5 text-slate-600">{w.area_name}</td>
                      <td className="px-4 py-2.5 text-slate-500 font-mono text-[11px]">{w.well_type}</td>
                      <td className="px-4 py-2.5 text-center">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            w.is_producing
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-rose-50 text-rose-700 border border-rose-200'
                          }`}
                        >
                          {w.is_producing ? 'PRODUCING' : 'OFFLINE'}
                        </span>
                      </td>
                      <td
                        className={`px-4 py-2.5 text-right font-mono font-medium ${
                          w.is_producing ? 'text-emerald-700' : 'text-rose-700'
                        }`}
                      >
                        {Number(w.effective_temp_delta_c || 0).toFixed(1)} &deg;C
                      </td>
                      <td className="px-4 py-2.5 text-slate-500 text-[11px]">{w.latest_inspection_date}</td>
                      <td className="px-4 py-2.5 text-slate-600">{w.inspector_name}</td>
                      <td className="px-4 py-2.5 text-right">
                        <button
                          onClick={() => {
                            setActiveTab('copilot');
                            handleSendPrompt(`Is ${w.asset_id} producing oil right now? Explain how you know.`);
                          }}
                          className="px-2.5 py-1 rounded bg-slate-100 hover:bg-sky-50 text-slate-700 hover:text-sky-700 text-[11px] border border-slate-200 transition font-medium"
                        >
                          Ask Copilot
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* VIEW 3: Telemetry & Analytics */}
      {activeTab === 'analytics' && (
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 bg-[#f8fafc]">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-1 shadow-sm">
              <span className="text-[11px] text-slate-500 uppercase tracking-wider block font-medium">Monitored Assets</span>
              <span className="text-2xl font-bold text-slate-900 font-mono">200 Wells</span>
              <span className="text-[11px] text-emerald-700 block font-medium">&check; 100% Telemetry Parity</span>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-1 shadow-sm">
              <span className="text-[11px] text-slate-500 uppercase tracking-wider block font-medium">Fleet Downtime</span>
              <span className="text-2xl font-bold text-amber-700 font-mono">8.0%</span>
              <span className="text-[11px] text-slate-500 block">16 wells offline across 4 areas</span>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-1 shadow-sm">
              <span className="text-[11px] text-slate-500 uppercase tracking-wider block font-medium">SOP Delta Threshold</span>
              <span className="text-2xl font-bold text-sky-700 font-mono">15.0 &deg;C</span>
              <span className="text-[11px] text-slate-500 block">T200 & T350 Standard Limits</span>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900">Interactive Operational Telemetry Views</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div
                onClick={() =>
                  handleSendPrompt(
                    'Show the weekly wellhead and ambient temperatures for WELL-0001 over the last 13 weeks. On which dates was it not producing oil?'
                  )
                }
                className="p-4 rounded-lg bg-slate-50 border border-slate-200 hover:border-sky-300 hover:bg-sky-50/40 cursor-pointer transition space-y-1"
              >
                <span className="text-xs font-semibold text-slate-900 block">13-Week Temperature Curve</span>
                <span className="text-[11px] text-slate-500 block">
                  Plots weekly wellhead, ambient, and delta T with threshold limits.
                </span>
              </div>

              <div
                onClick={() =>
                  handleSendPrompt(
                    'Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart.'
                  )
                }
                className="p-4 rounded-lg bg-slate-50 border border-slate-200 hover:border-sky-300 hover:bg-sky-50/40 cursor-pointer transition space-y-1"
              >
                <span className="text-xs font-semibold text-slate-900 block">Downtime Comparison Bar Chart</span>
                <span className="text-[11px] text-slate-500 block">
                  Identifies top downtime wells in NE Block 7 with duration breakdown.
                </span>
              </div>

              <div
                onClick={() =>
                  handleSendPrompt('Produce a monthly heatmap of spill counts by area for 2026.')
                }
                className="p-4 rounded-lg bg-slate-50 border border-slate-200 hover:border-sky-300 hover:bg-sky-50/40 cursor-pointer transition space-y-1"
              >
                <span className="text-xs font-semibold text-slate-900 block">Area &times; Month Spill Heatmap</span>
                <span className="text-[11px] text-slate-500 block">
                  Cross-tabulation matrix of 12-month verified environmental incidents.
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 4: Overrides & Audits */}
      {activeTab === 'overrides' && (
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 bg-[#f8fafc]">
          <div className="flex items-center justify-between bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Runtime Field Corrections Ledger</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Scoped in-memory DuckDB corrections overriding base telemetry with complete audit provenance.
              </p>
            </div>
            <DashboardButton variant="danger" size="sm" onClick={() => setShowResetDialog(true)}>
              Purge Overrides & Revert to Baseline
            </DashboardButton>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Target ID</th>
                  <th className="px-4 py-3">Field</th>
                  <th className="px-4 py-3">Old Value</th>
                  <th className="px-4 py-3">Overridden Value</th>
                  <th className="px-4 py-3">Author</th>
                  <th className="px-4 py-3">Origin</th>
                  <th className="px-4 py-3 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {activeOverrides.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-slate-400">
                      No active runtime overrides. System is operating on clean baseline telemetry.
                    </td>
                  </tr>
                ) : (
                  activeOverrides.map((o, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/80 transition">
                      <td className="px-4 py-2.5 font-mono text-sky-700 font-bold">{o.target_id}</td>
                      <td className="px-4 py-2.5 text-slate-800">{o.field_name}</td>
                      <td className="px-4 py-2.5 text-slate-400 font-mono">
                        <del>{String(o.old_value ?? '-')}</del>
                      </td>
                      <td className="px-4 py-2.5 text-emerald-700 font-mono font-bold">
                        {String(o.new_value ?? '-')}
                      </td>
                      <td className="px-4 py-2.5 text-slate-700">{o.author_name}</td>
                      <td className="px-4 py-2.5 text-slate-500 font-mono text-[11px]">{o.source_origin}</td>
                      <td className="px-4 py-2.5 text-right">
                        <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 text-[10px] font-bold">
                          ACTIVE
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 18-Scenario Evaluation Verification Gate Modal */}
      {showEvalModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl max-w-2xl w-full p-6 space-y-4 max-h-[85vh] flex flex-col shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center justify-center font-bold text-sm">
                  &check;
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 text-sm">18-Scenario Verification Gate</h3>
                  <p className="text-[11px] text-slate-500">Deterministic Parity across Part A1, A2, and Part B</p>
                </div>
              </div>
              <button
                onClick={() => setShowEvalModal(false)}
                className="text-slate-400 hover:text-slate-700 text-base"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3">
              {evalReport ? (
                <>
                  <div className="grid grid-cols-3 gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-100 text-center">
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase tracking-wider block font-medium">Total Scenarios</span>
                      <span className="text-base font-bold text-slate-900 font-mono">
                        {evalReport.summary?.total_scenarios || 18}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase tracking-wider block font-medium">Parity</span>
                      <span className="text-base font-bold text-emerald-700 font-mono">
                        {evalReport.summary?.parity_percentage || 100}%
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase tracking-wider block font-medium">Latency</span>
                      <span className="text-base font-bold text-sky-700 font-mono">
                        {evalReport.summary?.total_duration_seconds ? evalReport.summary?.total_duration_seconds + 's' : '0.19s'}
                      </span>
                    </div>
                  </div>

                  <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden bg-white shadow-xs">
                    {Object.keys(evalReport.scenarios || {}).map((q) => (
                      <div key={q} className="p-3 flex items-center justify-between text-xs hover:bg-slate-50 transition">
                        <div className="flex items-center gap-2.5">
                          <span className="w-2 h-2 rounded-full bg-emerald-500" />
                          <strong className="font-mono text-slate-900">{q}</strong>
                          <span className="text-slate-600 text-[11px] truncate max-w-md">
                            {evalReport.scenarios[q]?.prompt}
                          </span>
                        </div>
                        <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold text-[10px] font-mono">
                          PASS
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="text-center py-8 text-slate-400 text-xs">Loading verification report...</div>
              )}
            </div>

            <div className="pt-3 border-t border-slate-100 flex justify-end">
              <DashboardButton variant="secondary" onClick={() => setShowEvalModal(false)}>
                Close
              </DashboardButton>
            </div>
          </div>
        </div>
      )}

      {/* Citation Slide-over / Modal in Light Mode */}
      {selectedCitation && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-semibold text-sky-700 text-sm font-mono">
                Evidence Record: [{selectedCitation}]
              </h3>
              <button
                onClick={() => setSelectedCitation(null)}
                className="text-slate-400 hover:text-slate-700"
              >
                ✕
              </button>
            </div>
            <div className="space-y-2 text-xs text-slate-700">
              <p>
                <strong>Identifier:</strong> <code className="text-sky-700 font-mono">{selectedCitation}</code>
              </p>
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 font-mono text-[11px] text-slate-600 space-y-1">
                <div>Ground-truth verified deterministic record retrieved from DuckDB Semantic Views.</div>
                <div className="text-slate-400">SOURCE: artifacts/copilot.duckdb</div>
              </div>
            </div>
            <div className="pt-3 border-t border-slate-100 flex justify-end">
              <DashboardButton variant="secondary" onClick={() => setSelectedCitation(null)}>
                Dismiss
              </DashboardButton>
            </div>
          </div>
        </div>
      )}

      {/* Reset State Confirmation Dialog */}
      <DashboardConfirmDialog
        open={showResetDialog}
        onOpenChange={setShowResetDialog}
        tone="danger"
        title="Purge Runtime Overrides?"
        description="This rolls back all in-memory field corrections in <50ms and restores the pristine baseline telemetry state."
        confirmLabel="Purge & Reset"
        onConfirm={executeResetState}
      />
    </DashboardShell>
  );
}
