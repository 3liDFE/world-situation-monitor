/**
 * Custom hook for WebSocket connection with auto-reconnect.
 * Provides real-time updates for all intelligence layers.
 */

import { useEffect, useRef, useState, useCallback } from 'react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
const MAX_RECONNECT_DELAY = 30000;
const INITIAL_RECONNECT_DELAY = 1000;

export default function useWebSocket(onMessage) {
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const wsRef = useRef(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY);
  const reconnectTimeoutRef = useRef(null);
  const mountedRef = useRef(true);
  const onMessageRef = useRef(onMessage);

  // Keep callback ref current without re-triggering effect
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.onopen = null;
      if (wsRef.current.readyState < 2) {
        wsRef.current.close();
      }
    }

    setConnectionStatus('reconnecting');

    try {
      const ws = new WebSocket(`${WS_URL}/ws/live`);
      wsRef.current = ws;

      let pingInterval = null;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setConnectionStatus('connected');
        reconnectDelayRef.current = INITIAL_RECONNECT_DELAY;

        // Send subscription message
        try {
          ws.send(JSON.stringify({
            action: 'subscribe',
            layers: ['conflicts', 'aircraft', 'missiles', 'earthquakes', 'weather', 'news', 'ai_insights', 'all'],
          }));
        } catch (e) {
          // Ignore send errors on fresh connections
        }

        // Start keepalive ping
        pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            try { ws.send(JSON.stringify({ action: 'ping' })); } catch {}
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const data = JSON.parse(event.data);
          if (onMessageRef.current) {
            onMessageRef.current(data);
          }
        } catch (e) {
          console.warn('WebSocket message parse error:', e);
        }
      };

      ws.onerror = () => {
        // Error will be followed by onclose, so we handle reconnect there
      };

      ws.onclose = () => {
        if (pingInterval) clearInterval(pingInterval);
        if (!mountedRef.current) return;
        setConnectionStatus('disconnected');
        scheduleReconnect();
      };
    } catch (error) {
      console.warn('WebSocket connection error:', error);
      setConnectionStatus('disconnected');
      scheduleReconnect();
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    const delay = reconnectDelayRef.current;
    reconnectTimeoutRef.current = setTimeout(() => {
      if (mountedRef.current) {
        connect();
      }
    }, delay);

    // Exponential backoff with jitter
    reconnectDelayRef.current = Math.min(
      delay * 1.5 + Math.random() * 1000,
      MAX_RECONNECT_DELAY
    );
  }, [connect]);

  const sendMessage = useCallback((message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify(message));
      } catch (e) {
        console.warn('WebSocket send error:', e);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }

      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current.onopen = null;
        if (wsRef.current.readyState < 2) {
          wsRef.current.close();
        }
      }
    };
  }, [connect]);

  return {
    connectionStatus,
    sendMessage,
  };
}
