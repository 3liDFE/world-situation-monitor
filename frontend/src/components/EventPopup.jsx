/**
 * EventPopup Component - World Situation Monitor
 * Overlay popup for clicked map events.
 * Note: The primary popup is rendered via MapLibre's native Popup API
 * (see MapContainer.jsx buildPopupHTML). This React component serves as
 * an alternative detail view for complex events or when used outside the map.
 */

import React from 'react';
import {
  X,
  MapPin,
  Clock,
  Shield,
  Plane,
  AlertTriangle,
  Radio,
  Building2,
  Atom,
  Navigation,
  Cloud,
  ExternalLink,
} from 'lucide-react';

const TYPE_CONFIG = {
  conflict: { icon: Shield, color: '#ef4444', label: 'Active Conflict' },
  aircraft: { icon: Plane, color: '#06b6d4', label: 'Aircraft' },
  missile_launch: { icon: Radio, color: '#f97316', label: 'Missile Launch' },
  missile_target: { icon: Radio, color: '#ef4444', label: 'Missile Target' },
  earthquake: { icon: AlertTriangle, color: '#f43f5e', label: 'Earthquake' },
  military_base: { icon: Building2, color: '#8b5cf6', label: 'Military Base' },
  nuclear: { icon: Atom, color: '#eab308', label: 'Nuclear Site' },
  waterway: { icon: Navigation, color: '#0ea5e9', label: 'Waterway' },
  weather: { icon: Cloud, color: '#a855f7', label: 'Weather' },
};

export default function EventPopup({ event, onClose }) {
  if (!event) return null;

  const config = TYPE_CONFIG[event.type] || {
    icon: MapPin,
    color: '#3b82f6',
    label: event.type || 'Event',
  };
  const IconComp = config.icon;

  const severity = event.intensity || event.severity || event.status || '';
  const title = event.title || event.name || event.callsign || 'Unknown Event';
  const description = event.description || '';

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 24,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 350,
        background: 'rgba(17, 24, 39, 0.95)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: '1px solid rgba(59, 130, 246, 0.2)',
        borderRadius: 10,
        boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
        padding: 16,
        minWidth: 300,
        maxWidth: 420,
        animation: 'fadeIn 0.2s ease',
      }}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        style={{
          position: 'absolute',
          top: 8,
          right: 8,
          background: 'none',
          border: 'none',
          color: '#64748b',
          cursor: 'pointer',
          padding: 4,
          borderRadius: 4,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <X size={16} />
      </button>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: config.color + '20',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <IconComp size={16} style={{ color: config.color }} />
        </div>
        <div>
          <div style={{ fontSize: 9, fontWeight: 700, color: config.color, textTransform: 'uppercase', letterSpacing: 1 }}>
            {config.label}
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9' }}>{title}</div>
        </div>
      </div>

      {/* Severity badge */}
      {severity && (
        <div style={{ marginBottom: 8 }}>
          <SeverityBadge severity={severity} />
        </div>
      )}

      {/* Description */}
      {description && (
        <div
          style={{
            fontSize: 12,
            color: '#94a3b8',
            lineHeight: 1.5,
            marginBottom: 10,
            maxHeight: 80,
            overflow: 'hidden',
          }}
        >
          {description}
        </div>
      )}

      {/* Meta info based on type */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {event.type === 'aircraft' && (
          <>
            <MetaRow label="Callsign" value={event.callsign || 'N/A'} />
            <MetaRow label="Altitude" value={event.altitude ? `${Math.round(event.altitude)} m` : 'N/A'} />
            <MetaRow label="Speed" value={event.velocity ? `${Math.round(event.velocity)} m/s` : 'N/A'} />
            <MetaRow label="Heading" value={event.heading ? `${Math.round(event.heading)}deg` : 'N/A'} />
            <MetaRow label="Country" value={event.origin_country || 'N/A'} />
          </>
        )}
        {event.type === 'conflict' && (
          <>
            <MetaRow label="Parties" value={event.parties || 'N/A'} />
            <MetaRow label="Radius" value={event.radius ? `${event.radius} km` : 'N/A'} />
          </>
        )}
        {(event.type === 'missile_launch' || event.type === 'missile_target') && (
          <>
            <MetaRow label="Type" value={event.missile_type || 'N/A'} />
            <MetaRow label="Status" value={event.status || 'N/A'} />
          </>
        )}
        {event.type === 'earthquake' && (
          <>
            <MetaRow label="Magnitude" value={event.magnitude || 'N/A'} />
            <MetaRow label="Depth" value={event.depth ? `${event.depth} km` : 'N/A'} />
          </>
        )}
        {event.type === 'military_base' && (
          <>
            <MetaRow label="Country" value={event.country || 'N/A'} />
            <MetaRow label="Branch" value={event.branch || 'N/A'} />
            <MetaRow label="Type" value={event.base_type || 'N/A'} />
          </>
        )}
        {event.type === 'nuclear' && (
          <>
            <MetaRow label="Country" value={event.country || 'N/A'} />
            <MetaRow label="Type" value={event.site_type || 'N/A'} />
            <MetaRow label="Status" value={event.status || 'N/A'} />
          </>
        )}

        {/* Coordinates */}
        {(event.lat != null && event.lng != null) && (
          <MetaRow
            label="Location"
            value={`${Number(event.lat).toFixed(4)}, ${Number(event.lng).toFixed(4)}`}
          />
        )}

        {/* Timestamp */}
        {event.timestamp && (
          <MetaRow label="Time" value={formatTimestamp(event.timestamp)} />
        )}
      </div>
    </div>
  );
}

function MetaRow({ label, value }) {
  return (
    <div style={{ display: 'flex', fontSize: 11, gap: 8 }}>
      <span style={{ color: '#475569', minWidth: 65 }}>{label}:</span>
      <span style={{ color: '#94a3b8', fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
        {value}
      </span>
    </div>
  );
}

function SeverityBadge({ severity }) {
  const s = (severity || '').toLowerCase();
  const colorMap = {
    critical: { bg: 'rgba(239,68,68,0.15)', fg: '#ef4444', border: 'rgba(239,68,68,0.3)' },
    high: { bg: 'rgba(249,115,22,0.12)', fg: '#f97316', border: 'rgba(249,115,22,0.3)' },
    medium: { bg: 'rgba(245,158,11,0.15)', fg: '#f59e0b', border: 'rgba(245,158,11,0.3)' },
    low: { bg: 'rgba(34,197,94,0.15)', fg: '#22c55e', border: 'rgba(34,197,94,0.3)' },
    confirmed: { bg: 'rgba(249,115,22,0.12)', fg: '#f97316', border: 'rgba(249,115,22,0.3)' },
    reported: { bg: 'rgba(245,158,11,0.15)', fg: '#f59e0b', border: 'rgba(245,158,11,0.3)' },
    intercepted: { bg: 'rgba(34,197,94,0.15)', fg: '#22c55e', border: 'rgba(34,197,94,0.3)' },
  };
  const c = colorMap[s] || { bg: 'rgba(59,130,246,0.15)', fg: '#3b82f6', border: 'rgba(59,130,246,0.3)' };

  return (
    <span
      style={{
        display: 'inline-flex',
        padding: '2px 7px',
        borderRadius: 3,
        fontSize: 10,
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: 0.3,
        background: c.bg,
        color: c.fg,
        border: `1px solid ${c.border}`,
      }}
    >
      {s.toUpperCase()}
    </span>
  );
}

function formatTimestamp(ts) {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return String(ts);
    return d.toUTCString().replace('GMT', 'UTC');
  } catch {
    return String(ts);
  }
}
