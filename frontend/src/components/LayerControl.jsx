/**
 * LayerControl Component - World Situation Monitor
 * Left sidebar with categorized layer toggles.
 */

import React, { useState } from 'react';
import {
  Layers,
  ChevronDown,
  X,
  Shield,
  Plane,
  Crosshair,
  Radio,
  Anchor,
  Building2,
  Atom,
  Navigation,
  Map,
  Cloud,
  Flame,
  Zap,
  AlertTriangle,
} from 'lucide-react';

// Layer category definitions with their layers
const LAYER_CATEGORIES = [
  {
    id: 'security',
    name: 'Security',
    color: '#ef4444',
    layers: [
      { id: 'conflicts', name: 'Active Conflicts', icon: Crosshair, color: '#ef4444' },
      { id: 'missiles', name: 'Missile Events', icon: Radio, color: '#f97316' },
      { id: 'hotspots', name: 'Hotspot Zones', icon: Flame, color: '#ef4444' },
      { id: 'cyberAttacks', name: 'Cyber Attacks', icon: Zap, color: '#a855f7' },
    ],
  },
  {
    id: 'military',
    name: 'Military',
    color: '#8b5cf6',
    layers: [
      { id: 'militaryAircraft', name: 'Fighter Jets / Military', icon: Plane, color: '#ef4444' },
      { id: 'militaryBases', name: 'Military Bases', icon: Building2, color: '#8b5cf6' },
    ],
  },
  {
    id: 'tracking',
    name: 'Tracking',
    color: '#06b6d4',
    layers: [
      { id: 'commercialAircraft', name: 'Commercial Flights', icon: Plane, color: '#06b6d4' },
      { id: 'naval', name: 'Naval Vessels', icon: Anchor, color: '#3b82f6' },
    ],
  },
  {
    id: 'strategic',
    name: 'Strategic',
    color: '#eab308',
    layers: [
      { id: 'nuclearSites', name: 'Nuclear Sites', icon: Atom, color: '#eab308' },
      { id: 'waterways', name: 'Strategic Waterways', icon: Navigation, color: '#0ea5e9' },
      { id: 'sanctions', name: 'Sanctions', icon: Map, color: '#f59e0b' },
    ],
  },
  {
    id: 'natural',
    name: 'Natural',
    color: '#22c55e',
    layers: [
      { id: 'earthquakes', name: 'Earthquakes', icon: AlertTriangle, color: '#f43f5e' },
      { id: 'weather', name: 'Weather Alerts', icon: Cloud, color: '#a855f7' },
    ],
  },
];

export default function LayerControl({
  activeLayers,
  onToggleLayer,
  onShowAll,
  onClearAll,
  layerCounts,
  isOpen,
  onTogglePanel,
}) {
  const [expandedCategories, setExpandedCategories] = useState(
    new Set(['security', 'military', 'tracking', 'strategic', 'natural'])
  );

  const toggleCategory = (catId) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(catId)) {
        next.delete(catId);
      } else {
        next.add(catId);
      }
      return next;
    });
  };

  const toggleAllInCategory = (category) => {
    const allActive = category.layers.every((l) => activeLayers.has(l.id));
    category.layers.forEach((l) => {
      if (allActive && activeLayers.has(l.id)) {
        onToggleLayer(l.id);
      } else if (!allActive && !activeLayers.has(l.id)) {
        onToggleLayer(l.id);
      }
    });
  };

  return (
    <>
      {/* Toggle button when panel is collapsed */}
      <button
        className={`layer-control-toggle ${isOpen ? 'hidden' : ''}`}
        onClick={onTogglePanel}
        title="Show layers"
      >
        <Layers size={16} />
      </button>

      {/* Layer panel */}
      <div className={`layer-control glass-panel ${isOpen ? '' : 'collapsed'}`}>
        {/* Header */}
        <div className="layer-panel-header">
          <h2>Layers</h2>
          <div className="layer-panel-actions">
            <button className="layer-panel-btn" onClick={onShowAll}>
              All
            </button>
            <button className="layer-panel-btn" onClick={onClearAll}>
              None
            </button>
            <button className="layer-panel-close" onClick={onTogglePanel} title="Hide panel">
              <X size={14} />
            </button>
          </div>
        </div>

        {/* Layer categories */}
        <div className="layer-panel-body">
          {LAYER_CATEGORIES.map((category) => {
            const isExpanded = expandedCategories.has(category.id);
            const activeCount = category.layers.filter((l) =>
              activeLayers.has(l.id)
            ).length;
            const totalCount = category.layers.length;

            return (
              <div key={category.id} className="layer-category">
                {/* Category header */}
                <div
                  className="layer-category-header"
                  onClick={() => toggleCategory(category.id)}
                >
                  <div className="layer-category-left">
                    <div
                      className="layer-category-icon"
                      style={{ backgroundColor: category.color }}
                    />
                    <span className="layer-category-name">
                      {category.name}
                    </span>
                    <span
                      style={{
                        fontSize: 9,
                        color: 'var(--text-dim)',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {activeCount}/{totalCount}
                    </span>
                  </div>
                  <ChevronDown
                    size={14}
                    className={`layer-category-chevron ${isExpanded ? 'open' : ''}`}
                  />
                </div>

                {/* Layer items */}
                <div
                  className={`layer-items ${isExpanded ? '' : 'collapsed'}`}
                  style={{ maxHeight: isExpanded ? category.layers.length * 40 + 'px' : 0 }}
                >
                  {category.layers.map((layer) => {
                    const IconComp = layer.icon;
                    const isActive = activeLayers.has(layer.id);
                    const count = layerCounts[layer.id] || 0;

                    return (
                      <div
                        key={layer.id}
                        className="layer-item"
                        onClick={() => onToggleLayer(layer.id)}
                      >
                        <div
                          className="layer-color-dot"
                          style={{
                            backgroundColor: isActive ? layer.color : 'transparent',
                            borderColor: layer.color,
                            color: layer.color,
                            border: `1.5px solid ${isActive ? layer.color : 'var(--text-dim)'}`,
                          }}
                        />
                        <div className="layer-item-info">
                          <div
                            className="layer-item-name"
                            style={{
                              color: isActive
                                ? 'var(--text-primary)'
                                : 'var(--text-muted)',
                            }}
                          >
                            {layer.name}
                          </div>
                          {count > 0 && (
                            <div className="layer-item-count">{count}</div>
                          )}
                        </div>
                        <label
                          className="toggle-switch"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="checkbox"
                            checked={isActive}
                            onChange={() => onToggleLayer(layer.id)}
                          />
                          <span className="toggle-slider" />
                        </label>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
