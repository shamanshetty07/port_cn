/**
 * PortOrange — Main Application Controller
 * 
 * Initializes all modules, wires up event listeners,
 * manages WebSocket events, and handles auto-refresh fallback.
 */

(function() {
    'use strict';
    
    let _refreshTimer = null;
    const REFRESH_INTERVAL = 10000; // 10 second fallback
    
    // ── Initialization ───────────────────────────────────────
    
    async function init() {
        console.log('🍊 PortOrange Dashboard initializing...');
        
        // Initialize modules
        PortDetail.init();
        
        // Wire up event handlers
        _setupWebSocketHandlers();
        _setupUIHandlers();
        
        // Connect WebSocket
        PortAPI.connectWebSocket();
        
        // Initial data load
        await Dashboard.init();
        await _refreshStats();
        
        // Start fallback polling (in case WebSocket drops)
        _startFallbackRefresh();
        
        console.log('🍊 PortOrange Dashboard ready');
    }
    
    // ── WebSocket Event Handlers ─────────────────────────────
    
    function _setupWebSocketHandlers() {
        // Connection status
        PortAPI.on('ws:connected', () => {
            _updateConnectionIndicator('connected');
            // Stop fallback polling when WS is active
            _stopFallbackRefresh();
        });
        
        PortAPI.on('ws:disconnected', () => {
            _updateConnectionIndicator('disconnected');
            // Start fallback polling
            _startFallbackRefresh();
        });
        
        PortAPI.on('ws:error', () => {
            _updateConnectionIndicator('disconnected');
        });
        
        // State change events
        PortAPI.on('ws:state_change', (data) => {
            // Update port in grid
            Dashboard.updatePort(data);
            
            // Update detail panel if open for this port
            PortDetail.updateIfOpen(data.port_id, data);
            
            // Show toast notification
            _showToast(data);
        });
        
        // Stats updates
        PortAPI.on('ws:stats_update', (stats) => {
            Dashboard.updateStats(stats);
        });
    }
    
    // ── UI Event Handlers ────────────────────────────────────
    
    function _setupUIHandlers() {
        // Device filter
        const deviceFilter = document.getElementById('device-filter');
        if (deviceFilter) {
            deviceFilter.addEventListener('change', (e) => {
                Dashboard.filterByDevice(e.target.value);
            });
        }
    }
    
    // ── Connection Indicator ─────────────────────────────────
    
    function _updateConnectionIndicator(status) {
        const indicator = document.getElementById('ws-indicator');
        if (!indicator) return;
        
        indicator.className = `connection-indicator ${status}`;
        const label = indicator.querySelector('.ws-label');
        
        switch (status) {
            case 'connected':
                label.textContent = 'Live';
                break;
            case 'disconnected':
                label.textContent = 'Reconnecting';
                break;
            default:
                label.textContent = 'Connecting';
        }
    }
    
    // ── Toast Notifications ──────────────────────────────────
    
    function _showToast(data) {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        const toast = document.createElement('div');
        let toastClass = `toast-${data.current_state}`;
        if (data.is_flapping) toastClass = 'toast-flapping';
        
        toast.className = `toast ${toastClass}`;
        
        const deviceName = data.device_name || data.device_id;
        const time = new Date().toLocaleTimeString('en-US', {
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
        
        toast.innerHTML = `
            <span class="toast-dot"></span>
            <span class="toast-text">
                <strong>${_escapeHtml(deviceName)}</strong> · 
                Port ${data.port_index} 
                ${data.previous_state} → <strong>${data.current_state}</strong>
            </span>
            <span class="toast-time">${time}</span>
        `;
        
        container.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.classList.add('toast-exit');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
        
        // Keep max 5 toasts
        while (container.children.length > 5) {
            container.firstChild.remove();
        }
    }
    
    // ── Fallback Refresh ─────────────────────────────────────
    
    function _startFallbackRefresh() {
        if (_refreshTimer) return;
        _refreshTimer = setInterval(async () => {
            try {
                await Dashboard.refresh();
                await _refreshStats();
            } catch (e) {
                console.error('Fallback refresh failed:', e);
            }
        }, REFRESH_INTERVAL);
    }
    
    function _stopFallbackRefresh() {
        if (_refreshTimer) {
            clearInterval(_refreshTimer);
            _refreshTimer = null;
        }
    }
    
    async function _refreshStats() {
        try {
            const stats = await PortAPI.getStats();
            Dashboard.updateStats(stats);
        } catch (e) {
            // Silently fail
        }
    }
    
    // ── Utilities ────────────────────────────────────────────
    
    function _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
    
    // ── Boot ─────────────────────────────────────────────────
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
