/**
 * API service module for World Situation Monitor.
 * Handles all HTTP requests to the backend with error handling and timeouts.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const TIMEOUT_MS = 10000;

/**
 * Make an API request with timeout and error handling.
 * Returns parsed JSON on success, or a fallback value on failure.
 */
async function request(endpoint, options = {}, fallback = null) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      console.warn(`API ${endpoint} returned ${response.status}`);
      return fallback;
    }

    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);

    if (error.name === 'AbortError') {
      console.warn(`API ${endpoint} timed out after ${TIMEOUT_MS}ms`);
    } else {
      console.warn(`API ${endpoint} failed:`, error.message);
    }

    return fallback;
  }
}

/** Fetch active conflict zones. */
export async function fetchConflicts() {
  return request('/api/conflicts', {}, []);
}

/** Fetch live aircraft positions. Optional bounding box filter. */
export async function fetchAircraft(bbox = null) {
  let endpoint = '/api/aircraft';
  if (bbox) {
    const { lamin, lomin, lamax, lomax } = bbox;
    endpoint += `?lamin=${lamin}&lomin=${lomin}&lamax=${lamax}&lomax=${lomax}`;
  }
  return request(endpoint, {}, []);
}

/** Fetch missile/rocket events. */
export async function fetchMissiles() {
  return request('/api/missiles', {}, []);
}

/** Fetch earthquake data. */
export async function fetchEarthquakes() {
  return request('/api/earthquakes', {}, []);
}

/** Fetch weather alerts and data. */
export async function fetchWeather() {
  return request('/api/weather', {}, []);
}

/** Fetch known military bases. */
export async function fetchMilitaryBases() {
  return request('/api/military-bases', {}, []);
}

/** Fetch known nuclear sites. */
export async function fetchNuclearSites() {
  return request('/api/nuclear', {}, []);
}

/** Fetch strategic waterways. */
export async function fetchWaterways() {
  return request('/api/waterways', {}, []);
}

/** Fetch vessel positions. */
export async function fetchVessels() {
  return request('/api/vessels', {}, []);
}

/** Fetch news articles. Optional country filter. */
export async function fetchNews(country = null) {
  let endpoint = '/api/news';
  if (country) {
    endpoint += `?country=${encodeURIComponent(country)}`;
  }
  return request(endpoint, {}, []);
}

/** Fetch available live feeds. Optional country filter. */
export async function fetchLiveFeeds(country = null) {
  let endpoint = '/api/live-feeds';
  if (country) {
    endpoint += `?country=${encodeURIComponent(country)}`;
  }
  return request(endpoint, {}, []);
}

/** Fetch AI-generated intelligence insights. */
export async function fetchAIInsights() {
  return request('/api/ai-insights', {}, []);
}

/** Fetch all layer data in a single batch request. */
export async function fetchAllLayers() {
  return request('/api/layers/all', {}, null);
}

/** Fetch system status and data freshness. */
export async function fetchStatus() {
  return request('/api/status', {}, null);
}

/** Fetch sanctioned countries data. */
export async function fetchSanctions() {
  return request('/api/sanctions', {}, []);
}

export default {
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
  fetchAllLayers,
  fetchStatus,
  fetchSanctions,
};
