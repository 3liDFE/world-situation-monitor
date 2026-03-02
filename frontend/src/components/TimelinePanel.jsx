/**
 * TimelinePanel Component - World Situation Monitor
 * Collapsible bottom panel showing correlated event chains.
 */

import React from 'react';
import { ChevronUp, ChevronDown, Link2, Clock, MapPin } from 'lucide-react';

const TYPE_COLORS = {
  conflict: '#ef4444',
  missile: '#f97316',
  news: '#3b82f6',
  infrastructure: '#22d3ee',
  aircraft: '#06b6d4',
  vessel: '#3b82f6',
};

const CHAIN_TYPE_LABELS = {
  escalation: 'ESCALATION',
  retaliation: 'RETALIATION',
  cascade: 'CASCADE',
  related: 'RELATED',
};

const SEVERITY_COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#f59e0b',
  low: '#22c55e',
  info: '#3b82f6',
};

function formatTime(ts) {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) +
      ' ' + d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

export default function TimelinePanel({
  eventChains,
  isOpen,
  onToggle,
  selectedChain,
  onSelectChain,
}) {
  const chains = eventChains || [];

  return (
    <div className={`timeline-panel ${isOpen ? 'timeline-panel-open' : ''}`}>
      {/* Toggle bar */}
      <div className="timeline-panel-toggle" onClick={onToggle}>
        <div className="timeline-panel-toggle-content">
          <Link2 size={14} />
          <span>Event Correlation Timeline</span>
          <span className="timeline-panel-count">{chains.length} chains</span>
        </div>
        {isOpen ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
      </div>

      {/* Content */}
      {isOpen && (
        <div className="timeline-panel-body">
          {chains.length === 0 ? (
            <div className="timeline-panel-empty">
              No correlated event chains detected. Chains form when events share temporal,
              geographic, and thematic proximity.
            </div>
          ) : (
            <div className="timeline-chains-scroll">
              {chains.map((chain) => {
                const isSelected = selectedChain?.id === chain.id;
                return (
                  <div
                    key={chain.id}
                    className={`timeline-chain-card ${isSelected ? 'timeline-chain-selected' : ''}`}
                    onClick={() => onSelectChain(isSelected ? null : chain)}
                  >
                    {/* Chain header */}
                    <div className="timeline-chain-header">
                      <span
                        className="timeline-chain-type-badge"
                        style={{
                          color: SEVERITY_COLORS[chain.severity] || '#3b82f6',
                          borderColor: SEVERITY_COLORS[chain.severity] || '#3b82f6',
                        }}
                      >
                        {CHAIN_TYPE_LABELS[chain.chain_type] || 'RELATED'}
                      </span>
                      <span className="timeline-chain-title">{chain.title}</span>
                    </div>

                    {/* Chain meta */}
                    <div className="timeline-chain-meta">
                      <span><Clock size={10} /> {formatTime(chain.timestamp_start)}</span>
                      {chain.regions && chain.regions.length > 0 && (
                        <span><MapPin size={10} /> {chain.regions.slice(0, 3).join(', ')}</span>
                      )}
                      <span>{chain.events?.length || 0} events</span>
                    </div>

                    {/* Chain events timeline */}
                    {isSelected && chain.events && (
                      <div className="timeline-chain-events">
                        {chain.events.map((evt, idx) => (
                          <div key={evt.id || idx} className="timeline-event-node">
                            <div
                              className="timeline-event-dot"
                              style={{ background: TYPE_COLORS[evt.type] || '#6b7280' }}
                            />
                            {idx < chain.events.length - 1 && (
                              <div className="timeline-event-connector" />
                            )}
                            <div className="timeline-event-info">
                              <span className="timeline-event-type" style={{ color: TYPE_COLORS[evt.type] || '#6b7280' }}>
                                {(evt.type || 'event').toUpperCase()}
                              </span>
                              <span className="timeline-event-title">{evt.title}</span>
                              <span className="timeline-event-time">{formatTime(evt.timestamp)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Summary */}
                    <div className="timeline-chain-summary">{chain.summary}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
