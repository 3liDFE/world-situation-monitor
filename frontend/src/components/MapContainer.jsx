/**
 * MapContainer Component - World Situation Monitor
 * The core map display using MapLibre GL JS for high-performance WebGL rendering.
 * All markers use GeoJSON sources and map layers -- NO DOM markers.
 */

import React, { useEffect, useRef, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import EventPopup from './EventPopup';
import {
  DARK_BASEMAP_URL,
  LAYER_COLORS,
  EMPTY_GEOJSON,
  createAircraftIcon,
  createMilitaryAircraftIcon,
  createShipIcon,
  createBaseIcon,
  createNuclearIcon,
  createConflictIcon,
  createMissileIcon,
  createWeatherIcon,
  createPulsingDot,
  conflictsToGeoJSON,
  aircraftToGeoJSON,
  missilesToGeoJSON,
  missileArcsToGeoJSON,
  earthquakesToGeoJSON,
  weatherToGeoJSON,
  militaryBasesToGeoJSON,
  nuclearSitesToGeoJSON,
  waterwaysToGeoJSON,
  vesselsToGeoJSON,
  infraToGeoJSON,
  createInfraIcon,
} from '../utils/mapStyle';

// Layer ID constants for source and layer management
const SOURCES = {
  conflicts: 'conflicts-source',
  missiles: 'missiles-source',
  missileArcs: 'missile-arcs-source',
  commercialAircraft: 'commercial-aircraft-source',
  militaryAircraft: 'military-aircraft-source',
  aircraftTrails: 'aircraft-trails-source',
  vessels: 'vessels-source',
  earthquakes: 'earthquakes-source',
  weather: 'weather-source',
  militaryBases: 'military-bases-source',
  nuclearSites: 'nuclear-sites-source',
  waterways: 'waterways-source',
  hotspots: 'hotspots-source',
  infrastructure: 'infrastructure-source',
  countryBoundaries: 'country-boundaries-source',
  correlationHighlight: 'correlation-highlight-source',
};

const LAYERS = {
  conflictsGlow: 'conflicts-glow-layer',
  conflictsCircle: 'conflicts-circle-layer',
  conflictsIcon: 'conflicts-icon-layer',
  missilePoints: 'missiles-points-layer',
  missileArcs: 'missile-arcs-layer',
  missileIcons: 'missiles-icon-layer',
  aircraftTrails: 'aircraft-trails-layer',
  commercialAircraftIcon: 'commercial-aircraft-icon-layer',
  commercialAircraftLabels: 'commercial-aircraft-labels-layer',
  militaryAircraftIcon: 'military-aircraft-icon-layer',
  militaryAircraftLabels: 'military-aircraft-labels-layer',
  vesselsIcon: 'vessels-icon-layer',
  vesselsLabels: 'vessels-labels-layer',
  earthquakeCircle: 'earthquakes-circle-layer',
  earthquakeGlow: 'earthquakes-glow-layer',
  weatherIcon: 'weather-icon-layer',
  weatherLabels: 'weather-labels-layer',
  militaryBasesIcon: 'military-bases-icon-layer',
  militaryBasesLabels: 'military-bases-labels-layer',
  nuclearSitesIcon: 'nuclear-sites-icon-layer',
  nuclearSitesGlow: 'nuclear-sites-glow-layer',
  waterwaysLine: 'waterways-line-layer',
  waterwaysLabel: 'waterways-label-layer',
  hotspotHeat: 'hotspots-heatmap-layer',
  infraIcon: 'infrastructure-icon-layer',
  infraLabels: 'infrastructure-labels-layer',
  infraGlow: 'infrastructure-glow-layer',
  countryFill: 'country-fill-layer',
  countryHighlight: 'country-highlight-layer',
  countryHighlightOutline: 'country-highlight-outline-layer',
  correlationCircle: 'correlation-circle-layer',
  correlationLine: 'correlation-line-layer',
};

// Map layer IDs to the parent toggle layer names
const LAYER_GROUP_MAP = {
  conflicts: [LAYERS.conflictsGlow, LAYERS.conflictsCircle, LAYERS.conflictsIcon],
  missiles: [LAYERS.missilePoints, LAYERS.missileArcs, LAYERS.missileIcons],
  commercialAircraft: [LAYERS.commercialAircraftIcon, LAYERS.commercialAircraftLabels, LAYERS.aircraftTrails],
  militaryAircraft: [LAYERS.militaryAircraftIcon, LAYERS.militaryAircraftLabels],
  naval: [LAYERS.vesselsIcon, LAYERS.vesselsLabels],
  earthquakes: [LAYERS.earthquakeCircle, LAYERS.earthquakeGlow],
  weather: [LAYERS.weatherIcon, LAYERS.weatherLabels],
  militaryBases: [LAYERS.militaryBasesIcon, LAYERS.militaryBasesLabels],
  nuclearSites: [LAYERS.nuclearSitesIcon, LAYERS.nuclearSitesGlow],
  waterways: [LAYERS.waterwaysLine, LAYERS.waterwaysLabel],
  hotspots: [LAYERS.hotspotHeat],
  infrastructure: [LAYERS.infraIcon, LAYERS.infraLabels, LAYERS.infraGlow],
};

export default function MapContainer({
  activeLayers,
  conflicts,
  aircraft,
  missiles,
  earthquakes,
  weather,
  militaryBases,
  nuclearSites,
  waterways,
  vessels,
  selectedEvent,
  onEventClick,
  onMapReady,
  onCountrySelect,
  initialView,
  infraOutages,
  dataCenters,
  underseaCables,
  eventChains,
  selectedChain,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const readyRef = useRef(false);
  const popupRef = useRef(null);

  // Animation refs for smooth aircraft movement and missile arcs
  const aircraftHistoryRef = useRef({}); // { icao24: [[lon,lat], [lon,lat], ...] }
  const animFrameRef = useRef(null);
  const prevAircraftRef = useRef({}); // previous positions for interpolation
  const interpStartRef = useRef(0); // timestamp of last data update
  const pendingUpdatesRef = useRef({}); // queued source updates before map ready

  // =============================================
  // MAP INITIALIZATION
  // =============================================

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: DARK_BASEMAP_URL,
      center: initialView?.center || [47, 29],
      zoom: initialView?.zoom || 4,
      minZoom: 1.5,
      maxZoom: 18,
      attributionControl: true,
      antialias: true,
      fadeDuration: 100,
    });

    mapRef.current = map;

    // Navigation controls
    map.addControl(new maplibregl.NavigationControl({ showCompass: true, showZoom: true }), 'bottom-right');
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 150 }), 'bottom-left');
    map.addControl(new maplibregl.FullscreenControl(), 'bottom-right');

    // Geolocate control
    map.addControl(
      new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: false },
        trackUserLocation: false,
      }),
      'bottom-right'
    );

    map.on('load', () => {
      readyRef.current = true;
      addCustomImages(map);
      addAllSources(map);
      addAllLayers(map);

      // Flush any data updates that arrived before the map was ready
      const pending = pendingUpdatesRef.current;
      Object.entries(pending).forEach(([sid, geojson]) => {
        const source = map.getSource(sid);
        if (source) {
          source.setData(geojson);
        }
      });
      pendingUpdatesRef.current = {};

      // Load country boundaries for click detection
      fetch('https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson')
        .then(r => r.json())
        .then(geojson => {
          const src = map.getSource(SOURCES.countryBoundaries);
          if (src) src.setData(geojson);
        })
        .catch(() => {}); // Non-critical

      if (onMapReady) {
        onMapReady(map);
      }
    });

    // Click handler for interactive layers
    const interactiveLayers = [
      LAYERS.conflictsIcon,
      LAYERS.conflictsCircle,
      LAYERS.commercialAircraftIcon,
      LAYERS.militaryAircraftIcon,
      LAYERS.missileIcons,
      LAYERS.missilePoints,
      LAYERS.earthquakeCircle,
      LAYERS.vesselsIcon,
      LAYERS.militaryBasesIcon,
      LAYERS.nuclearSitesIcon,
      LAYERS.weatherIcon,
      LAYERS.waterwaysLine,
      LAYERS.infraIcon,
    ];

    interactiveLayers.forEach((layerId) => {
      map.on('click', layerId, (e) => {
        if (e.features && e.features.length > 0) {
          const feature = e.features[0];
          const coords = e.lngLat;

          // Remove existing popup
          if (popupRef.current) {
            popupRef.current.remove();
          }

          const props = feature.properties;
          const popup = new maplibregl.Popup({
            closeButton: true,
            closeOnClick: true,
            maxWidth: '320px',
            offset: 15,
          });

          const popupHTML = buildPopupHTML(props);
          popup.setLngLat(coords).setHTML(popupHTML).addTo(map);
          popupRef.current = popup;

          if (onEventClick) {
            onEventClick({ ...props, lng: coords.lng, lat: coords.lat });
          }
        }
      });

      // Cursor change on hover
      map.on('mouseenter', layerId, () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', layerId, () => {
        map.getCanvas().style.cursor = '';
      });
    });

    // Aircraft callsign tooltip on hover (works for both commercial and military)
    let hoverPopup = null;
    const aircraftHoverLayers = [LAYERS.commercialAircraftIcon, LAYERS.militaryAircraftIcon];
    aircraftHoverLayers.forEach((layerId) => {
      const isMilLayer = layerId === LAYERS.militaryAircraftIcon;
      const hoverColor = isMilLayer ? '#ef4444' : '#06b6d4';
      map.on('mouseenter', layerId, (e) => {
        if (e.features && e.features.length > 0) {
          const props = e.features[0].properties;
          const callsign = props.callsign || props.icao24 || '';
          if (callsign) {
            if (hoverPopup) { hoverPopup.remove(); hoverPopup = null; }
            hoverPopup = new maplibregl.Popup({
              closeButton: false,
              closeOnClick: false,
              offset: 12,
              className: 'aircraft-hover-popup',
            });
            const acType = props.aircraft_type && props.aircraft_type !== 'Unknown' ? props.aircraft_type : '';
            const milTag = isMilLayer ? '<br/><span style="color:#ef4444;font-weight:bold;font-size:10px">MILITARY</span>' : '';
            hoverPopup
              .setLngLat(e.lngLat)
              .setHTML(
                `<div style="padding:4px 8px;font-size:11px;font-family:monospace;color:${hoverColor};">${callsign}${
                  props.origin_country ? ` (${props.origin_country})` : ''
                }${acType ? `<br/><span style="color:#f59e0b;font-size:10px">${acType}</span>` : ''}${milTag}</div>`
              )
              .addTo(map);
          }
        }
      });
      map.on('mouseleave', layerId, () => {
        if (hoverPopup) {
          hoverPopup.remove();
          hoverPopup = null;
        }
      });
    });

    // Country boundary click handler
    const COUNTRY_NAME_MAP = {
      'United Arab Emirates': 'UAE',
      'Syrian Arab Republic': 'Syria',
      'Russian Federation': 'Russia',
      "Iran (Islamic Republic of)": 'Iran',
      'Republic of Turkey': 'Turkey',
      'Hashemite Kingdom of Jordan': 'Jordan',
      'State of Palestine': 'Palestine',
    };
    map.on('click', LAYERS.countryFill, (e) => {
      if (e.features && e.features.length > 0 && onCountrySelect) {
        const rawName = e.features[0].properties.ADMIN || e.features[0].properties.name || '';
        const countryName = COUNTRY_NAME_MAP[rawName] || rawName;
        onCountrySelect(countryName);
        // Highlight the selected country
        map.setFilter(LAYERS.countryHighlight, ['==', ['get', 'ADMIN'], e.features[0].properties.ADMIN]);
        map.setFilter(LAYERS.countryHighlightOutline, ['==', ['get', 'ADMIN'], e.features[0].properties.ADMIN]);
      }
    });
    map.on('mouseenter', LAYERS.countryFill, () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', LAYERS.countryFill, () => {
      map.getCanvas().style.cursor = '';
    });

    return () => {
      readyRef.current = false;
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      if (popupRef.current) popupRef.current.remove();
      if (hoverPopup) hoverPopup.remove();
      map.remove();
      mapRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // =============================================
  // CUSTOM ICON IMAGES
  // =============================================

  function addCustomImages(map) {
    const icons = [
      { id: 'aircraft-icon', fn: createAircraftIcon, args: [28, LAYER_COLORS.commercialAircraft] },
      { id: 'military-aircraft-icon', fn: createMilitaryAircraftIcon, args: [28, '#ef4444'] },
      { id: 'ship-icon', fn: createShipIcon, args: [22, LAYER_COLORS.naval] },
      { id: 'base-icon', fn: createBaseIcon, args: [24, LAYER_COLORS.militaryBase] },
      { id: 'nuclear-icon', fn: createNuclearIcon, args: [26, LAYER_COLORS.nuclear] },
      { id: 'conflict-icon', fn: createConflictIcon, args: [24, LAYER_COLORS.conflict] },
      { id: 'missile-icon', fn: createMissileIcon, args: [22, LAYER_COLORS.missile] },
      { id: 'weather-icon', fn: createWeatherIcon, args: [22, LAYER_COLORS.weather] },
      { id: 'infra-icon', fn: createInfraIcon, args: [24, LAYER_COLORS.infrastructure] },
    ];

    icons.forEach(({ id, fn, args }) => {
      const img = fn(...args);
      if (!map.hasImage(id)) {
        map.addImage(id, img, { pixelRatio: window.devicePixelRatio || 1 });
      }
    });

    // Pulsing dot for real-time markers
    const pulsingDot = createPulsingDot(map, 80, [239, 68, 68]);
    if (!map.hasImage('pulsing-dot')) {
      map.addImage('pulsing-dot', pulsingDot, { pixelRatio: 2 });
    }
  }

  // =============================================
  // ADD ALL SOURCES (empty initially)
  // =============================================

  function addAllSources(map) {
    Object.values(SOURCES).forEach((sourceId) => {
      if (!map.getSource(sourceId)) {
        map.addSource(sourceId, {
          type: 'geojson',
          data: EMPTY_GEOJSON,
        });
      }
    });
  }

  // =============================================
  // ADD ALL LAYERS
  // =============================================

  function addAllLayers(map) {
    // --- HOTSPOT HEATMAP (below everything) ---
    if (!map.getLayer(LAYERS.hotspotHeat)) {
      map.addLayer({
        id: LAYERS.hotspotHeat,
        type: 'heatmap',
        source: SOURCES.hotspots,
        paint: {
          'heatmap-weight': [
            'interpolate', ['linear'],
            ['get', 'radius'],
            0, 0.2,
            50, 1,
          ],
          'heatmap-intensity': 0.6,
          'heatmap-color': [
            'interpolate', ['linear'], ['heatmap-density'],
            0, 'rgba(0,0,0,0)',
            0.2, 'rgba(239,68,68,0.1)',
            0.4, 'rgba(239,68,68,0.25)',
            0.6, 'rgba(249,115,22,0.4)',
            0.8, 'rgba(245,158,11,0.6)',
            1, 'rgba(239,68,68,0.8)',
          ],
          'heatmap-radius': 40,
          'heatmap-opacity': 0.7,
        },
      });
    }

    // --- WATERWAYS ---
    if (!map.getLayer(LAYERS.waterwaysLine)) {
      map.addLayer({
        id: LAYERS.waterwaysLine,
        type: 'line',
        source: SOURCES.waterways,
        filter: ['==', '$type', 'LineString'],
        paint: {
          'line-color': LAYER_COLORS.waterway,
          'line-width': 3,
          'line-opacity': 0.7,
          'line-dasharray': [2, 1],
        },
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
        },
      });
    }

    if (!map.getLayer(LAYERS.waterwaysLabel)) {
      map.addLayer({
        id: LAYERS.waterwaysLabel,
        type: 'symbol',
        source: SOURCES.waterways,
        layout: {
          'text-field': ['get', 'name'],
          'text-size': 11,
          'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
          'text-offset': [0, 1.2],
          'text-anchor': 'top',
          'symbol-placement': 'point',
        },
        paint: {
          'text-color': LAYER_COLORS.waterway,
          'text-halo-color': '#0a0e17',
          'text-halo-width': 1.5,
          'text-opacity': 0.9,
        },
      });
    }

    // --- CONFLICTS ---
    if (!map.getLayer(LAYERS.conflictsGlow)) {
      map.addLayer({
        id: LAYERS.conflictsGlow,
        type: 'circle',
        source: SOURCES.conflicts,
        paint: {
          'circle-radius': [
            'interpolate', ['linear'],
            ['get', 'radius'],
            1, 20,
            10, 35,
            50, 60,
          ],
          'circle-color': LAYER_COLORS.conflict,
          'circle-opacity': 0.08,
          'circle-blur': 1,
        },
      });
    }

    if (!map.getLayer(LAYERS.conflictsCircle)) {
      map.addLayer({
        id: LAYERS.conflictsCircle,
        type: 'circle',
        source: SOURCES.conflicts,
        paint: {
          'circle-radius': [
            'match', ['get', 'intensity'],
            'critical', 10,
            'high', 8,
            'medium', 6,
            'low', 5,
            6,
          ],
          'circle-color': [
            'match', ['get', 'intensity'],
            'critical', '#ef4444',
            'high', '#f97316',
            'medium', '#f59e0b',
            'low', '#eab308',
            '#ef4444',
          ],
          'circle-opacity': 0.6,
          'circle-stroke-width': 2,
          'circle-stroke-color': [
            'match', ['get', 'intensity'],
            'critical', '#ef4444',
            'high', '#f97316',
            'medium', '#f59e0b',
            'low', '#eab308',
            '#ef4444',
          ],
          'circle-stroke-opacity': 0.8,
        },
      });
    }

    if (!map.getLayer(LAYERS.conflictsIcon)) {
      map.addLayer({
        id: LAYERS.conflictsIcon,
        type: 'symbol',
        source: SOURCES.conflicts,
        layout: {
          'icon-image': 'conflict-icon',
          'icon-size': [
            'match', ['get', 'intensity'],
            'critical', 1.1,
            'high', 0.9,
            'medium', 0.75,
            0.65,
          ],
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
        minzoom: 4,
      });
    }

    // --- MISSILE ARCS ---
    if (!map.getLayer(LAYERS.missileArcs)) {
      map.addLayer({
        id: LAYERS.missileArcs,
        type: 'line',
        source: SOURCES.missileArcs,
        paint: {
          'line-color': LAYER_COLORS.missile,
          'line-width': 2,
          'line-opacity': 0.7,
          'line-dasharray': [4, 3],
        },
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
        },
      });
    }

    // --- MISSILE POINTS ---
    if (!map.getLayer(LAYERS.missilePoints)) {
      map.addLayer({
        id: LAYERS.missilePoints,
        type: 'circle',
        source: SOURCES.missiles,
        paint: {
          'circle-radius': 6,
          'circle-color': [
            'match', ['get', 'type'],
            'missile_launch', '#f97316',
            'missile_target', '#ef4444',
            '#f97316',
          ],
          'circle-opacity': 0.8,
          'circle-stroke-width': 2,
          'circle-stroke-color': 'rgba(255,255,255,0.3)',
        },
      });
    }

    if (!map.getLayer(LAYERS.missileIcons)) {
      map.addLayer({
        id: LAYERS.missileIcons,
        type: 'symbol',
        source: SOURCES.missiles,
        layout: {
          'icon-image': 'missile-icon',
          'icon-size': 0.85,
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
        minzoom: 5,
      });
    }

    // --- AIRCRAFT TRAILS ---
    if (!map.getLayer(LAYERS.aircraftTrails)) {
      map.addLayer({
        id: LAYERS.aircraftTrails,
        type: 'line',
        source: SOURCES.aircraftTrails,
        paint: {
          'line-color': '#06b6d4',
          'line-width': 1.5,
          'line-opacity': 0.4,
        },
        layout: {
          'line-cap': 'round',
          'line-join': 'round',
        },
      });
    }

    // --- COMMERCIAL AIRCRAFT ---
    if (!map.getLayer(LAYERS.commercialAircraftIcon)) {
      map.addLayer({
        id: LAYERS.commercialAircraftIcon,
        type: 'symbol',
        source: SOURCES.commercialAircraft,
        layout: {
          'icon-image': 'aircraft-icon',
          'icon-size': [
            'interpolate', ['linear'], ['zoom'],
            3, 0.5,
            6, 0.7,
            10, 1,
          ],
          'icon-rotate': ['get', 'heading'],
          'icon-rotation-alignment': 'map',
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
        paint: {
          'icon-opacity': [
            'case',
            ['get', 'on_ground'],
            0.4,
            0.9,
          ],
        },
      });
    }

    if (!map.getLayer(LAYERS.commercialAircraftLabels)) {
      map.addLayer({
        id: LAYERS.commercialAircraftLabels,
        type: 'symbol',
        source: SOURCES.commercialAircraft,
        layout: {
          'text-field': [
            'case',
            ['all', ['has', 'aircraft_type'], ['!=', ['get', 'aircraft_type'], ''], ['!=', ['get', 'aircraft_type'], 'Unknown']],
            ['concat', ['get', 'callsign'], '\n', ['get', 'aircraft_type']],
            ['get', 'callsign'],
          ],
          'text-size': 10,
          'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
          'text-offset': [0, 1.6],
          'text-anchor': 'top',
          'text-allow-overlap': false,
        },
        paint: {
          'text-color': LAYER_COLORS.commercialAircraft,
          'text-halo-color': '#0a0e17',
          'text-halo-width': 1,
          'text-opacity': 0.8,
        },
        minzoom: 7,
      });
    }

    // --- MILITARY AIRCRAFT ---
    if (!map.getLayer(LAYERS.militaryAircraftIcon)) {
      map.addLayer({
        id: LAYERS.militaryAircraftIcon,
        type: 'symbol',
        source: SOURCES.militaryAircraft,
        layout: {
          'icon-image': 'military-aircraft-icon',
          'icon-size': [
            'interpolate', ['linear'], ['zoom'],
            3, 0.55,
            6, 0.8,
            10, 1.1,
          ],
          'icon-rotate': ['get', 'heading'],
          'icon-rotation-alignment': 'map',
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
        paint: {
          'icon-opacity': [
            'case',
            ['get', 'on_ground'],
            0.5,
            1.0,
          ],
        },
      });
    }

    if (!map.getLayer(LAYERS.militaryAircraftLabels)) {
      map.addLayer({
        id: LAYERS.militaryAircraftLabels,
        type: 'symbol',
        source: SOURCES.militaryAircraft,
        layout: {
          'text-field': [
            'case',
            ['all', ['has', 'aircraft_type'], ['!=', ['get', 'aircraft_type'], ''], ['!=', ['get', 'aircraft_type'], 'Unknown']],
            ['concat', ['get', 'callsign'], '\n', ['get', 'aircraft_type']],
            ['get', 'callsign'],
          ],
          'text-size': 10,
          'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
          'text-offset': [0, 1.6],
          'text-anchor': 'top',
          'text-allow-overlap': false,
        },
        paint: {
          'text-color': LAYER_COLORS.militaryAircraft,
          'text-halo-color': '#0a0e17',
          'text-halo-width': 1,
          'text-opacity': 0.9,
        },
        minzoom: 6,
      });
    }

    // --- VESSELS ---
    if (!map.getLayer(LAYERS.vesselsIcon)) {
      map.addLayer({
        id: LAYERS.vesselsIcon,
        type: 'symbol',
        source: SOURCES.vessels,
        layout: {
          'icon-image': 'ship-icon',
          'icon-size': [
            'interpolate', ['linear'], ['zoom'],
            3, 0.5,
            6, 0.75,
            10, 1,
          ],
          'icon-rotate': ['get', 'course'],
          'icon-rotation-alignment': 'map',
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
        paint: {
          'icon-opacity': 0.9,
        },
      });
    }

    if (!map.getLayer(LAYERS.vesselsLabels)) {
      map.addLayer({
        id: LAYERS.vesselsLabels,
        type: 'symbol',
        source: SOURCES.vessels,
        layout: {
          'text-field': ['get', 'name'],
          'text-size': 10,
          'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
          'text-offset': [0, 1.4],
          'text-anchor': 'top',
          'text-allow-overlap': false,
        },
        paint: {
          'text-color': LAYER_COLORS.naval,
          'text-halo-color': '#0a0e17',
          'text-halo-width': 1,
          'text-opacity': 0.8,
        },
        minzoom: 7,
      });
    }

    // --- EARTHQUAKES ---
    if (!map.getLayer(LAYERS.earthquakeGlow)) {
      map.addLayer({
        id: LAYERS.earthquakeGlow,
        type: 'circle',
        source: SOURCES.earthquakes,
        paint: {
          'circle-radius': [
            'interpolate', ['linear'],
            ['get', 'magnitude'],
            2.5, 15,
            5, 30,
            7, 50,
          ],
          'circle-color': LAYER_COLORS.earthquake,
          'circle-opacity': 0.06,
          'circle-blur': 0.8,
        },
      });
    }

    if (!map.getLayer(LAYERS.earthquakeCircle)) {
      map.addLayer({
        id: LAYERS.earthquakeCircle,
        type: 'circle',
        source: SOURCES.earthquakes,
        paint: {
          'circle-radius': [
            'interpolate', ['linear'],
            ['get', 'magnitude'],
            2.5, 4,
            5, 8,
            7, 14,
            9, 22,
          ],
          'circle-color': [
            'interpolate', ['linear'],
            ['get', 'depth'],
            0, '#ef4444',
            70, '#f59e0b',
            300, '#3b82f6',
          ],
          'circle-opacity': 0.7,
          'circle-stroke-width': 1.5,
          'circle-stroke-color': 'rgba(255,255,255,0.2)',
        },
      });
    }

    // --- WEATHER ---
    if (!map.getLayer(LAYERS.weatherIcon)) {
      map.addLayer({
        id: LAYERS.weatherIcon,
        type: 'symbol',
        source: SOURCES.weather,
        layout: {
          'icon-image': 'weather-icon',
          'icon-size': 0.85,
          'icon-allow-overlap': true,
        },
      });
    }

    if (!map.getLayer(LAYERS.weatherLabels)) {
      map.addLayer({
        id: LAYERS.weatherLabels,
        type: 'symbol',
        source: SOURCES.weather,
        layout: {
          'text-field': [
            'concat',
            ['get', 'city'],
            '\n',
            ['to-string', ['get', 'temperature']],
            '\u00B0C',
          ],
          'text-size': 10,
          'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
          'text-offset': [0, 1.5],
          'text-anchor': 'top',
          'text-allow-overlap': false,
        },
        paint: {
          'text-color': '#c4b5fd',
          'text-halo-color': '#0a0e17',
          'text-halo-width': 1,
          'text-opacity': 0.85,
        },
        minzoom: 5,
      });
    }

    // --- MILITARY BASES ---
    if (!map.getLayer(LAYERS.militaryBasesIcon)) {
      map.addLayer({
        id: LAYERS.militaryBasesIcon,
        type: 'symbol',
        source: SOURCES.militaryBases,
        layout: {
          'icon-image': 'base-icon',
          'icon-size': [
            'interpolate', ['linear'], ['zoom'],
            3, 0.5,
            6, 0.75,
            10, 1,
          ],
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
      });
    }

    if (!map.getLayer(LAYERS.militaryBasesLabels)) {
      map.addLayer({
        id: LAYERS.militaryBasesLabels,
        type: 'symbol',
        source: SOURCES.militaryBases,
        layout: {
          'text-field': ['get', 'name'],
          'text-size': 10,
          'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
          'text-offset': [0, 1.4],
          'text-anchor': 'top',
          'text-allow-overlap': false,
        },
        paint: {
          'text-color': LAYER_COLORS.militaryBase,
          'text-halo-color': '#0a0e17',
          'text-halo-width': 1.2,
          'text-opacity': 0.85,
        },
        minzoom: 6,
      });
    }

    // --- NUCLEAR SITES ---
    if (!map.getLayer(LAYERS.nuclearSitesGlow)) {
      map.addLayer({
        id: LAYERS.nuclearSitesGlow,
        type: 'circle',
        source: SOURCES.nuclearSites,
        paint: {
          'circle-radius': 20,
          'circle-color': LAYER_COLORS.nuclear,
          'circle-opacity': 0.06,
          'circle-blur': 0.8,
        },
      });
    }

    if (!map.getLayer(LAYERS.nuclearSitesIcon)) {
      map.addLayer({
        id: LAYERS.nuclearSitesIcon,
        type: 'symbol',
        source: SOURCES.nuclearSites,
        layout: {
          'icon-image': 'nuclear-icon',
          'icon-size': [
            'interpolate', ['linear'], ['zoom'],
            3, 0.55,
            6, 0.8,
            10, 1,
          ],
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
      });
    }

    // --- INFRASTRUCTURE ---
    if (!map.getLayer(LAYERS.infraGlow)) {
      map.addLayer({
        id: LAYERS.infraGlow,
        type: 'circle',
        source: SOURCES.infrastructure,
        paint: {
          'circle-radius': 18,
          'circle-color': [
            'match', ['get', 'status'],
            'outage', '#ef4444',
            'disrupted', '#ef4444',
            'degraded', '#f59e0b',
            'reported', '#f97316',
            LAYER_COLORS.infrastructure,
          ],
          'circle-opacity': 0.1,
          'circle-blur': 0.8,
        },
      });
    }

    if (!map.getLayer(LAYERS.infraIcon)) {
      map.addLayer({
        id: LAYERS.infraIcon,
        type: 'symbol',
        source: SOURCES.infrastructure,
        layout: {
          'icon-image': 'infra-icon',
          'icon-size': [
            'interpolate', ['linear'], ['zoom'],
            3, 0.5,
            6, 0.75,
            10, 1,
          ],
          'icon-allow-overlap': true,
        },
      });
    }

    if (!map.getLayer(LAYERS.infraLabels)) {
      map.addLayer({
        id: LAYERS.infraLabels,
        type: 'symbol',
        source: SOURCES.infrastructure,
        layout: {
          'text-field': ['get', 'name'],
          'text-size': 9,
          'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
          'text-offset': [0, 1.4],
          'text-anchor': 'top',
          'text-allow-overlap': false,
        },
        paint: {
          'text-color': LAYER_COLORS.infrastructure,
          'text-halo-color': '#0a0e17',
          'text-halo-width': 1.2,
          'text-opacity': 0.8,
        },
        minzoom: 5,
      });
    }

    // --- COUNTRY BOUNDARIES (transparent fill for click detection) ---
    if (!map.getLayer(LAYERS.countryHighlight)) {
      map.addLayer({
        id: LAYERS.countryHighlight,
        type: 'fill',
        source: SOURCES.countryBoundaries,
        paint: {
          'fill-color': '#3b82f6',
          'fill-opacity': 0.12,
        },
        filter: ['==', ['get', 'ADMIN'], ''],
      });
    }

    if (!map.getLayer(LAYERS.countryHighlightOutline)) {
      map.addLayer({
        id: LAYERS.countryHighlightOutline,
        type: 'line',
        source: SOURCES.countryBoundaries,
        paint: {
          'line-color': '#3b82f6',
          'line-width': 2,
          'line-opacity': 0.5,
        },
        filter: ['==', ['get', 'ADMIN'], ''],
      });
    }

    if (!map.getLayer(LAYERS.countryFill)) {
      map.addLayer({
        id: LAYERS.countryFill,
        type: 'fill',
        source: SOURCES.countryBoundaries,
        paint: {
          'fill-color': 'transparent',
          'fill-opacity': 0,
        },
      });
    }

    // --- CORRELATION HIGHLIGHT ---
    if (!map.getLayer(LAYERS.correlationCircle)) {
      map.addLayer({
        id: LAYERS.correlationCircle,
        type: 'circle',
        source: SOURCES.correlationHighlight,
        paint: {
          'circle-radius': 15,
          'circle-color': '#a855f7',
          'circle-opacity': 0.25,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#a855f7',
        },
      });
    }

    if (!map.getLayer(LAYERS.correlationLine)) {
      map.addLayer({
        id: LAYERS.correlationLine,
        type: 'line',
        source: SOURCES.correlationHighlight,
        filter: ['==', '$type', 'LineString'],
        paint: {
          'line-color': '#a855f7',
          'line-width': 2,
          'line-dasharray': [3, 2],
          'line-opacity': 0.6,
        },
      });
    }
  }

  // =============================================
  // DATA UPDATE EFFECTS
  // Update source data when props change.
  // =============================================

  const updateSource = useCallback((sourceId, geojson) => {
    const map = mapRef.current;
    if (!map || !readyRef.current) {
      // Queue the update for when the map becomes ready
      pendingUpdatesRef.current[sourceId] = geojson;
      return;
    }
    const source = map.getSource(sourceId);
    if (source) {
      source.setData(geojson);
    }
  }, []);

  // Conflicts
  useEffect(() => {
    const geojson = conflictsToGeoJSON(conflicts);
    updateSource(SOURCES.conflicts, geojson);
    updateSource(SOURCES.hotspots, geojson); // hotspot heatmap uses same data
  }, [conflicts, updateSource]);

  // Aircraft -- smooth interpolation + trail lines (split into commercial and military)
  useEffect(() => {
    if (!aircraft || aircraft.length === 0) {
      updateSource(SOURCES.commercialAircraft, aircraftToGeoJSON([]));
      updateSource(SOURCES.militaryAircraft, aircraftToGeoJSON([]));
      updateSource(SOURCES.aircraftTrails, EMPTY_GEOJSON);
      return;
    }

    // Split aircraft into commercial and military
    const commercialAircraft = aircraft.filter(a => !a.is_military);
    const militaryAircraftData = aircraft.filter(a => a.is_military);

    // Build prev/next position lookup
    const prevPositions = prevAircraftRef.current;
    const nextPositions = {};
    aircraft.forEach((a) => {
      if (a.lat != null && a.lon != null) {
        nextPositions[a.icao24] = { lon: a.lon, lat: a.lat, heading: a.heading || 0 };
      }
    });

    interpStartRef.current = performance.now();
    const INTERP_DURATION = 5000; // 5s to match typical refresh interval

    // Update trail history (commercial only for trails)
    const history = aircraftHistoryRef.current;
    commercialAircraft.forEach((a) => {
      if (a.lat == null || a.lon == null) return;
      if (!history[a.icao24]) history[a.icao24] = [];
      const trail = history[a.icao24];
      const last = trail[trail.length - 1];
      if (!last || last[0] !== a.lon || last[1] !== a.lat) {
        trail.push([a.lon, a.lat]);
        if (trail.length > 20) trail.shift(); // keep last 20 positions
      }
    });

    // Prune history for aircraft no longer present
    const activeIcaos = new Set(commercialAircraft.filter((a) => a.lat != null && a.lon != null).map((a) => a.icao24));
    Object.keys(history).forEach((icao) => {
      if (!activeIcaos.has(icao)) delete history[icao];
    });

    // Build trail GeoJSON
    const trailFeatures = Object.entries(history)
      .filter(([, trail]) => trail.length >= 2)
      .map(([icao24, trail]) => ({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: trail },
        properties: { icao24 },
      }));
    updateSource(SOURCES.aircraftTrails, { type: 'FeatureCollection', features: trailFeatures });

    function animate() {
      const map = mapRef.current;
      if (!map || !readyRef.current) return;

      const elapsed = performance.now() - interpStartRef.current;
      const t = Math.min(elapsed / INTERP_DURATION, 1);

      // Interpolate positions between previous and new
      const interpolatedCommercial = commercialAircraft.map((a) => {
        if (a.lat == null || a.lon == null) return a;
        const prev = prevPositions[a.icao24];
        if (prev) {
          return {
            ...a,
            lon: prev.lon + (a.lon - prev.lon) * t,
            lat: prev.lat + (a.lat - prev.lat) * t,
          };
        }
        return a;
      });

      const interpolatedMilitary = militaryAircraftData.map((a) => {
        if (a.lat == null || a.lon == null) return a;
        const prev = prevPositions[a.icao24];
        if (prev) {
          return {
            ...a,
            lon: prev.lon + (a.lon - prev.lon) * t,
            lat: prev.lat + (a.lat - prev.lat) * t,
          };
        }
        return a;
      });

      const commSource = map.getSource(SOURCES.commercialAircraft);
      if (commSource) {
        commSource.setData(aircraftToGeoJSON(interpolatedCommercial));
      }

      const milSource = map.getSource(SOURCES.militaryAircraft);
      if (milSource) {
        milSource.setData(aircraftToGeoJSON(interpolatedMilitary));
      }

      if (t < 1) {
        animFrameRef.current = requestAnimationFrame(animate);
      }
    }

    // Cancel previous animation loop
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    animFrameRef.current = requestAnimationFrame(animate);

    // Save current positions as prev for next update cycle
    prevAircraftRef.current = nextPositions;
  }, [aircraft, updateSource]);

  // Missiles -- static full arcs (no animation)
  useEffect(() => {
    if (!missiles || missiles.length === 0) {
      updateSource(SOURCES.missiles, missilesToGeoJSON([]));
      updateSource(SOURCES.missileArcs, missileArcsToGeoJSON([]));
      return;
    }

    updateSource(SOURCES.missiles, missilesToGeoJSON(missiles));
    updateSource(SOURCES.missileArcs, missileArcsToGeoJSON(missiles));
  }, [missiles, updateSource]);

  // Earthquakes
  useEffect(() => {
    updateSource(SOURCES.earthquakes, earthquakesToGeoJSON(earthquakes));
  }, [earthquakes, updateSource]);

  // Weather
  useEffect(() => {
    updateSource(SOURCES.weather, weatherToGeoJSON(weather));
  }, [weather, updateSource]);

  // Military Bases
  useEffect(() => {
    updateSource(SOURCES.militaryBases, militaryBasesToGeoJSON(militaryBases));
  }, [militaryBases, updateSource]);

  // Nuclear Sites
  useEffect(() => {
    updateSource(SOURCES.nuclearSites, nuclearSitesToGeoJSON(nuclearSites));
  }, [nuclearSites, updateSource]);

  // Waterways
  useEffect(() => {
    updateSource(SOURCES.waterways, waterwaysToGeoJSON(waterways));
  }, [waterways, updateSource]);

  // Vessels
  useEffect(() => {
    updateSource(SOURCES.vessels, vesselsToGeoJSON(vessels));
  }, [vessels, updateSource]);

  // Infrastructure (data centers + outages + cables)
  useEffect(() => {
    const geojson = infraToGeoJSON(dataCenters, infraOutages, underseaCables);
    updateSource(SOURCES.infrastructure, geojson);
  }, [dataCenters, infraOutages, underseaCables, updateSource]);

  // Event correlation highlights
  useEffect(() => {
    if (!selectedChain || !selectedChain.events) {
      updateSource(SOURCES.correlationHighlight, EMPTY_GEOJSON);
      return;
    }
    const features = [];
    const chainEvents = selectedChain.events.filter(e => e.lat && e.lon);
    // Add circles for each event
    chainEvents.forEach(e => {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [e.lon, e.lat] },
        properties: { id: e.id, title: e.title, type: e.type },
      });
    });
    // Add connection lines between sequential events
    if (chainEvents.length >= 2) {
      features.push({
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: chainEvents.map(e => [e.lon, e.lat]),
        },
        properties: { id: selectedChain.id },
      });
    }
    updateSource(SOURCES.correlationHighlight, { type: 'FeatureCollection', features });
  }, [selectedChain, updateSource]);

  // =============================================
  // LAYER VISIBILITY
  // =============================================

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;

    Object.entries(LAYER_GROUP_MAP).forEach(([groupKey, layerIds]) => {
      const isVisible = activeLayers.has(groupKey);
      layerIds.forEach((layerId) => {
        if (map.getLayer(layerId)) {
          map.setLayoutProperty(
            layerId,
            'visibility',
            isVisible ? 'visible' : 'none'
          );
        }
      });
    });
  }, [activeLayers]);

  // =============================================
  // RENDER
  // =============================================

  return (
    <div className="map-wrapper">
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
}

// =============================================
// POPUP HTML BUILDER
// =============================================

function buildPopupHTML(props) {
  const type = props.type || 'unknown';
  const title = props.title || props.name || props.callsign || 'Unknown';
  const severity = props.intensity || props.severity || props.status || '';
  const description = props.description || '';
  const timestamp = props.timestamp || '';

  let meta = '';

  switch (type) {
    case 'conflict':
      meta = `
        ${props.parties ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Parties:</span><span class="event-popup-meta-value">${props.parties}</span></div>` : ''}
        ${props.radius ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Radius:</span><span class="event-popup-meta-value">${props.radius} km</span></div>` : ''}
      `;
      break;
    case 'aircraft': {
      const fr24Link = `https://www.flightradar24.com/${(props.callsign || props.icao24 || '').trim().toLowerCase()}`;
      const isMil = props.is_military === 'true' || props.is_military === true;
      const typeColor = isMil ? '#ef4444' : '#06b6d4';
      meta = `
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Callsign:</span><span class="event-popup-meta-value">${props.callsign || 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">ICAO24:</span><span class="event-popup-meta-value">${props.icao24 || 'N/A'}</span></div>
        ${props.aircraft_type && props.aircraft_type !== 'Unknown' ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Type:</span><span class="event-popup-meta-value" style="color:${typeColor};font-weight:600">${props.aircraft_type}</span></div>` : ''}
        ${props.operator ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Operator:</span><span class="event-popup-meta-value">${props.operator}</span></div>` : ''}
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Altitude:</span><span class="event-popup-meta-value">${props.altitude ? Math.round(props.altitude) + ' m (' + Math.round(props.altitude * 3.281) + ' ft)' : 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Speed:</span><span class="event-popup-meta-value">${props.velocity ? Math.round(props.velocity) + ' m/s (' + Math.round(props.velocity * 1.944) + ' kts)' : 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Heading:</span><span class="event-popup-meta-value">${props.heading ? Math.round(props.heading) + '\u00B0' : 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Country:</span><span class="event-popup-meta-value">${props.origin_country || 'N/A'}</span></div>
        ${isMil ? '<div class="event-popup-meta-row"><span class="event-popup-meta-label">Status:</span><span class="event-popup-meta-value" style="color:#ef4444;font-weight:600">MILITARY</span></div>' : ''}
        <div class="event-popup-meta-row" style="margin-top:6px"><a href="${fr24Link}" target="_blank" rel="noopener noreferrer" style="color:#06b6d4;text-decoration:underline;font-size:11px;font-family:monospace">Track on FlightRadar24</a></div>
      `;
      break;
    }
    case 'missile_launch':
    case 'missile_target':
      meta = `
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Type:</span><span class="event-popup-meta-value">${props.missile_type || 'Unknown'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Status:</span><span class="event-popup-meta-value">${props.status || 'N/A'}</span></div>
        ${props.source ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Source:</span><span class="event-popup-meta-value">${props.source}</span></div>` : ''}
      `;
      break;
    case 'earthquake':
      meta = `
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Magnitude:</span><span class="event-popup-meta-value">${props.magnitude || 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Depth:</span><span class="event-popup-meta-value">${props.depth ? props.depth + ' km' : 'N/A'}</span></div>
      `;
      break;
    case 'military_base':
      meta = `
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Country:</span><span class="event-popup-meta-value">${props.country || 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Type:</span><span class="event-popup-meta-value">${props.base_type || 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Branch:</span><span class="event-popup-meta-value">${props.branch || 'N/A'}</span></div>
        ${props.operator ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Operator:</span><span class="event-popup-meta-value">${props.operator}</span></div>` : ''}
      `;
      break;
    case 'nuclear':
      meta = `
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Country:</span><span class="event-popup-meta-value">${props.country || 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Type:</span><span class="event-popup-meta-value">${props.site_type || 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Status:</span><span class="event-popup-meta-value">${props.status || 'N/A'}</span></div>
      `;
      break;
    case 'weather':
      meta = `
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Temp:</span><span class="event-popup-meta-value">${props.temperature != null ? props.temperature + '\u00B0C' : 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Wind:</span><span class="event-popup-meta-value">${props.wind_speed != null ? props.wind_speed + ' m/s' : 'N/A'}</span></div>
        ${props.event ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Event:</span><span class="event-popup-meta-value">${props.event}</span></div>` : ''}
      `;
      break;
    case 'vessel':
      meta = `
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">MMSI:</span><span class="event-popup-meta-value">${props.mmsi || 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Type:</span><span class="event-popup-meta-value">${props.vessel_type || 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Flag:</span><span class="event-popup-meta-value">${props.flag || 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Speed:</span><span class="event-popup-meta-value">${props.speed != null ? props.speed + ' kn' : 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Course:</span><span class="event-popup-meta-value">${props.course != null ? Math.round(props.course) + '\u00B0' : 'N/A'}</span></div>
        ${props.destination ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Destination:</span><span class="event-popup-meta-value">${props.destination}</span></div>` : ''}
      `;
      break;
    case 'waterway':
      meta = `
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Type:</span><span class="event-popup-meta-value">${props.waterway_type || 'N/A'}</span></div>
        ${props.daily_traffic ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Traffic:</span><span class="event-popup-meta-value">${props.daily_traffic}</span></div>` : ''}
        ${props.controlled_by ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Control:</span><span class="event-popup-meta-value">${props.controlled_by}</span></div>` : ''}
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Importance:</span><span class="event-popup-meta-value">${props.strategic_importance || 'N/A'}</span></div>
      `;
      break;
    case 'data_center':
    case 'infra_outage':
    case 'undersea_cable': {
      const statusColor = { operational: '#22c55e', degraded: '#f59e0b', outage: '#ef4444', disrupted: '#ef4444' }[props.status] || '#3b82f6';
      const causeLabel = { war_related: 'WAR-RELATED', cyber_attack: 'CYBER ATTACK', natural_disaster: 'NATURAL', technical: 'TECHNICAL' }[props.cause] || '';
      meta = `
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Provider:</span><span class="event-popup-meta-value">${props.provider || 'N/A'}</span></div>
        <div class="event-popup-meta-row"><span class="event-popup-meta-label">Status:</span><span class="event-popup-meta-value" style="color:${statusColor};font-weight:600">${(props.status || 'unknown').toUpperCase()}</span></div>
        ${props.country ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Country:</span><span class="event-popup-meta-value">${props.country}</span></div>` : ''}
        ${causeLabel ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Cause:</span><span class="event-popup-meta-value">${causeLabel}</span></div>` : ''}
        ${props.connects ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Route:</span><span class="event-popup-meta-value" style="font-size:10px">${props.connects}</span></div>` : ''}
      `;
      break;
    }
    default:
      break;
  }

  const severityBadge = severity
    ? `<span class="badge badge-${mapSeverity(severity)}">${severity.toUpperCase()}</span>`
    : '';

  const typeBadge = `<span class="badge badge-source">${formatType(type)}</span>`;

  const timeStr = timestamp
    ? `<div class="event-popup-meta-row"><span class="event-popup-meta-label">Time:</span><span class="event-popup-meta-value">${formatTimestamp(timestamp)}</span></div>`
    : '';

  return `
    <div class="event-popup">
      <div class="event-popup-type">${typeBadge} ${severityBadge}</div>
      <div class="event-popup-title">${escapeHTML(title)}</div>
      ${description ? `<div class="event-popup-desc">${escapeHTML(description).substring(0, 200)}</div>` : ''}
      <div class="event-popup-meta">
        ${meta}
        ${timeStr}
      </div>
    </div>
  `;
}

function mapSeverity(s) {
  const lower = (s || '').toLowerCase();
  if (lower === 'critical') return 'critical';
  if (lower === 'high') return 'high';
  if (lower === 'medium') return 'medium';
  if (lower === 'low') return 'low';
  if (lower === 'confirmed') return 'high';
  if (lower === 'reported') return 'medium';
  if (lower === 'intercepted') return 'low';
  return 'info';
}

function formatType(type) {
  return (type || 'unknown')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
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

function escapeHTML(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
