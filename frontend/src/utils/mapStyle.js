/**
 * Map style utilities for World Situation Monitor.
 * Provides icon creation, color constants, and GeoJSON conversion helpers.
 * All icons are created programmatically on canvas for WebGL rendering.
 */

// =============================================
// BASEMAP
// =============================================

export const DARK_BASEMAP_URL =
  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

// =============================================
// LAYER COLORS
// =============================================

export const LAYER_COLORS = {
  conflict: '#ef4444',
  missile: '#f97316',
  aircraft: '#06b6d4',
  naval: '#3b82f6',
  militaryBase: '#8b5cf6',
  nuclear: '#eab308',
  earthquake: '#f43f5e',
  weather: '#a855f7',
  hotspot: '#ef4444',
  waterway: '#0ea5e9',
  sanctions: '#f59e0b',
};

// =============================================
// SEVERITY COLORS
// =============================================

export const SEVERITY_COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#f59e0b',
  low: '#22c55e',
  info: '#3b82f6',
};

// =============================================
// ICON CREATION FUNCTIONS
// Canvas-based icon generation for WebGL markers
// =============================================

/**
 * Create a canvas-based aircraft icon (arrow/chevron shape).
 * Returns an ImageData-compatible object for map.addImage().
 */
export function createAircraftIcon(size = 24, color = '#06b6d4') {
  const canvas = document.createElement('canvas');
  const ratio = window.devicePixelRatio || 1;
  canvas.width = size * ratio;
  canvas.height = size * ratio;
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);

  const cx = size / 2;
  const cy = size / 2;

  // Aircraft arrow shape pointing up
  ctx.beginPath();
  ctx.moveTo(cx, cy - size * 0.42);       // nose
  ctx.lineTo(cx + size * 0.14, cy + size * 0.1);
  ctx.lineTo(cx + size * 0.38, cy + size * 0.15);  // right wing tip
  ctx.lineTo(cx + size * 0.12, cy + size * 0.22);
  ctx.lineTo(cx + size * 0.16, cy + size * 0.4);   // right tail
  ctx.lineTo(cx, cy + size * 0.3);                  // tail center
  ctx.lineTo(cx - size * 0.16, cy + size * 0.4);   // left tail
  ctx.lineTo(cx - size * 0.12, cy + size * 0.22);
  ctx.lineTo(cx - size * 0.38, cy + size * 0.15);  // left wing tip
  ctx.lineTo(cx - size * 0.14, cy + size * 0.1);
  ctx.closePath();

  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 4;
  ctx.fill();

  // Inner highlight
  ctx.shadowBlur = 0;
  ctx.fillStyle = 'rgba(255,255,255,0.25)';
  ctx.beginPath();
  ctx.moveTo(cx, cy - size * 0.3);
  ctx.lineTo(cx + size * 0.06, cy + size * 0.05);
  ctx.lineTo(cx - size * 0.06, cy + size * 0.05);
  ctx.closePath();
  ctx.fill();

  return {
    width: canvas.width,
    height: canvas.height,
    data: ctx.getImageData(0, 0, canvas.width, canvas.height).data,
  };
}

/**
 * Create a ship/naval icon (diamond with dot).
 */
export function createShipIcon(size = 20, color = '#3b82f6') {
  const canvas = document.createElement('canvas');
  const ratio = window.devicePixelRatio || 1;
  canvas.width = size * ratio;
  canvas.height = size * ratio;
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);

  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.38;

  // Diamond shape
  ctx.beginPath();
  ctx.moveTo(cx, cy - r);
  ctx.lineTo(cx + r * 0.7, cy);
  ctx.lineTo(cx, cy + r);
  ctx.lineTo(cx - r * 0.7, cy);
  ctx.closePath();

  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 4;
  ctx.fill();

  // Center dot
  ctx.shadowBlur = 0;
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.beginPath();
  ctx.arc(cx, cy, 2, 0, Math.PI * 2);
  ctx.fill();

  return {
    width: canvas.width,
    height: canvas.height,
    data: ctx.getImageData(0, 0, canvas.width, canvas.height).data,
  };
}

/**
 * Create a military base icon (star/pentagon shape).
 */
export function createBaseIcon(size = 22, color = '#8b5cf6') {
  const canvas = document.createElement('canvas');
  const ratio = window.devicePixelRatio || 1;
  canvas.width = size * ratio;
  canvas.height = size * ratio;
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);

  const cx = size / 2;
  const cy = size / 2;
  const outerR = size * 0.4;
  const innerR = size * 0.18;
  const points = 5;

  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const r = i % 2 === 0 ? outerR : innerR;
    const angle = (Math.PI * i) / points - Math.PI / 2;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();

  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 5;
  ctx.fill();

  return {
    width: canvas.width,
    height: canvas.height,
    data: ctx.getImageData(0, 0, canvas.width, canvas.height).data,
  };
}

/**
 * Create a nuclear hazard icon (trefoil simplified).
 */
export function createNuclearIcon(size = 24, color = '#eab308') {
  const canvas = document.createElement('canvas');
  const ratio = window.devicePixelRatio || 1;
  canvas.width = size * ratio;
  canvas.height = size * ratio;
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);

  const cx = size / 2;
  const cy = size / 2;

  // Outer circle
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.4, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 6;
  ctx.fill();

  // Inner dark circle
  ctx.shadowBlur = 0;
  ctx.fillStyle = '#0a0e17';
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.28, 0, Math.PI * 2);
  ctx.fill();

  // Trefoil blades (three segments)
  const bladeAngles = [0, (2 * Math.PI) / 3, (4 * Math.PI) / 3];
  ctx.fillStyle = color;
  bladeAngles.forEach((startAngle) => {
    ctx.beginPath();
    ctx.arc(cx, cy, size * 0.36, startAngle - 0.4, startAngle + 0.4);
    ctx.arc(cx, cy, size * 0.16, startAngle + 0.4, startAngle - 0.4, true);
    ctx.closePath();
    ctx.fill();
  });

  // Center dot
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.08, 0, Math.PI * 2);
  ctx.fill();

  return {
    width: canvas.width,
    height: canvas.height,
    data: ctx.getImageData(0, 0, canvas.width, canvas.height).data,
  };
}

/**
 * Create a conflict/explosion marker.
 */
export function createConflictIcon(size = 22, color = '#ef4444') {
  const canvas = document.createElement('canvas');
  const ratio = window.devicePixelRatio || 1;
  canvas.width = size * ratio;
  canvas.height = size * ratio;
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);

  const cx = size / 2;
  const cy = size / 2;

  // Burst/starburst shape
  const points = 8;
  const outerR = size * 0.42;
  const innerR = size * 0.22;

  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const r = i % 2 === 0 ? outerR : innerR;
    const angle = (Math.PI * i) / points - Math.PI / 2;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();

  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 6;
  ctx.fill();

  // Inner glow
  ctx.shadowBlur = 0;
  ctx.fillStyle = 'rgba(255,255,255,0.3)';
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.12, 0, Math.PI * 2);
  ctx.fill();

  return {
    width: canvas.width,
    height: canvas.height,
    data: ctx.getImageData(0, 0, canvas.width, canvas.height).data,
  };
}

/**
 * Create a missile icon (elongated diamond with trail).
 */
export function createMissileIcon(size = 20, color = '#f97316') {
  const canvas = document.createElement('canvas');
  const ratio = window.devicePixelRatio || 1;
  canvas.width = size * ratio;
  canvas.height = size * ratio;
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);

  const cx = size / 2;
  const cy = size / 2;

  // Elongated diamond
  ctx.beginPath();
  ctx.moveTo(cx, cy - size * 0.4);
  ctx.lineTo(cx + size * 0.15, cy);
  ctx.lineTo(cx, cy + size * 0.4);
  ctx.lineTo(cx - size * 0.15, cy);
  ctx.closePath();

  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 5;
  ctx.fill();

  // Highlight streak
  ctx.shadowBlur = 0;
  ctx.strokeStyle = 'rgba(255,255,255,0.4)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(cx, cy - size * 0.3);
  ctx.lineTo(cx, cy + size * 0.1);
  ctx.stroke();

  return {
    width: canvas.width,
    height: canvas.height,
    data: ctx.getImageData(0, 0, canvas.width, canvas.height).data,
  };
}

/**
 * Create a weather icon (cloud shape).
 */
export function createWeatherIcon(size = 20, color = '#a855f7') {
  const canvas = document.createElement('canvas');
  const ratio = window.devicePixelRatio || 1;
  canvas.width = size * ratio;
  canvas.height = size * ratio;
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);

  const cx = size / 2;
  const cy = size / 2;

  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 4;

  // Simple cloud using overlapping circles
  ctx.beginPath();
  ctx.arc(cx - 2, cy + 1, size * 0.2, 0, Math.PI * 2);
  ctx.arc(cx + 2, cy + 1, size * 0.22, 0, Math.PI * 2);
  ctx.arc(cx, cy - 2, size * 0.24, 0, Math.PI * 2);
  ctx.fill();

  return {
    width: canvas.width,
    height: canvas.height,
    data: ctx.getImageData(0, 0, canvas.width, canvas.height).data,
  };
}

/**
 * Create an animated pulsing dot canvas image.
 * Returns an object compatible with map.addImage() with animation support.
 */
export function createPulsingDot(map, size = 100, color = [59, 130, 246]) {
  return {
    width: size,
    height: size,
    data: new Uint8Array(size * size * 4),
    context: null,

    onAdd() {
      const canvas = document.createElement('canvas');
      canvas.width = this.width;
      canvas.height = this.height;
      this.context = canvas.getContext('2d');
    },

    render() {
      const duration = 1500;
      const t = (performance.now() % duration) / duration;
      const radius = (size / 2) * 0.3;
      const outerRadius = (size / 2) * 0.6 * t + radius;
      const ctx = this.context;

      if (!ctx) return false;

      ctx.clearRect(0, 0, this.width, this.height);

      // Outer pulsing ring
      ctx.beginPath();
      ctx.arc(this.width / 2, this.height / 2, outerRadius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${1 - t})`;
      ctx.fill();

      // Inner solid dot
      ctx.beginPath();
      ctx.arc(this.width / 2, this.height / 2, radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, 1)`;
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.lineWidth = 2;
      ctx.fill();
      ctx.stroke();

      this.data = ctx.getImageData(0, 0, this.width, this.height).data;

      map.triggerRepaint();
      return true;
    },
  };
}

// =============================================
// GEOJSON CONVERSION HELPERS
// =============================================

/**
 * Convert an array of conflict objects to GeoJSON FeatureCollection.
 */
export function conflictsToGeoJSON(conflicts) {
  return {
    type: 'FeatureCollection',
    features: (conflicts || [])
      .filter((c) => c.lat != null && c.lon != null)
      .map((c) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [c.lon, c.lat],
        },
        properties: {
          id: c.id,
          name: c.name || c.title || 'Unknown Conflict',
          title: c.name || c.title || 'Unknown Conflict',
          type: 'conflict',
          intensity: c.intensity || c.severity || 'low',
          parties: Array.isArray(c.parties) ? c.parties.join(', ') : '',
          description: c.description || '',
          radius: c.radius || 10,
          timestamp: c.last_updated || c.timestamp || '',
        },
      })),
  };
}

/**
 * Convert aircraft array to GeoJSON FeatureCollection.
 */
export function aircraftToGeoJSON(aircraft) {
  return {
    type: 'FeatureCollection',
    features: (aircraft || [])
      .filter((a) => a.lat != null && a.lon != null)
      .map((a) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [a.lon, a.lat],
        },
        properties: {
          icao24: a.icao24,
          callsign: (a.callsign || '').trim(),
          altitude: a.altitude || a.baro_altitude || 0,
          velocity: a.velocity || 0,
          heading: a.heading || 0,
          on_ground: a.on_ground || false,
          origin_country: a.origin_country || '',
          squawk: a.squawk || '',
          type: 'aircraft',
        },
      })),
  };
}

/**
 * Convert missile events to GeoJSON FeatureCollection.
 * Creates both launch and target point features.
 */
export function missilesToGeoJSON(missiles) {
  const features = [];

  (missiles || []).forEach((m) => {
    if (m.launch_lat != null && m.launch_lon != null) {
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [m.launch_lon, m.launch_lat],
        },
        properties: {
          id: m.id,
          title: m.title || 'Missile Event',
          type: 'missile_launch',
          missile_type: m.missile_type || 'unknown',
          status: m.status || 'reported',
          description: m.description || '',
          source: m.source || '',
          timestamp: m.timestamp || '',
        },
      });
    }

    if (m.target_lat != null && m.target_lon != null) {
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [m.target_lon, m.target_lat],
        },
        properties: {
          id: m.id + '_target',
          title: m.title || 'Missile Target',
          type: 'missile_target',
          missile_type: m.missile_type || 'unknown',
          status: m.status || 'reported',
          description: m.description || '',
          source: m.source || '',
          timestamp: m.timestamp || '',
        },
      });
    }
  });

  return { type: 'FeatureCollection', features };
}

/**
 * Convert missile events to GeoJSON LineString FeatureCollection for arcs.
 */
export function missileArcsToGeoJSON(missiles) {
  return {
    type: 'FeatureCollection',
    features: (missiles || [])
      .filter(
        (m) =>
          m.launch_lat != null &&
          m.launch_lon != null &&
          m.target_lat != null &&
          m.target_lon != null
      )
      .map((m) => {
        const points = generateArcPoints(
          [m.launch_lon, m.launch_lat],
          [m.target_lon, m.target_lat],
          30
        );
        return {
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: points,
          },
          properties: {
            id: m.id,
            missile_type: m.missile_type || 'unknown',
            status: m.status || 'reported',
          },
        };
      }),
  };
}

/**
 * Generate arc points between two coordinates (great circle approximation).
 */
export function generateArcPoints(start, end, numPoints = 30) {
  const points = [];
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  const dist = Math.sqrt(dx * dx + dy * dy);

  for (let i = 0; i <= numPoints; i++) {
    const t = i / numPoints;
    const lng = start[0] + dx * t;
    const lat = start[1] + dy * t;
    // Add height curve for arc effect
    const arcHeight = Math.sin(t * Math.PI) * dist * 0.15;
    points.push([lng, lat + arcHeight]);
  }

  return points;
}

/**
 * Convert earthquake data to GeoJSON FeatureCollection.
 */
export function earthquakesToGeoJSON(earthquakes) {
  return {
    type: 'FeatureCollection',
    features: (earthquakes || [])
      .filter((e) => e.lat != null && e.lon != null)
      .map((e) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [e.lon, e.lat],
        },
        properties: {
          id: e.id,
          title: e.title || e.event || 'Earthquake',
          type: 'earthquake',
          magnitude: e.metadata?.mag || e.metadata?.magnitude || 0,
          depth: e.metadata?.depth || 0,
          severity: e.severity || 'low',
          description: e.description || '',
          timestamp: e.timestamp || '',
        },
      })),
  };
}

/**
 * Convert weather data to GeoJSON FeatureCollection.
 */
export function weatherToGeoJSON(weather) {
  return {
    type: 'FeatureCollection',
    features: (weather || [])
      .filter((w) => w.lat != null && w.lon != null)
      .map((w) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [w.lon, w.lat],
        },
        properties: {
          id: w.id,
          city: w.city || '',
          title: w.city || 'Weather',
          type: 'weather',
          event: w.event || '',
          severity: w.severity || 'info',
          temperature: w.temperature,
          wind_speed: w.wind_speed,
          weather_code: w.weather_code,
          description: w.description || '',
        },
      })),
  };
}

/**
 * Convert military bases to GeoJSON FeatureCollection.
 */
export function militaryBasesToGeoJSON(bases) {
  return {
    type: 'FeatureCollection',
    features: (bases || [])
      .filter((b) => b.lat != null && b.lon != null)
      .map((b) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [b.lon, b.lat],
        },
        properties: {
          id: b.id,
          name: b.name,
          title: b.name,
          type: 'military_base',
          base_type: b.type || '',
          country: b.country || '',
          branch: b.branch || '',
          status: b.status || 'active',
          operator: b.operator || '',
          description: b.description || '',
        },
      })),
  };
}

/**
 * Convert nuclear sites to GeoJSON FeatureCollection.
 */
export function nuclearSitesToGeoJSON(sites) {
  return {
    type: 'FeatureCollection',
    features: (sites || [])
      .filter((s) => s.lat != null && s.lon != null)
      .map((s) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [s.lon, s.lat],
        },
        properties: {
          id: s.id,
          name: s.name,
          title: s.name,
          type: 'nuclear',
          site_type: s.type || '',
          country: s.country || '',
          status: s.status || 'active',
          description: s.description || '',
        },
      })),
  };
}

/**
 * Convert waterways to GeoJSON FeatureCollection.
 * Uses LineString if coordinates array is provided, otherwise Point.
 */
export function waterwaysToGeoJSON(waterways) {
  return {
    type: 'FeatureCollection',
    features: (waterways || []).map((w) => {
      const hasCoords =
        Array.isArray(w.coordinates) && w.coordinates.length >= 2;

      if (hasCoords) {
        return {
          type: 'Feature',
          geometry: {
            type: 'LineString',
            // Backend sends [lat, lon] pairs; convert to [lon, lat]
            coordinates: w.coordinates.map((c) =>
              Array.isArray(c) && c.length >= 2 ? [c[1], c[0]] : c
            ),
          },
          properties: {
            id: w.id,
            name: w.name,
            title: w.name,
            type: 'waterway',
            waterway_type: w.type || 'strait',
            description: w.description || '',
            daily_traffic: w.daily_traffic || '',
            strategic_importance: w.strategic_importance || 'high',
            controlled_by: w.controlled_by || '',
          },
        };
      }

      // Fallback to point
      return {
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [w.lon || 0, w.lat || 0],
        },
        properties: {
          id: w.id,
          name: w.name,
          title: w.name,
          type: 'waterway',
          waterway_type: w.type || 'strait',
          description: w.description || '',
          daily_traffic: w.daily_traffic || '',
          strategic_importance: w.strategic_importance || 'high',
          controlled_by: w.controlled_by || '',
        },
      };
    }),
  };
}

/**
 * Convert vessels to GeoJSON FeatureCollection.
 */
export function vesselsToGeoJSON(vessels) {
  return {
    type: 'FeatureCollection',
    features: (vessels || [])
      .filter((v) => v.lat != null && v.lon != null && (v.lat !== 0 || v.lon !== 0))
      .map((v) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [v.lon, v.lat],
        },
        properties: {
          mmsi: v.mmsi,
          name: v.name || 'Unknown Vessel',
          title: v.name || v.mmsi,
          type: 'vessel',
          vessel_type: v.vessel_type || '',
          flag: v.flag || '',
          speed: v.speed || 0,
          course: v.course || 0,
          destination: v.destination || '',
          description: `${v.vessel_type || 'Vessel'} | Flag: ${v.flag || 'Unknown'} | Dest: ${v.destination || 'N/A'}`,
        },
      })),
  };
}

/**
 * Empty GeoJSON FeatureCollection.
 */
export const EMPTY_GEOJSON = {
  type: 'FeatureCollection',
  features: [],
};
