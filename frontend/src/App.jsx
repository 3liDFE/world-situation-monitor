/**
 * Main Application Component - World Situation Monitor
 * Manages all state, data fetching, and layout orchestration.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header';
import MapContainer from './components/MapContainer';
import LayerControl from './components/LayerControl';
import SidePanel from './components/SidePanel';
import useWebSocket from './hooks/useWebSocket';
import {
  fetchConflicts,
  fetchAircraft,
  fetchMissiles,
  fetchEarthquakes,
  fetchWeather,
  fetchMilitaryBases,
  fetchNuclearSites,
  fetchWaterways,
  fetchVessels,
  fetchNews,
  fetchLiveFeeds,
  fetchAIInsights,
  fetchStatus,
} from './services/api';

// Default active layers on startup
const DEFAULT_LAYERS = new Set([
  'conflicts',
  'missiles',
  'aircraft',
  'naval',
  'militaryBases',
  'nuclearSites',
  'waterways',
  'earthquakes',
]);

// Region presets for quick navigation
const REGION_PRESETS = {
  Global: { center: [30, 20], zoom: 2.5 },
  'Middle East': { center: [47, 29], zoom: 4 },
  Europe: { center: [15, 50], zoom: 4 },
  Asia: { center: [100, 35], zoom: 3.5 },
  Africa: { center: [20, 5], zoom: 3.5 },
};

export default function App() {
  // ----- Layer visibility state -----
  const [activeLayers, setActiveLayers] = useState(DEFAULT_LAYERS);

  // ----- Data state for each layer -----
  const [conflicts, setConflicts] = useState([]);
  const [aircraft, setAircraft] = useState([]);
  const [missiles, setMissiles] = useState([]);
  const [earthquakes, setEarthquakes] = useState([]);
  const [weather, setWeather] = useState([]);
  const [militaryBases, setMilitaryBases] = useState([]);
  const [nuclearSites, setNuclearSites] = useState([]);
  const [waterways, setWaterways] = useState([]);
  const [vessels, setVessels] = useState([]);
  const [news, setNews] = useState([]);
  const [liveFeeds, setLiveFeeds] = useState([]);
  const [aiInsights, setAIInsights] = useState([]);
  const [alerts, setAlerts] = useState([]);

  // ----- UI state -----
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [sidePanel, setSidePanel] = useState('feeds');
  const [selectedCountry, setSelectedCountry] = useState('');
  const [activeRegion, setActiveRegion] = useState('Middle East');
  const [timeRange, setTimeRange] = useState('Live');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLayerPanelOpen, setIsLayerPanelOpen] = useState(true);
  const [isSidePanelOpen, setIsSidePanelOpen] = useState(true);
  const [systemStatus, setSystemStatus] = useState(null);
  const [dataFreshness, setDataFreshness] = useState({});

  // ----- Map control state -----
  const [mapView, setMapView] = useState(REGION_PRESETS['Middle East']);
  const mapRef = useRef(null);

  // ----- Interval refs for cleanup -----
  const intervalsRef = useRef([]);

  // ----- Layer counts for display -----
  const layerCounts = {
    conflicts: conflicts.length,
    missiles: missiles.length,
    aircraft: aircraft.length,
    naval: vessels.length,
    militaryBases: militaryBases.length,
    nuclearSites: nuclearSites.length,
    waterways: waterways.length,
    earthquakes: earthquakes.length,
    weather: weather.length,
    hotspots: conflicts.length,
    sanctions: 0,
    cyberAttacks: 0,
  };

  // =============================================
  // DATA FETCHING
  // =============================================

  const loadConflicts = useCallback(async () => {
    const data = await fetchConflicts();
    if (data && Array.isArray(data)) {
      setConflicts(data);
      updateFreshness('conflicts');
    }
  }, []);

  const loadAircraft = useCallback(async () => {
    const data = await fetchAircraft();
    if (data && Array.isArray(data)) {
      setAircraft(data);
      updateFreshness('aircraft');
    }
  }, []);

  const loadMissiles = useCallback(async () => {
    const data = await fetchMissiles();
    if (data && Array.isArray(data)) {
      setMissiles(data);
      updateFreshness('missiles');
    }
  }, []);

  const loadEarthquakes = useCallback(async () => {
    const data = await fetchEarthquakes();
    if (data && Array.isArray(data)) {
      setEarthquakes(data);
      updateFreshness('earthquakes');
    }
  }, []);

  const loadWeather = useCallback(async () => {
    const data = await fetchWeather();
    if (data && Array.isArray(data)) {
      setWeather(data);
      updateFreshness('weather');
    }
  }, []);

  const loadMilitaryBases = useCallback(async () => {
    const data = await fetchMilitaryBases();
    if (data && Array.isArray(data)) {
      setMilitaryBases(data);
      updateFreshness('militaryBases');
    }
  }, []);

  const loadNuclearSites = useCallback(async () => {
    const data = await fetchNuclearSites();
    if (data && Array.isArray(data)) {
      setNuclearSites(data);
      updateFreshness('nuclearSites');
    }
  }, []);

  const loadWaterways = useCallback(async () => {
    const data = await fetchWaterways();
    if (data && Array.isArray(data)) {
      setWaterways(data);
      updateFreshness('waterways');
    }
  }, []);

  const loadVessels = useCallback(async () => {
    const data = await fetchVessels();
    if (data && Array.isArray(data)) {
      setVessels(data);
      updateFreshness('vessels');
    }
  }, []);

  const loadNews = useCallback(async (country) => {
    const data = await fetchNews(country || undefined);
    if (data && Array.isArray(data)) {
      setNews(data);
      updateFreshness('news');
    }
  }, []);

  const loadLiveFeeds = useCallback(async (country) => {
    const data = await fetchLiveFeeds(country || undefined);
    if (data && Array.isArray(data)) {
      setLiveFeeds(data);
    }
  }, []);

  const loadAIInsights = useCallback(async () => {
    const data = await fetchAIInsights();
    if (data && Array.isArray(data)) {
      setAIInsights(data);
      updateFreshness('aiInsights');
    }
  }, []);

  const loadStatus = useCallback(async () => {
    const data = await fetchStatus();
    if (data) {
      setSystemStatus(data);
    }
  }, []);

  const updateFreshness = (key) => {
    setDataFreshness((prev) => ({
      ...prev,
      [key]: Date.now(),
    }));
  };

  // =============================================
  // WEBSOCKET HANDLER
  // =============================================

  const handleWSMessage = useCallback((data) => {
    if (!data) return;

    // Handle wrapped format: {type: "update", layer: "aircraft", data: [...]}
    const messageType = data.layer || data.type;
    const payload = data.data;

    // Skip non-data messages
    if (data.type === 'connected' || data.type === 'subscribed' || data.type === 'pong' || data.type === 'unsubscribed') {
      return;
    }

    if (!payload) return;

    switch (messageType) {
      case 'conflicts':
        if (Array.isArray(payload)) {
          setConflicts(payload);
          updateFreshness('conflicts');
        }
        break;
      case 'aircraft':
        if (Array.isArray(payload)) {
          setAircraft(payload);
          updateFreshness('aircraft');
        }
        break;
      case 'missiles':
        if (Array.isArray(payload)) {
          setMissiles(payload);
          updateFreshness('missiles');
        }
        break;
      case 'earthquakes':
        if (Array.isArray(payload)) {
          setEarthquakes(payload);
          updateFreshness('earthquakes');
        }
        break;
      case 'weather':
        if (Array.isArray(payload)) {
          setWeather(payload);
          updateFreshness('weather');
        }
        break;
      case 'news':
        if (Array.isArray(payload)) {
          setNews(payload);
          updateFreshness('news');
        }
        break;
      case 'vessels':
        if (Array.isArray(payload)) {
          setVessels(payload);
          updateFreshness('vessels');
        }
        break;
      case 'ai_insights':
        if (Array.isArray(payload)) {
          setAIInsights(payload);
          updateFreshness('aiInsights');
        }
        break;
      case 'alert':
        setAlerts((prev) => [payload, ...prev].slice(0, 100));
        break;
      default:
        break;
    }
  }, []);

  const { connectionStatus } = useWebSocket(handleWSMessage);

  // =============================================
  // INITIAL DATA LOAD & POLLING
  // =============================================

  useEffect(() => {
    // Initial fetch via HTTP - one-time load, then WebSocket takes over
    loadConflicts();
    loadAircraft();
    loadMissiles();
    loadEarthquakes();
    loadWeather();
    loadMilitaryBases();
    loadNuclearSites();
    loadWaterways();
    loadVessels();
    loadNews();
    loadLiveFeeds();
    loadAIInsights();
    loadStatus();

    // Only poll system status (lightweight health check) - everything else is WebSocket-driven
    const statusInterval = setInterval(loadStatus, 30000);
    intervalsRef.current = [statusInterval];

    return () => {
      intervalsRef.current.forEach(clearInterval);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Reload feeds when country changes
  useEffect(() => {
    loadLiveFeeds(selectedCountry);
    loadNews(selectedCountry);
  }, [selectedCountry, loadLiveFeeds, loadNews]);

  // =============================================
  // LAYER TOGGLE HANDLERS
  // =============================================

  const toggleLayer = useCallback((layerId) => {
    setActiveLayers((prev) => {
      const next = new Set(prev);
      if (next.has(layerId)) {
        next.delete(layerId);
      } else {
        next.add(layerId);
      }
      return next;
    });
  }, []);

  const showAllLayers = useCallback(() => {
    setActiveLayers(
      new Set([
        'conflicts',
        'missiles',
        'aircraft',
        'naval',
        'militaryBases',
        'nuclearSites',
        'waterways',
        'earthquakes',
        'weather',
        'hotspots',
        'sanctions',
        'cyberAttacks',
      ])
    );
  }, []);

  const clearAllLayers = useCallback(() => {
    setActiveLayers(new Set());
  }, []);

  // =============================================
  // REGION NAVIGATION
  // =============================================

  const handleRegionSelect = useCallback((region) => {
    setActiveRegion(region);
    const preset = REGION_PRESETS[region];
    if (preset && mapRef.current) {
      mapRef.current.flyTo({
        center: preset.center,
        zoom: preset.zoom,
        duration: 1500,
        essential: true,
      });
    }
  }, []);

  // =============================================
  // MAP EVENT HANDLER
  // =============================================

  const handleMapEvent = useCallback((event) => {
    setSelectedEvent(event);
  }, []);

  const handleMapReady = useCallback((map) => {
    mapRef.current = map;
  }, []);

  // =============================================
  // RENDER
  // =============================================

  return (
    <div className="app-container">
      <Header
        connectionStatus={connectionStatus}
        activeRegion={activeRegion}
        onRegionSelect={handleRegionSelect}
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        dataFreshness={dataFreshness}
        systemStatus={systemStatus}
      />

      <MapContainer
        activeLayers={activeLayers}
        conflicts={conflicts}
        aircraft={aircraft}
        missiles={missiles}
        earthquakes={earthquakes}
        weather={weather}
        militaryBases={militaryBases}
        nuclearSites={nuclearSites}
        waterways={waterways}
        vessels={vessels}
        selectedEvent={selectedEvent}
        onEventClick={handleMapEvent}
        onMapReady={handleMapReady}
        initialView={REGION_PRESETS['Middle East']}
      />

      <LayerControl
        activeLayers={activeLayers}
        onToggleLayer={toggleLayer}
        onShowAll={showAllLayers}
        onClearAll={clearAllLayers}
        layerCounts={layerCounts}
        isOpen={isLayerPanelOpen}
        onTogglePanel={() => setIsLayerPanelOpen((v) => !v)}
      />

      <SidePanel
        activeTab={sidePanel}
        onTabChange={setSidePanel}
        isOpen={isSidePanelOpen}
        onTogglePanel={() => setIsSidePanelOpen((v) => !v)}
        selectedCountry={selectedCountry}
        onCountryChange={setSelectedCountry}
        liveFeeds={liveFeeds}
        news={news}
        aiInsights={aiInsights}
        alerts={alerts}
      />
    </div>
  );
}
