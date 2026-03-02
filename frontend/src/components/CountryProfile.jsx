/**
 * CountryProfile Component - World Situation Monitor
 * Slide-out drawer showing aggregated intelligence for a selected country.
 */

import React, { useState } from 'react';
import {
  X, Shield, AlertTriangle, Building2, Atom, Crosshair,
  Newspaper, Globe, Users, Zap, ChevronDown, ChevronRight,
} from 'lucide-react';
import AdUnit from './AdUnit';

// Curated alliance/relationship data
const ALLIANCES = {
  'Iran': { allies: ['Syria', 'Russia', 'China', 'Iraq (militia)'], rivals: ['Israel', 'Saudi Arabia', 'UAE', 'US'], groups: ['Axis of Resistance', 'SCO Observer'] },
  'Israel': { allies: ['United States', 'UAE', 'Bahrain', 'Morocco'], rivals: ['Iran', 'Hamas', 'Hezbollah', 'Houthis'], groups: ['Abraham Accords', 'US MNNA'] },
  'Saudi Arabia': { allies: ['UAE', 'US', 'Egypt', 'Bahrain'], rivals: ['Iran', 'Houthis', 'Qatar (hist.)'], groups: ['GCC', 'Arab League', 'OPEC+'] },
  'UAE': { allies: ['Saudi Arabia', 'US', 'Israel', 'Egypt'], rivals: ['Iran', 'Turkey (hist.)'], groups: ['GCC', 'Abraham Accords', 'I2U2'] },
  'Turkey': { allies: ['Azerbaijan', 'Qatar', 'Pakistan'], rivals: ['PKK/YPG', 'Greece (tensions)'], groups: ['NATO', 'OIC'] },
  'Iraq': { allies: ['Iran', 'US (complex)', 'Turkey'], rivals: ['ISIS remnants'], groups: ['Arab League', 'OPEC'] },
  'Syria': { allies: ['Iran', 'Russia', 'Hezbollah'], rivals: ['Turkey', 'Israel', 'HTS'], groups: ['Axis of Resistance'] },
  'Egypt': { allies: ['Saudi Arabia', 'UAE', 'US', 'France'], rivals: ['Muslim Brotherhood', 'Ethiopia (GERD)'], groups: ['Arab League', 'African Union'] },
  'Qatar': { allies: ['Turkey', 'US', 'UK'], rivals: ['Saudi (hist.)', 'UAE (hist.)'], groups: ['GCC', 'LNG Exporters'] },
  'Jordan': { allies: ['US', 'Saudi Arabia', 'UAE'], rivals: ['None currently'], groups: ['Arab League', 'US MNNA'] },
  'Lebanon': { allies: ['Iran (Hezbollah)', 'France'], rivals: ['Israel'], groups: ['Arab League'] },
  'Yemen': { allies: ['Saudi Coalition', 'UAE (south)'], rivals: ['Houthis/Ansar Allah'], groups: ['Arab League (suspended)'] },
  'Kuwait': { allies: ['US', 'Saudi Arabia', 'UK'], rivals: ['Iraq (hist.)'], groups: ['GCC', 'OPEC'] },
  'Bahrain': { allies: ['Saudi Arabia', 'US', 'Israel'], rivals: ['Iran'], groups: ['GCC', 'Abraham Accords'] },
  'Oman': { allies: ['Neutral mediator', 'US', 'UK'], rivals: ['None (neutral)'], groups: ['GCC'] },
  'Pakistan': { allies: ['China', 'Turkey', 'Saudi Arabia'], rivals: ['India', 'TTP'], groups: ['SCO', 'OIC', 'Nuclear Power'] },
  'Afghanistan': { allies: ['Pakistan (complex)', 'China (econ)'], rivals: ['ISIS-K', 'NRF'], groups: ['Taliban-controlled'] },
  'Ukraine': { allies: ['US', 'EU', 'UK', 'NATO support'], rivals: ['Russia'], groups: ['EU candidate', 'NATO partner'] },
  'Russia': { allies: ['China', 'Iran', 'North Korea', 'Syria'], rivals: ['NATO', 'Ukraine', 'US'], groups: ['SCO', 'BRICS', 'CSTO', 'Nuclear Power'] },
  'Libya': { allies: ['Turkey (GNA)', 'Egypt (LNA)', 'Russia (Wagner)'], rivals: ['Internal factions'], groups: ['Arab League', 'OPEC'] },
  'Sudan': { allies: ['Egypt', 'Saudi Arabia (SAF)', 'UAE (RSF)'], rivals: ['Internal civil war'], groups: ['Arab League', 'African Union'] },
  'Palestine': { allies: ['Iran', 'Turkey', 'Qatar'], rivals: ['Israel'], groups: ['Arab League Observer'] },
};

function computeThreatLevel(country, conflicts, missiles) {
  const matchCountry = (item) => {
    const text = JSON.stringify(item).toLowerCase();
    return text.includes(country.toLowerCase());
  };
  const countryConflicts = (conflicts || []).filter(matchCountry);
  const countryMissiles = (missiles || []).filter(matchCountry);
  const score = countryConflicts.length + countryMissiles.length;
  if (score >= 6) return { level: 'CRITICAL', color: '#ef4444', bg: 'rgba(239,68,68,0.15)' };
  if (score >= 3) return { level: 'HIGH', color: '#f97316', bg: 'rgba(249,115,22,0.15)' };
  if (score >= 1) return { level: 'MEDIUM', color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' };
  return { level: 'LOW', color: '#22c55e', bg: 'rgba(34,197,94,0.15)' };
}

function filterByCountry(items, country) {
  if (!items || !country) return [];
  const c = country.toLowerCase();
  return items.filter(item => {
    const text = JSON.stringify(item).toLowerCase();
    return text.includes(c);
  });
}

function CollapsibleSection({ title, icon: Icon, count, children, defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="country-profile-section">
      <div className="country-profile-section-header" onClick={() => setIsOpen(v => !v)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {Icon && <Icon size={14} />}
          <span>{title}</span>
          {count > 0 && <span className="country-profile-count">{count}</span>}
        </div>
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </div>
      {isOpen && <div className="country-profile-section-content">{children}</div>}
    </div>
  );
}

export default function CountryProfile({
  country,
  conflicts,
  missiles,
  militaryBases,
  nuclearSites,
  news,
  xIntelligence,
  telegramIntelligence,
  osintOther,
  infraOutages,
  onClose,
}) {
  const threat = computeThreatLevel(country, conflicts, missiles);
  const alliance = ALLIANCES[country] || { allies: [], rivals: [], groups: [] };

  const countryConflicts = filterByCountry(conflicts, country);
  const countryMissiles = filterByCountry(missiles, country);
  const countryBases = (militaryBases || []).filter(b => b.country === country);
  const countryNuclear = (nuclearSites || []).filter(n => n.country === country);
  const countryNews = filterByCountry(news, country);
  const countryXIntel = filterByCountry(xIntelligence, country);
  const countryTelegram = filterByCountry(telegramIntelligence, country);
  const countryOsint = filterByCountry(osintOther, country);
  const countryInfra = filterByCountry(infraOutages, country);

  return (
    <div className="country-profile-overlay">
      <div className="country-profile-drawer glass-panel">
        {/* Header */}
        <div className="country-profile-header">
          <div>
            <h2 className="country-profile-name">{country}</h2>
            <div
              className="country-profile-threat-badge"
              style={{ color: threat.color, background: threat.bg }}
            >
              <Shield size={12} />
              Threat Level: {threat.level}
            </div>
          </div>
          <button className="country-profile-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="country-profile-body">
          {/* Alliances */}
          <CollapsibleSection title="Alliances & Relationships" icon={Users} count={0} defaultOpen={true}>
            {alliance.allies.length > 0 && (
              <div className="country-profile-alliance-row">
                <span className="country-profile-alliance-label" style={{ color: '#22c55e' }}>Allies:</span>
                <span>{alliance.allies.join(', ')}</span>
              </div>
            )}
            {alliance.rivals.length > 0 && (
              <div className="country-profile-alliance-row">
                <span className="country-profile-alliance-label" style={{ color: '#ef4444' }}>Rivals:</span>
                <span>{alliance.rivals.join(', ')}</span>
              </div>
            )}
            {alliance.groups.length > 0 && (
              <div className="country-profile-alliance-row">
                <span className="country-profile-alliance-label" style={{ color: '#3b82f6' }}>Groups:</span>
                <span>{alliance.groups.join(', ')}</span>
              </div>
            )}
          </CollapsibleSection>

          {/* Active Conflicts */}
          <CollapsibleSection title="Active Conflicts" icon={Crosshair} count={countryConflicts.length} defaultOpen={countryConflicts.length > 0}>
            {countryConflicts.length === 0 ? (
              <div className="country-profile-empty">No active conflicts</div>
            ) : (
              countryConflicts.slice(0, 10).map((c, i) => (
                <div key={i} className="country-profile-item">
                  <span className={`severity-dot severity-${c.severity || 'medium'}`} />
                  <span className="country-profile-item-text">{c.title || c.name || 'Unknown'}</span>
                </div>
              ))
            )}
          </CollapsibleSection>

          {/* Missile Events */}
          <CollapsibleSection title="Missile Events" icon={AlertTriangle} count={countryMissiles.length}>
            {countryMissiles.length === 0 ? (
              <div className="country-profile-empty">No missile events</div>
            ) : (
              countryMissiles.slice(0, 10).map((m, i) => (
                <div key={i} className="country-profile-item">
                  <span className="severity-dot severity-high" />
                  <span className="country-profile-item-text">{m.title || 'Missile Event'}</span>
                </div>
              ))
            )}
          </CollapsibleSection>

          {/* Military Installations */}
          <CollapsibleSection title="Military Installations" icon={Building2} count={countryBases.length}>
            {countryBases.length === 0 ? (
              <div className="country-profile-empty">No tracked installations</div>
            ) : (
              countryBases.map((b, i) => (
                <div key={i} className="country-profile-item">
                  <span style={{ color: '#8b5cf6', fontSize: '11px', fontWeight: 600 }}>{b.type?.replace('_', ' ').toUpperCase()}</span>
                  <span className="country-profile-item-text">{b.name}{b.operator ? ` (${b.operator})` : ''}</span>
                </div>
              ))
            )}
          </CollapsibleSection>

          {/* Nuclear Facilities */}
          <CollapsibleSection title="Nuclear Facilities" icon={Atom} count={countryNuclear.length}>
            {countryNuclear.length === 0 ? (
              <div className="country-profile-empty">No nuclear facilities</div>
            ) : (
              countryNuclear.map((n, i) => (
                <div key={i} className="country-profile-item">
                  <span style={{ color: '#eab308', fontSize: '11px', fontWeight: 600 }}>{n.type?.replace('_', ' ').toUpperCase()}</span>
                  <span className="country-profile-item-text">{n.name} ({n.status})</span>
                </div>
              ))
            )}
          </CollapsibleSection>

          {/* Tech Infrastructure */}
          <CollapsibleSection title="Tech Infrastructure" icon={Zap} count={countryInfra.length}>
            {countryInfra.length === 0 ? (
              <div className="country-profile-empty">No infrastructure incidents</div>
            ) : (
              countryInfra.slice(0, 10).map((o, i) => (
                <div key={i} className="country-profile-item">
                  <span style={{ color: o.status === 'outage' ? '#ef4444' : '#f59e0b', fontSize: '11px', fontWeight: 600 }}>
                    {(o.status || 'reported').toUpperCase()}
                  </span>
                  <span className="country-profile-item-text">{o.title || 'Infrastructure incident'}</span>
                </div>
              ))
            )}
          </CollapsibleSection>

          {/* Recent News */}
          <CollapsibleSection title="Recent News" icon={Newspaper} count={countryNews.length}>
            {countryNews.length === 0 ? (
              <div className="country-profile-empty">No recent news</div>
            ) : (
              countryNews.slice(0, 8).map((n, i) => (
                <div key={i} className="country-profile-item">
                  <span className="country-profile-item-text">
                    {n.url ? <a href={n.url} target="_blank" rel="noopener noreferrer" style={{ color: '#93c5fd' }}>{n.title}</a> : n.title}
                  </span>
                </div>
              ))
            )}
          </CollapsibleSection>

          {/* OSINT Intelligence */}
          <CollapsibleSection title="OSINT Intelligence" icon={Globe} count={countryXIntel.length + countryTelegram.length + countryOsint.length}>
            {countryXIntel.length + countryTelegram.length + countryOsint.length === 0 ? (
              <div className="country-profile-empty">No OSINT intelligence</div>
            ) : (
              <>
                {countryXIntel.slice(0, 5).map((p, i) => (
                  <div key={`x-${i}`} className="country-profile-item">
                    <span style={{ color: '#1da1f2', fontSize: '10px', fontWeight: 600 }}>X</span>
                    <span className="country-profile-item-text">{p.text || p.title || ''}</span>
                  </div>
                ))}
                {countryTelegram.slice(0, 5).map((p, i) => (
                  <div key={`tg-${i}`} className="country-profile-item">
                    <span style={{ color: '#0088cc', fontSize: '10px', fontWeight: 600 }}>TG</span>
                    <span className="country-profile-item-text">{p.text || p.title || ''}</span>
                  </div>
                ))}
                {countryOsint.slice(0, 5).map((p, i) => (
                  <div key={`os-${i}`} className="country-profile-item">
                    <span style={{ color: '#a855f7', fontSize: '10px', fontWeight: 600 }}>INT</span>
                    <span className="country-profile-item-text">{p.text || p.title || ''}</span>
                  </div>
                ))}
              </>
            )}
          </CollapsibleSection>

          {/* Non-intrusive ad at bottom of profile */}
          <AdUnit format="rectangle" slot="country-profile" style={{ marginTop: '12px' }} />
        </div>
      </div>
    </div>
  );
}
