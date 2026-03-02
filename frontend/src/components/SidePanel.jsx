/**
 * SidePanel Component - World Situation Monitor
 * Right sidebar with tabbed content: Live Feeds, AI Insights, News, Alerts.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Radio,
  Brain,
  Newspaper,
  Bell,
  ChevronRight,
  ExternalLink,
  Shield,
  AlertTriangle,
  AlertCircle,
  Info,
  Clock,
  MapPin,
  Globe,
  Tv,
  Twitter,
  MessageCircle,
  Search,
  Crosshair,
  Hash,
  Send,
  Server,
} from 'lucide-react';
import AdUnit from './AdUnit';

const TABS = [
  { id: 'feeds', label: 'Feeds', icon: Radio },
  { id: 'x_intel', label: 'X Intel', icon: Twitter },
  { id: 'telegram', label: 'Telegram', icon: Send },
  { id: 'osint', label: 'OSINT', icon: Crosshair },
  { id: 'insights', label: 'AI Intel', icon: Brain },
  { id: 'news', label: 'News', icon: Newspaper },
  { id: 'alerts', label: 'Alerts', icon: Bell },
  { id: 'infra', label: 'Infra', icon: Server },
];

const COUNTRIES = [
  '', 'Iraq', 'Syria', 'Palestine', 'Israel', 'Iran', 'Yemen',
  'Lebanon', 'Saudi Arabia', 'UAE', 'Turkey', 'Egypt', 'Jordan',
  'Kuwait', 'Qatar', 'Bahrain', 'Oman', 'Afghanistan', 'Pakistan',
  'Libya', 'Sudan', 'Ukraine', 'Russia',
];

export default function SidePanel({
  activeTab,
  onTabChange,
  isOpen,
  onTogglePanel,
  selectedCountry,
  onCountryChange,
  liveFeeds,
  news,
  aiInsights,
  xIntelligence = [],
  telegramIntelligence = [],
  osintOther = [],
  alerts,
  infraOutages = [],
  dataCenters = [],
}) {
  const alertsRef = useRef(null);
  const [unreadAlerts, setUnreadAlerts] = useState(0);

  // Track unread alerts
  useEffect(() => {
    if (activeTab !== 'alerts' && alerts.length > 0) {
      setUnreadAlerts((prev) => prev + 1);
    }
  }, [alerts.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // Clear unread when switching to alerts tab
  useEffect(() => {
    if (activeTab === 'alerts') {
      setUnreadAlerts(0);
    }
  }, [activeTab]);

  // Auto-scroll alerts
  useEffect(() => {
    if (activeTab === 'alerts' && alertsRef.current) {
      alertsRef.current.scrollTop = 0;
    }
  }, [alerts, activeTab]);

  return (
    <>
      {/* Toggle button when panel is collapsed */}
      <button
        className={`side-panel-toggle ${isOpen ? 'hidden' : ''}`}
        onClick={onTogglePanel}
        title="Show panel"
      >
        <ChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />
      </button>

      {/* Side panel */}
      <div className={`side-panel glass-panel ${isOpen ? '' : 'collapsed'}`}>
        {/* Tab bar */}
        <div className="side-panel-tabs">
          {TABS.map((tab) => {
            const IconComp = tab.icon;
            return (
              <button
                key={tab.id}
                className={`side-panel-tab ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => onTabChange(tab.id)}
              >
                <IconComp size={14} />
                <span>{tab.label}</span>
                {tab.id === 'alerts' && unreadAlerts > 0 && (
                  <span className="tab-badge">{unreadAlerts > 99 ? '99+' : unreadAlerts}</span>
                )}
              </button>
            );
          })}
          {/* Close button */}
          <button
            className="side-panel-tab"
            onClick={onTogglePanel}
            style={{ flex: '0 0 36px' }}
            title="Close panel"
          >
            <ChevronRight size={14} />
          </button>
        </div>

        {/* Tab content */}
        <div className="side-panel-body" ref={activeTab === 'alerts' ? alertsRef : null}>
          {activeTab === 'feeds' && (
            <LiveFeedsTab
              feeds={liveFeeds}
              selectedCountry={selectedCountry}
              onCountryChange={onCountryChange}
            />
          )}
          {activeTab === 'x_intel' && (
            <XIntelligenceTab posts={xIntelligence} />
          )}
          {activeTab === 'telegram' && (
            <TelegramTab posts={telegramIntelligence} />
          )}
          {activeTab === 'osint' && (
            <OsintTab posts={osintOther} />
          )}
          {activeTab === 'insights' && (
            <AIInsightsTab insights={aiInsights} />
          )}
          {activeTab === 'news' && (
            <NewsTab
              news={news}
              selectedCountry={selectedCountry}
              onCountryChange={onCountryChange}
            />
          )}
          {activeTab === 'alerts' && (
            <AlertsTab alerts={alerts} />
          )}
          {activeTab === 'infra' && (
            <InfraTab outages={infraOutages} dataCenters={dataCenters} />
          )}

          {/* Non-intrusive ad at bottom of feed content */}
          <AdUnit format="banner" slot="side-panel-bottom" />
        </div>
      </div>
    </>
  );
}

// =============================================
// LIVE FEEDS TAB
// =============================================

function LiveFeedsTab({ feeds, selectedCountry, onCountryChange }) {
  const [activeEmbed, setActiveEmbed] = useState(null);

  return (
    <div>
      <div className="feed-country-selector">
        <select
          value={selectedCountry}
          onChange={(e) => onCountryChange(e.target.value)}
        >
          <option value="">All Countries</option>
          {COUNTRIES.filter(Boolean).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* YouTube embed player */}
      {activeEmbed && (
        <div style={{ padding: '8px', borderBottom: '1px solid var(--border-color)' }}>
          <div style={{ position: 'relative', paddingBottom: '56.25%', height: 0, overflow: 'hidden', borderRadius: 6, background: '#000' }}>
            <iframe
              src={`https://www.youtube.com/embed/${activeEmbed.embed_id}?autoplay=1&mute=1`}
              style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', border: 'none' }}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              title={activeEmbed.channel_name}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 }}>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
              <Radio size={10} style={{ marginRight: 4, color: '#ef4444', verticalAlign: 'middle' }} />
              {activeEmbed.channel_name}
            </span>
            <button
              onClick={() => setActiveEmbed(null)}
              style={{ background: 'rgba(239,68,68,0.2)', border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444', fontSize: 10, padding: '2px 8px', borderRadius: 4, cursor: 'pointer' }}
            >
              Close
            </button>
          </div>
        </div>
      )}

      {feeds.length === 0 ? (
        <div className="no-data">
          <Tv size={32} className="no-data-icon" />
          <div className="no-data-text">No live feeds available</div>
          <div className="no-data-sub">
            {selectedCountry
              ? `No streams found for ${selectedCountry}`
              : 'Select a country or try again later'}
          </div>
        </div>
      ) : (
        feeds.map((feed, idx) => (
          <div
            key={`${feed.channel_name}-${idx}`}
            className="feed-item"
          >
            <div className="feed-item-header">
              <span className="feed-item-channel">
                <Radio size={12} style={{ marginRight: 6, verticalAlign: 'middle', color: '#ef4444' }} />
                {feed.channel_name}
              </span>
              {feed.language && (
                <span className="feed-item-lang">{feed.language}</span>
              )}
            </div>
            <div className="feed-item-category" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <MapPin size={10} style={{ verticalAlign: 'middle' }} />
              {feed.country}
              <span style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
                {feed.embed_id && (
                  <button
                    onClick={(e) => { e.stopPropagation(); setActiveEmbed(feed); }}
                    style={{ background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)', color: '#3b82f6', fontSize: 9, padding: '2px 6px', borderRadius: 3, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3 }}
                    title="Watch here"
                  >
                    <Tv size={9} /> Watch
                  </button>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); if (feed.stream_url) window.open(feed.stream_url, '_blank', 'noopener'); }}
                  style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: 9, padding: '2px 6px', borderRadius: 3, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3 }}
                  title="Open in new tab"
                >
                  <ExternalLink size={9} /> Open
                </button>
              </span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// =============================================
// AI INSIGHTS TAB
// =============================================

function AIInsightsTab({ insights }) {
  if (insights.length === 0) {
    return (
      <div>
        <LoadingSkeleton count={3} />
      </div>
    );
  }

  return (
    <div>
      {insights.map((insight, idx) => (
        <div key={insight.id || idx} className="insight-card">
          <div className="insight-card-header">
            <div className="insight-card-title">{insight.title}</div>
            <SeverityBadge severity={insight.severity} />
          </div>
          <div className="insight-card-summary">{insight.summary}</div>
          <div className="insight-card-meta">
            {insight.region && (
              <span className="badge badge-region">{insight.region}</span>
            )}
            {insight.confidence != null && (
              <span className="insight-confidence">
                Confidence: {Math.round(insight.confidence * 100)}%
              </span>
            )}
            {insight.generated_at && (
              <span
                style={{
                  fontSize: 10,
                  color: 'var(--text-dim)',
                  fontFamily: 'var(--font-mono)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 3,
                }}
              >
                <Clock size={9} />
                {timeAgo(insight.generated_at)}
              </span>
            )}
          </div>
          {insight.analysis && (
            <ExpandableText text={insight.analysis} maxLength={150} />
          )}
        </div>
      ))}
    </div>
  );
}

// =============================================
// NEWS TAB
// =============================================

function NewsTab({ news: newsItems, selectedCountry, onCountryChange }) {
  if (newsItems.length === 0) {
    return (
      <div>
        <div className="feed-country-selector">
          <select
            value={selectedCountry}
            onChange={(e) => onCountryChange(e.target.value)}
          >
            <option value="">All Countries</option>
            {COUNTRIES.filter(Boolean).map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div className="no-data">
          <Newspaper size={32} className="no-data-icon" />
          <div className="no-data-text">No news articles</div>
          <div className="no-data-sub">Waiting for news data from backend</div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="feed-country-selector">
        <select
          value={selectedCountry}
          onChange={(e) => onCountryChange(e.target.value)}
        >
          <option value="">All Countries</option>
          {COUNTRIES.filter(Boolean).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {newsItems.map((item, idx) => (
        <div
          key={item.id || idx}
          className="news-item"
          onClick={() => {
            if (item.url) {
              window.open(item.url, '_blank', 'noopener');
            }
          }}
        >
          <div className="news-item-thumb">
            {item.image_url ? (
              <img
                src={item.image_url}
                alt=""
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.parentElement.innerHTML =
                    '<span class="thumb-placeholder"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="20" height="20" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg></span>';
                }}
              />
            ) : (
              <span className="thumb-placeholder">
                <Globe size={20} />
              </span>
            )}
          </div>
          <div className="news-item-content">
            <div className="news-item-title">{item.title}</div>
            <div className="news-item-meta">
              {item.source && <span>{item.source}</span>}
              {item.source && item.published_at && <span style={{ opacity: 0.3 }}>|</span>}
              {item.published_at && (
                <span>
                  <Clock size={9} style={{ marginRight: 2, verticalAlign: 'middle' }} />
                  {timeAgo(item.published_at)}
                </span>
              )}
              {item.country && (
                <span className="badge badge-region" style={{ fontSize: 8, padding: '1px 4px' }}>
                  {item.country}
                </span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// =============================================
// ALERTS TAB
// =============================================

function AlertsTab({ alerts: alertItems }) {
  if (alertItems.length === 0) {
    return (
      <div className="no-data">
        <Bell size={32} className="no-data-icon" />
        <div className="no-data-text">No alerts</div>
        <div className="no-data-sub">Real-time alerts will appear here via WebSocket</div>
      </div>
    );
  }

  return (
    <div>
      {alertItems.map((alert, idx) => {
        const severity = (alert.severity || alert.type || 'info').toLowerCase();
        const AlertIcon = getAlertIcon(severity);

        return (
          <div key={alert.id || idx} className={`alert-item ${severity}`}>
            <div className="alert-item-icon">
              <AlertIcon size={16} style={{ color: getAlertColor(severity) }} />
            </div>
            <div className="alert-item-content">
              <div className="alert-item-title">{alert.title || 'Alert'}</div>
              {alert.description && (
                <div className="alert-item-desc">{alert.description}</div>
              )}
              <div className="alert-item-time">
                {alert.timestamp ? timeAgo(alert.timestamp) : 'Just now'}
                {alert.region && (
                  <span
                    className="badge badge-region"
                    style={{ marginLeft: 6, fontSize: 8, padding: '1px 4px' }}
                  >
                    {alert.region}
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// =============================================
// X (TWITTER) INTELLIGENCE TAB
// =============================================

function XIntelligenceTab({ posts }) {
  if (posts.length === 0) {
    return (
      <div>
        <LoadingSkeleton count={3} />
      </div>
    );
  }

  return (
    <div>
      <div style={{ padding: '8px 12px', fontSize: 10, color: 'var(--text-dim)', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Twitter size={12} style={{ color: '#1d9bf0' }} />
        <span>OSINT accounts monitoring active conflicts</span>
      </div>
      {posts.map((post, idx) => (
        <div
          key={post.id || idx}
          className="feed-item"
          onClick={() => {
            if (post.url) window.open(post.url, '_blank', 'noopener');
          }}
        >
          <div className="feed-item-header">
            <span className="feed-item-channel" style={{ color: '#1d9bf0' }}>
              <Twitter size={12} style={{ marginRight: 6, verticalAlign: 'middle' }} />
              {post.channel}
            </span>
            <span className="feed-item-lang" style={{ fontSize: 9 }}>{post.handle}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, padding: '4px 0' }}>
            {post.text}
          </div>
          <div className="feed-item-category">
            {post.category && (
              <span className={`badge badge-${getCategoryColor(post.category)}`} style={{ fontSize: 8, padding: '1px 5px', marginRight: 6 }}>
                {post.category.toUpperCase()}
              </span>
            )}
            <Clock size={9} style={{ marginRight: 3, verticalAlign: 'middle' }} />
            {timeAgo(post.timestamp)}
            {!post.verified && (
              <span style={{ marginLeft: 8, fontSize: 9, color: 'var(--text-dim)', opacity: 0.6 }}>UNVERIFIED</span>
            )}
            <ExternalLink size={9} style={{ marginLeft: 'auto', verticalAlign: 'middle', opacity: 0.4 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// =============================================
// TELEGRAM INTELLIGENCE TAB
// =============================================

function TelegramTab({ posts }) {
  if (posts.length === 0) {
    return (
      <div>
        <LoadingSkeleton count={3} />
      </div>
    );
  }

  return (
    <div>
      <div style={{ padding: '8px 12px', fontSize: 10, color: 'var(--text-dim)', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Send size={12} style={{ color: '#27a7e7' }} />
        <span>Public Telegram OSINT channels</span>
      </div>
      {posts.map((post, idx) => (
        <div
          key={post.id || idx}
          className="feed-item"
          onClick={() => {
            if (post.url) window.open(post.url, '_blank', 'noopener');
          }}
        >
          <div className="feed-item-header">
            <span className="feed-item-channel" style={{ color: '#27a7e7' }}>
              <Send size={12} style={{ marginRight: 6, verticalAlign: 'middle' }} />
              {post.channel}
            </span>
            <span className="feed-item-lang" style={{ fontSize: 9 }}>{post.handle}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, padding: '4px 0' }}>
            {post.text && post.text.length > 300 ? post.text.substring(0, 300) + '...' : post.text}
          </div>
          <div className="feed-item-category">
            {post.category && (
              <span className={`badge badge-${getCategoryColor(post.category)}`} style={{ fontSize: 8, padding: '1px 5px', marginRight: 6 }}>
                {post.category.toUpperCase()}
              </span>
            )}
            <Clock size={9} style={{ marginRight: 3, verticalAlign: 'middle' }} />
            {timeAgo(post.timestamp)}
            {post.focus && (
              <span style={{ marginLeft: 8, fontSize: 9, color: 'var(--text-dim)' }}>{post.focus}</span>
            )}
            <ExternalLink size={9} style={{ marginLeft: 'auto', verticalAlign: 'middle', opacity: 0.4 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// =============================================
// OTHER OSINT TAB
// =============================================

function OsintTab({ posts }) {
  if (posts.length === 0) {
    return (
      <div>
        <LoadingSkeleton count={3} />
      </div>
    );
  }

  return (
    <div>
      <div style={{ padding: '8px 12px', fontSize: 10, color: 'var(--text-dim)', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Crosshair size={12} style={{ color: '#22c55e' }} />
        <span>SIGINT / IMINT / Maritime / Cyber Intelligence</span>
      </div>
      {posts.map((post, idx) => {
        const isClassified = post.source === 'osint_brief';
        return (
          <div
            key={post.id || idx}
            className={`feed-item ${isClassified ? 'insight-card' : ''}`}
            onClick={() => {
              if (post.url) window.open(post.url, '_blank', 'noopener');
            }}
          >
            <div className="feed-item-header">
              <span className="feed-item-channel" style={{ color: isClassified ? '#22c55e' : '#a78bfa' }}>
                {isClassified ? <Shield size={12} style={{ marginRight: 6, verticalAlign: 'middle' }} /> : <Search size={12} style={{ marginRight: 6, verticalAlign: 'middle' }} />}
                {post.channel}
              </span>
              {post.classification && (
                <span className="badge badge-info" style={{ fontSize: 8, padding: '1px 5px' }}>
                  {post.classification}
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: isClassified ? 'var(--text-primary)' : 'var(--text-secondary)', lineHeight: 1.5, padding: '4px 0', fontFamily: isClassified ? 'var(--font-mono)' : 'inherit' }}>
              {post.text}
            </div>
            <div className="feed-item-category">
              {post.category && (
                <span className={`badge badge-${getCategoryColor(post.category)}`} style={{ fontSize: 8, padding: '1px 5px', marginRight: 6 }}>
                  {post.category.toUpperCase()}
                </span>
              )}
              <Clock size={9} style={{ marginRight: 3, verticalAlign: 'middle' }} />
              {timeAgo(post.timestamp)}
              {post.focus && (
                <span style={{ marginLeft: 8, fontSize: 9, color: 'var(--text-dim)' }}>{post.focus}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// =============================================
// HELPER COMPONENTS
// =============================================

function SeverityBadge({ severity }) {
  const s = (severity || 'info').toLowerCase();
  const classMap = {
    critical: 'badge-critical',
    high: 'badge-high',
    medium: 'badge-medium',
    low: 'badge-low',
    info: 'badge-info',
  };
  return (
    <span className={`badge ${classMap[s] || 'badge-info'}`}>
      {s.toUpperCase()}
    </span>
  );
}

function LoadingSkeleton({ count = 3 }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton skeleton-card" />
      ))}
    </>
  );
}

function ExpandableText({ text, maxLength = 150 }) {
  const [expanded, setExpanded] = useState(false);

  if (!text) return null;
  if (text.length <= maxLength) {
    return (
      <div
        style={{
          fontSize: 11,
          color: 'var(--text-muted)',
          lineHeight: 1.5,
          marginTop: 8,
          borderTop: '1px solid var(--border-color)',
          paddingTop: 8,
        }}
      >
        {text}
      </div>
    );
  }

  return (
    <div
      style={{
        fontSize: 11,
        color: 'var(--text-muted)',
        lineHeight: 1.5,
        marginTop: 8,
        borderTop: '1px solid var(--border-color)',
        paddingTop: 8,
      }}
    >
      {expanded ? text : text.substring(0, maxLength) + '...'}
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          background: 'none',
          border: 'none',
          color: 'var(--accent-blue)',
          cursor: 'pointer',
          fontSize: 11,
          marginLeft: 4,
          padding: 0,
          fontFamily: 'var(--font-primary)',
        }}
      >
        {expanded ? 'Show less' : 'Read more'}
      </button>
    </div>
  );
}

// =============================================
// INFRASTRUCTURE TAB
// =============================================

function InfraTab({ outages, dataCenters }) {
  const PROVIDER_COLORS = { AWS: '#f97316', Azure: '#3b82f6', GCP: '#22c55e', Oracle: '#ef4444', Alibaba: '#f59e0b' };
  const STATUS_COLORS = { operational: '#22c55e', degraded: '#f59e0b', outage: '#ef4444', disrupted: '#ef4444', reported: '#f97316' };
  const CAUSE_LABELS = { war_related: 'WAR-RELATED', cyber_attack: 'CYBER', natural_disaster: 'NATURAL', technical: 'TECHNICAL' };
  const CAUSE_COLORS = { war_related: '#ef4444', cyber_attack: '#a855f7', natural_disaster: '#f59e0b', technical: '#3b82f6' };

  // Group data centers by provider
  const providers = {};
  (dataCenters || []).forEach(dc => {
    if (!providers[dc.provider]) providers[dc.provider] = { status: 'operational', count: 0, incidents: 0 };
    providers[dc.provider].count++;
    if (dc.status === 'outage' || dc.status === 'disrupted') {
      providers[dc.provider].status = 'outage';
      providers[dc.provider].incidents += dc.active_incidents || 0;
    } else if (dc.status === 'degraded' && providers[dc.provider].status !== 'outage') {
      providers[dc.provider].status = 'degraded';
      providers[dc.provider].incidents += dc.active_incidents || 0;
    }
  });

  return (
    <div>
      <div style={{ padding: '8px 12px', fontSize: 10, color: 'var(--text-dim)', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Server size={12} style={{ color: '#22d3ee' }} />
        <span>Cloud & infrastructure status monitoring</span>
      </div>

      {/* Provider status cards */}
      <div style={{ padding: '8px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
        {Object.entries(providers).map(([name, info]) => (
          <div key={name} style={{
            background: 'rgba(255,255,255,0.03)',
            border: `1px solid ${STATUS_COLORS[info.status] || 'var(--border-color)'}33`,
            borderRadius: 6,
            padding: '8px 10px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: PROVIDER_COLORS[name] || '#fff' }}>{name}</span>
              <span style={{
                fontSize: 8,
                fontWeight: 700,
                color: STATUS_COLORS[info.status],
                background: `${STATUS_COLORS[info.status]}15`,
                padding: '1px 5px',
                borderRadius: 3,
                textTransform: 'uppercase',
              }}>
                {info.status}
              </span>
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-dim)' }}>
              {info.count} regions{info.incidents > 0 ? ` | ${info.incidents} incidents` : ''}
            </div>
          </div>
        ))}
      </div>

      {/* Active outages */}
      <div style={{ padding: '4px 12px 4px', fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        Active Incidents ({(outages || []).length})
      </div>

      {(!outages || outages.length === 0) ? (
        <div className="no-data" style={{ padding: '20px 12px' }}>
          <Server size={24} className="no-data-icon" style={{ color: '#22c55e' }} />
          <div className="no-data-text" style={{ color: '#22c55e' }}>All Systems Operational</div>
          <div className="no-data-sub">No active infrastructure incidents</div>
        </div>
      ) : (
        outages.map((outage, idx) => (
          <div key={outage.id || idx} className="feed-item" style={{ borderLeft: `3px solid ${STATUS_COLORS[outage.status] || '#3b82f6'}` }}
            onClick={() => { if (outage.url) window.open(outage.url, '_blank', 'noopener'); }}
          >
            <div className="feed-item-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: PROVIDER_COLORS[outage.provider] || '#fff' }}>
                {outage.provider} {outage.service ? `- ${outage.service}` : ''}
              </span>
              <span style={{
                fontSize: 8,
                fontWeight: 700,
                color: STATUS_COLORS[outage.status] || '#3b82f6',
                background: `${STATUS_COLORS[outage.status] || '#3b82f6'}15`,
                padding: '1px 5px',
                borderRadius: 3,
              }}>
                {(outage.status || 'reported').toUpperCase()}
              </span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4, padding: '2px 0' }}>
              {outage.title}
            </div>
            <div className="feed-item-category" style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              {outage.cause && CAUSE_LABELS[outage.cause] && (
                <span style={{
                  fontSize: 8,
                  fontWeight: 700,
                  color: CAUSE_COLORS[outage.cause] || '#6b7280',
                  background: `${CAUSE_COLORS[outage.cause] || '#6b7280'}15`,
                  padding: '1px 5px',
                  borderRadius: 3,
                  border: `1px solid ${CAUSE_COLORS[outage.cause] || '#6b7280'}33`,
                }}>
                  {CAUSE_LABELS[outage.cause]}
                </span>
              )}
              {outage.severity && (
                <SeverityBadge severity={outage.severity} />
              )}
              {outage.country && (
                <span style={{ fontSize: 9, color: 'var(--text-dim)' }}>
                  <MapPin size={9} style={{ verticalAlign: 'middle', marginRight: 2 }} />
                  {outage.country}
                </span>
              )}
              {outage.start_time && (
                <span style={{ fontSize: 9, color: 'var(--text-dim)', marginLeft: 'auto' }}>
                  <Clock size={9} style={{ verticalAlign: 'middle', marginRight: 2 }} />
                  {timeAgo(outage.start_time)}
                </span>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// =============================================
// HELPER FUNCTIONS
// =============================================

function getAlertIcon(severity) {
  switch (severity) {
    case 'critical': return Shield;
    case 'high': return AlertTriangle;
    case 'medium': return AlertCircle;
    case 'low': return Info;
    default: return Info;
  }
}

function getAlertColor(severity) {
  switch (severity) {
    case 'critical': return '#ef4444';
    case 'high': return '#f97316';
    case 'medium': return '#f59e0b';
    case 'low': return '#22c55e';
    default: return '#3b82f6';
  }
}

function getCategoryColor(category) {
  switch (category) {
    case 'missile': return 'critical';
    case 'strike': return 'high';
    case 'drone': return 'high';
    case 'nuclear': return 'critical';
    case 'casualties': return 'critical';
    case 'naval': return 'info';
    case 'aviation': return 'info';
    case 'military': return 'medium';
    case 'diplomacy': return 'low';
    default: return 'info';
  }
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return '';
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);

    if (diffSec < 60) return 'just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}
