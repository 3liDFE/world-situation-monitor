/**
 * Header Component - World Situation Monitor
 * Top bar with branding, system status, time, region controls, and search.
 */

import React, { useState, useEffect } from 'react';
import {
  Globe,
  Search,
  Wifi,
  WifiOff,
  Activity,
  Clock,
} from 'lucide-react';

const REGIONS = ['Global', 'Middle East', 'Europe', 'Asia', 'Africa'];
const TIME_RANGES = ['Live', '24h', '7d', '30d'];

export default function Header({
  connectionStatus,
  activeRegion,
  onRegionSelect,
  timeRange,
  onTimeRangeChange,
  searchQuery,
  onSearchChange,
  dataFreshness,
  systemStatus,
}) {
  const [utcTime, setUtcTime] = useState('');

  // Update UTC clock every second
  useEffect(() => {
    const update = () => {
      const now = new Date();
      const hh = String(now.getUTCHours()).padStart(2, '0');
      const mm = String(now.getUTCMinutes()).padStart(2, '0');
      const ss = String(now.getUTCSeconds()).padStart(2, '0');
      setUtcTime(`${hh}:${mm}:${ss} UTC`);
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  // Determine freshness status for key data layers
  const getFreshnessStatus = (key, maxAgeMs) => {
    const ts = dataFreshness[key];
    if (!ts) return 'offline';
    const age = Date.now() - ts;
    if (age < maxAgeMs) return 'fresh';
    if (age < maxAgeMs * 3) return 'stale';
    return 'offline';
  };

  const statusDotClass =
    connectionStatus === 'connected'
      ? 'connected'
      : connectionStatus === 'reconnecting'
      ? 'reconnecting'
      : 'disconnected';

  const statusLabel =
    connectionStatus === 'connected'
      ? 'LIVE'
      : connectionStatus === 'reconnecting'
      ? 'RECONNECTING'
      : 'OFFLINE';

  return (
    <header className="header">
      {/* Logo */}
      <div className="header-logo">
        <div className="logo-badge">
          <Globe size={16} className="logo-icon" />
          <div className="logo-pulse" />
        </div>
        <div className="logo-text">
          <h1>WSM</h1>
          <span className="logo-subtitle">World Situation Monitor</span>
        </div>
      </div>

      <div className="header-divider" />

      {/* Connection status */}
      <div className="header-status">
        <div className={`status-dot ${statusDotClass}`} />
        <span>{statusLabel}</span>
      </div>

      <div className="header-divider" />

      {/* UTC Clock */}
      <div className="header-time">
        <Clock size={11} style={{ marginRight: 4, verticalAlign: 'middle', opacity: 0.7 }} />
        {utcTime}
      </div>

      <div className="header-divider" />

      {/* Region quick-select */}
      <div className="header-regions">
        {REGIONS.map((region) => (
          <button
            key={region}
            className={`region-btn ${activeRegion === region ? 'active' : ''}`}
            onClick={() => onRegionSelect(region)}
          >
            {region}
          </button>
        ))}
      </div>

      <div className="header-divider" />

      {/* Time range */}
      <div className="header-time-range">
        {TIME_RANGES.map((tr) => (
          <button
            key={tr}
            className={`time-btn ${timeRange === tr ? 'active' : ''}`}
            onClick={() => onTimeRangeChange(tr)}
          >
            {tr}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="header-search">
        <Search size={12} className="search-icon" />
        <input
          type="text"
          placeholder="Search locations, events..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>

      {/* Data freshness indicators */}
      <div className="header-freshness">
        <div className="freshness-item">
          <div className={`freshness-dot ${getFreshnessStatus('conflicts', 120000)}`} />
          <span>CONF</span>
        </div>
        <div className="freshness-item">
          <div className={`freshness-dot ${getFreshnessStatus('aircraft', 30000)}`} />
          <span>AIR</span>
        </div>
        <div className="freshness-item">
          <div className={`freshness-dot ${getFreshnessStatus('missiles', 90000)}`} />
          <span>MSL</span>
        </div>
        <div className="freshness-item">
          <div className={`freshness-dot ${getFreshnessStatus('earthquakes', 600000)}`} />
          <span>EQ</span>
        </div>
        <div className="freshness-item">
          <div className={`freshness-dot ${getFreshnessStatus('news', 300000)}`} />
          <span>NEWS</span>
        </div>
      </div>
    </header>
  );
}
