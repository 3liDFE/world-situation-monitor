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
import CountryProfile from './components/CountryProfile';
import TimelinePanel from './components/TimelinePanel';
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
  fetchXIntelligence,
  fetchTelegramIntelligence,
  fetchOtherOsint,
  fetchAlerts,
  fetchInfraOutages,
  fetchDataCenters,
  fetchUnderseaCables,
  fetchCorrelations,
  fetchStatus,
} from './services/api';

// Default active layers on startup
const DEFAULT_LAYERS = new Set([
  'conflicts',
  'missiles',
  'commercialAircraft',
  'militaryAircraft',
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
  const [xIntelligence, setXIntelligence] = useState([]);
  const [telegramIntelligence, setTelegramIntelligence] = useState([]);
  const [osintOther, setOsintOther] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [infraOutages, setInfraOutages] = useState([]);
  const [dataCenters, setDataCenters] = useState([]);
  const [underseaCables, setUnderseaCables] = useState([]);
  const [eventChains, setEventChains] = useState([]);

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
  const [selectedCountryProfile, setSelectedCountryProfile] = useState(null);
  const [isTimelineOpen, setIsTimelineOpen] = useState(false);
  const [selectedChain, setSelectedChain] = useState(null);

  // ----- Map control state -----
  const [mapView, setMapView] = useState(REGION_PRESETS['Middle East']);
  const mapRef = useRef(null);

  // ----- Interval refs for cleanup -----
  const intervalsRef = useRef([]);

  // ----- Time filter helper -----
  const getTimeFilterMs = (range) => {
    switch (range) {
      case '24h': return 24 * 60 * 60 * 1000;
      case '7d': return 7 * 24 * 60 * 60 * 1000;
      case '30d': return 30 * 24 * 60 * 60 * 1000;
      default: return 0; // 'Live' = no filter
    }
  };

  const filterByTime = (items, timestampKey = 'timestamp') => {
    const maxAge = getTimeFilterMs(timeRange);
    if (!maxAge) return items;
    const cutoff = Date.now() - maxAge;
    return items.filter((item) => {
      const ts = item[timestampKey];
      if (!ts) return true; // keep items without timestamps
      const d = new Date(ts).getTime();
      return !isNaN(d) && d >= cutoff;
    });
  };

  // ----- Search filter helper -----
  const matchesSearch = (item, fields = ['title', 'text', 'description', 'channel', 'callsign', 'name']) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    for (const field of fields) {
      const val = item[field];
      if (val && typeof val === 'string' && val.toLowerCase().includes(q)) return true;
    }
    return false;
  };

  // ----- Sort helper (newest first) -----
  const sortNewest = (items, key = 'timestamp') =>
    [...items].sort((a, b) => {
      const da = new Date(a[key] || 0).getTime();
      const db = new Date(b[key] || 0).getTime();
      return db - da;
    });

  // ----- Filtered data (always sorted newest first) -----
  const filteredConflicts = sortNewest(filterByTime(conflicts).filter(i => matchesSearch(i)));
  const filteredMissiles = sortNewest(filterByTime(missiles).filter(i => matchesSearch(i)));
  const filteredNews = sortNewest(filterByTime(news, 'published_at').filter(i => matchesSearch(i)), 'published_at');
  const filteredXIntel = sortNewest(filterByTime(xIntelligence).filter(i => matchesSearch(i)));
  const filteredTelegram = sortNewest(filterByTime(telegramIntelligence).filter(i => matchesSearch(i)));
  const filteredOsint = sortNewest(filterByTime(osintOther).filter(i => matchesSearch(i)));

  // ----- Layer counts for display -----
  const layerCounts = {
    conflicts: filteredConflicts.length,
    missiles: filteredMissiles.length,
    commercialAircraft: aircraft.filter(a => !a.is_military).length,
    militaryAircraft: aircraft.filter(a => a.is_military).length,
    naval: vessels.length,
    militaryBases: militaryBases.length,
    nuclearSites: nuclearSites.length,
    waterways: waterways.length,
    earthquakes: earthquakes.length,
    weather: weather.length,
    hotspots: filteredConflicts.length,
    infrastructure: dataCenters.length + infraOutages.length,
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

  const loadXIntelligence = useCallback(async () => {
    const data = await fetchXIntelligence();
    if (data && Array.isArray(data)) {
      setXIntelligence(data);
      updateFreshness('xIntelligence');
    }
  }, []);

  const loadTelegramIntelligence = useCallback(async () => {
    const data = await fetchTelegramIntelligence();
    if (data && Array.isArray(data)) {
      setTelegramIntelligence(data);
      updateFreshness('telegramIntelligence');
    }
  }, []);

  const loadOsintOther = useCallback(async () => {
    const data = await fetchOtherOsint();
    if (data && Array.isArray(data)) {
      setOsintOther(data);
      updateFreshness('osintOther');
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    const data = await fetchAlerts();
    if (data && Array.isArray(data)) {
      setAlerts((prev) => {
        // Merge: keep HTTP alerts, prepend any new ones by ID
        const existingIds = new Set(prev.map((a) => a.id));
        const newOnes = data.filter((a) => !existingIds.has(a.id));
        if (newOnes.length === 0) return data; // full refresh from backend
        return [...newOnes, ...prev].slice(0, 100);
      });
      updateFreshness('alerts');
    }
  }, []);

  const loadInfraOutages = useCallback(async () => {
    const data = await fetchInfraOutages();
    if (data && Array.isArray(data)) {
      setInfraOutages(data);
      updateFreshness('infraOutages');
    }
  }, []);

  const loadDataCenters = useCallback(async () => {
    const data = await fetchDataCenters();
    if (data && Array.isArray(data)) {
      setDataCenters(data);
    }
  }, []);

  const loadUnderseaCables = useCallback(async () => {
    const data = await fetchUnderseaCables();
    if (data && Array.isArray(data)) {
      setUnderseaCables(data);
    }
  }, []);

  const loadCorrelations = useCallback(async () => {
    const data = await fetchCorrelations();
    if (data && Array.isArray(data)) {
      setEventChains(data);
      updateFreshness('correlations');
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
      case 'x_intelligence':
        if (Array.isArray(payload)) {
          setXIntelligence(payload);
          updateFreshness('xIntelligence');
        }
        break;
      case 'telegram_intelligence':
        if (Array.isArray(payload)) {
          setTelegramIntelligence(payload);
          updateFreshness('telegramIntelligence');
        }
        break;
      case 'osint_other':
        if (Array.isArray(payload)) {
          setOsintOther(payload);
          updateFreshness('osintOther');
        }
        break;
      case 'infra_outages':
        if (Array.isArray(payload)) {
          setInfraOutages(payload);
          updateFreshness('infraOutages');
        }
        break;
      case 'event_chains':
        if (Array.isArray(payload)) {
          setEventChains(payload);
          updateFreshness('correlations');
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
    loadXIntelligence();
    loadTelegramIntelligence();
    loadOsintOther();
    loadAlerts();
    loadInfraOutages();
    loadDataCenters();
    loadUnderseaCables();
    loadCorrelations();
    loadStatus();

    // Poll intel tabs every 30s as backup to WebSocket for live updates
    const statusInterval = setInterval(loadStatus, 30000);
    const intelInterval = setInterval(() => {
      loadXIntelligence();
      loadTelegramIntelligence();
      loadOsintOther();
      loadNews();
      loadAIInsights();
      loadAlerts();
    }, 30000);
    const conflictInterval = setInterval(() => {
      loadConflicts();
      loadMissiles();
      loadInfraOutages();
      loadCorrelations();
    }, 60000);
    intervalsRef.current = [statusInterval, intelInterval, conflictInterval];

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
        'commercialAircraft',
        'militaryAircraft',
        'naval',
        'militaryBases',
        'nuclearSites',
        'waterways',
        'earthquakes',
        'weather',
        'hotspots',
        'infrastructure',
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
        conflicts={filteredConflicts}
        aircraft={aircraft}
        missiles={filteredMissiles}
        earthquakes={earthquakes}
        weather={weather}
        militaryBases={militaryBases}
        nuclearSites={nuclearSites}
        waterways={waterways}
        vessels={vessels}
        infraOutages={infraOutages}
        dataCenters={dataCenters}
        underseaCables={underseaCables}
        eventChains={eventChains}
        selectedChain={selectedChain}
        selectedEvent={selectedEvent}
        onEventClick={handleMapEvent}
        onMapReady={handleMapReady}
        onCountrySelect={setSelectedCountryProfile}
        initialView={REGION_PRESETS['Middle East']}
      />

      {/* Mobile backdrop - tap to close panels */}
      {(isLayerPanelOpen || isSidePanelOpen) && (
        <div
          className="mobile-backdrop"
          onClick={() => {
            setIsLayerPanelOpen(false);
            setIsSidePanelOpen(false);
          }}
        />
      )}

      <LayerControl
        activeLayers={activeLayers}
        onToggleLayer={toggleLayer}
        onShowAll={showAllLayers}
        onClearAll={clearAllLayers}
        layerCounts={layerCounts}
        isOpen={isLayerPanelOpen}
        onTogglePanel={() => { setIsLayerPanelOpen((v) => !v); setIsSidePanelOpen(false); }}
      />

      <SidePanel
        activeTab={sidePanel}
        onTabChange={setSidePanel}
        isOpen={isSidePanelOpen}
        onTogglePanel={() => { setIsSidePanelOpen((v) => !v); setIsLayerPanelOpen(false); }}
        selectedCountry={selectedCountry}
        onCountryChange={setSelectedCountry}
        liveFeeds={liveFeeds}
        news={filteredNews}
        aiInsights={aiInsights}
        xIntelligence={filteredXIntel}
        telegramIntelligence={filteredTelegram}
        osintOther={filteredOsint}
        alerts={alerts}
        infraOutages={infraOutages}
        dataCenters={dataCenters}
      />

      {selectedCountryProfile && (
        <CountryProfile
          country={selectedCountryProfile}
          conflicts={filteredConflicts}
          missiles={filteredMissiles}
          militaryBases={militaryBases}
          nuclearSites={nuclearSites}
          news={filteredNews}
          xIntelligence={filteredXIntel}
          telegramIntelligence={filteredTelegram}
          osintOther={filteredOsint}
          infraOutages={infraOutages}
          onClose={() => setSelectedCountryProfile(null)}
        />
      )}

      <TimelinePanel
        eventChains={eventChains}
        isOpen={isTimelineOpen}
        onToggle={() => setIsTimelineOpen(v => !v)}
        selectedChain={selectedChain}
        onSelectChain={(chain) => {
          setSelectedChain(chain);
          if (chain && chain.events && chain.events.length > 0 && mapRef.current) {
            const firstEvent = chain.events[0];
            if (firstEvent.lat && firstEvent.lon) {
              mapRef.current.flyTo({ center: [firstEvent.lon, firstEvent.lat], zoom: 6, duration: 1500 });
            }
          }
        }}
      />
    </div>
  );
}
