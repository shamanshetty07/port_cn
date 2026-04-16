/**
 * PortOrange — API Client
 * 
 * REST fetch wrapper and WebSocket client with auto-reconnect.
 * Provides an event bus for decoupled component updates.
 */

const PortAPI = (() => {
    const BASE_URL = window.location.origin;
    const WS_URL = `ws://${window.location.host}/ws/live`;
    
    let _ws = null;
    let _wsReconnectTimer = null;
    let _wsReconnectDelay = 1000;
    const _maxReconnectDelay = 30000;
    
    // ── Event Bus ────────────────────────────────────────────
    const _listeners = {};
    
    function on(event, callback) {
        if (!_listeners[event]) _listeners[event] = [];
        _listeners[event].push(callback);
    }
    
    function off(event, callback) {
        if (!_listeners[event]) return;
        _listeners[event] = _listeners[event].filter(cb => cb !== callback);
    }
    
    function emit(event, data) {
        if (!_listeners[event]) return;
        _listeners[event].forEach(cb => {
            try { cb(data); } catch (e) { console.error(`Event handler error (${event}):`, e); }
        });
    }
    
    // ── REST Client ──────────────────────────────────────────
    async function fetchJSON(path, options = {}) {
        try {
            const response = await fetch(`${BASE_URL}${path}`, {
                headers: { 'Content-Type': 'application/json' },
                ...options
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error(`API Error (${path}):`, error);
            throw error;
        }
    }
    
    async function getDevices() {
        return fetchJSON('/api/devices');
    }
    
    async function getPorts(deviceId = null, status = null) {
        let path = '/api/ports';
        const params = new URLSearchParams();
        if (deviceId && deviceId !== 'all') params.set('device_id', deviceId);
        if (status) params.set('status', status);
        const qs = params.toString();
        if (qs) path += `?${qs}`;
        return fetchJSON(path);
    }
    
    async function getPort(portId) {
        return fetchJSON(`/api/ports/${portId}`);
    }
    
    async function getPortEvents(portId, limit = 20) {
        return fetchJSON(`/api/ports/${portId}/events?limit=${limit}`);
    }
    
    async function getPortEvents24h(portId) {
        return fetchJSON(`/api/ports/${portId}/events/24h`);
    }
    
    async function getEvents(limit = 50, offset = 0) {
        return fetchJSON(`/api/events?limit=${limit}&offset=${offset}`);
    }
    
    async function getStats() {
        return fetchJSON('/api/stats');
    }
    
    async function createMaintenanceWindow(data) {
        return fetchJSON('/api/maintenance', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    // ── WebSocket Client ─────────────────────────────────────
    function connectWebSocket() {
        if (_ws && (_ws.readyState === WebSocket.CONNECTING || _ws.readyState === WebSocket.OPEN)) {
            return;
        }
        
        try {
            _ws = new WebSocket(WS_URL);
            
            _ws.onopen = () => {
                console.log('🔌 WebSocket connected');
                _wsReconnectDelay = 1000;
                emit('ws:connected');
            };
            
            _ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    emit(`ws:${msg.type}`, msg.data);
                } catch (e) {
                    console.error('WS message parse error:', e);
                }
            };
            
            _ws.onclose = (event) => {
                console.log('🔌 WebSocket disconnected');
                emit('ws:disconnected');
                _scheduleReconnect();
            };
            
            _ws.onerror = (error) => {
                console.error('WS error:', error);
                emit('ws:error', error);
            };
        } catch (e) {
            console.error('WS connection failed:', e);
            _scheduleReconnect();
        }
    }
    
    function _scheduleReconnect() {
        if (_wsReconnectTimer) clearTimeout(_wsReconnectTimer);
        const delay = Math.min(_wsReconnectDelay, _maxReconnectDelay);
        _wsReconnectTimer = setTimeout(() => {
            console.log(`🔄 Reconnecting WebSocket (${delay}ms delay)...`);
            connectWebSocket();
        }, delay);
        _wsReconnectDelay *= 1.5;
    }
    
    function disconnectWebSocket() {
        if (_wsReconnectTimer) clearTimeout(_wsReconnectTimer);
        if (_ws) {
            _ws.close();
            _ws = null;
        }
    }
    
    // ── Public API ───────────────────────────────────────────
    return {
        on, off, emit,
        getDevices, getPorts, getPort,
        getPortEvents, getPortEvents24h,
        getEvents, getStats,
        createMaintenanceWindow,
        connectWebSocket, disconnectWebSocket
    };
})();
