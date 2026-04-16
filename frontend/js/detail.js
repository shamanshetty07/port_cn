/**
 * PortOrange — Port Detail Panel
 * 
 * Slide-in panel showing port details, recent events,
 * and 24-hour timeline chart.
 */

const PortDetail = (() => {
    let _currentPortId = null;
    let _currentDevice = null;
    let _isOpen = false;
    
    /**
     * Initialize event listeners for the detail panel.
     */
    function init() {
        const overlay = document.getElementById('detail-overlay');
        const closeBtn = document.getElementById('detail-close');
        
        if (overlay) overlay.addEventListener('click', close);
        if (closeBtn) closeBtn.addEventListener('click', close);
        
        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && _isOpen) close();
        });
    }
    
    /**
     * Open the detail panel for a specific port.
     */
    async function open(portId, device) {
        _currentPortId = portId;
        _currentDevice = device;
        _isOpen = true;
        
        // Show panel
        const panel = document.getElementById('detail-panel');
        const overlay = document.getElementById('detail-overlay');
        panel.classList.add('active');
        overlay.classList.add('active');
        
        // Set loading state
        document.getElementById('detail-port-name').textContent = 'Loading...';
        document.getElementById('detail-port-id').textContent = portId;
        
        try {
            // Fetch port data and events in parallel
            const [portData, eventsData, events24hData] = await Promise.all([
                PortAPI.getPort(portId),
                PortAPI.getPortEvents(portId, 20),
                PortAPI.getPortEvents24h(portId)
            ]);
            
            _renderPortInfo(portData, device);
            _renderEvents(eventsData.events || []);
            _renderChart(events24hData.events || [], portData.oper_status);
        } catch (error) {
            console.error('Failed to load port details:', error);
            document.getElementById('detail-port-name').textContent = 'Error loading data';
        }
    }
    
    /**
     * Close the detail panel.
     */
    function close() {
        _isOpen = false;
        _currentPortId = null;
        
        const panel = document.getElementById('detail-panel');
        const overlay = document.getElementById('detail-overlay');
        panel.classList.remove('active');
        overlay.classList.remove('active');
    }
    
    /**
     * Update the detail panel if it's showing the same port.
     */
    function updateIfOpen(portId, data) {
        if (!_isOpen || _currentPortId !== portId) return;
        
        // Re-fetch and re-render
        open(portId, _currentDevice);
    }
    
    // ── Private Rendering ────────────────────────────────────
    
    function _renderPortInfo(port, device) {
        // Port name
        const name = port.interface_name || `Port ${port.port_index}`;
        document.getElementById('detail-port-name').textContent = name;
        document.getElementById('detail-port-id').textContent = port.id;
        
        // Status indicator
        const statusDot = document.getElementById('detail-status-dot');
        const statusText = document.getElementById('detail-status-text');
        
        statusDot.className = 'detail-status-dot';
        if (port.is_flapping) {
            statusDot.classList.add('flapping');
            statusText.textContent = 'Flapping';
            statusText.style.color = 'var(--color-flapping)';
        } else if (port.oper_status === 'up') {
            statusDot.classList.add('up');
            statusText.textContent = 'Operational';
            statusText.style.color = 'var(--color-up)';
        } else if (port.oper_status === 'down') {
            statusDot.classList.add('down');
            statusText.textContent = 'Down';
            statusText.style.color = 'var(--color-down)';
        } else {
            statusText.textContent = 'Unknown';
            statusText.style.color = 'var(--color-unknown)';
        }
        
        // Meta values
        const deviceName = device ? device.name : port.device_id;
        document.getElementById('detail-device-name').textContent = deviceName;
        document.getElementById('detail-interface').textContent = port.interface_name || '—';
        document.getElementById('detail-speed').textContent = port.speed || '—';
        document.getElementById('detail-criticality').textContent = 
            (port.criticality || 'standard').toUpperCase();
        
        // Uptime
        if (port.uptime_since && port.oper_status === 'up') {
            const uptimeStr = _formatDuration(port.uptime_since);
            document.getElementById('detail-uptime').textContent = uptimeStr;
        } else {
            document.getElementById('detail-uptime').textContent = 
                port.oper_status === 'down' ? 'N/A (Down)' : '—';
        }
        
        // Last change
        if (port.last_change_at) {
            document.getElementById('detail-last-change').textContent = 
                _formatTimestamp(port.last_change_at);
        } else {
            document.getElementById('detail-last-change').textContent = '—';
        }
    }
    
    function _renderEvents(events) {
        const container = document.getElementById('detail-events');
        
        if (!events || events.length === 0) {
            container.innerHTML = '<p class="no-events">No events recorded</p>';
            return;
        }
        
        container.innerHTML = events.map(event => `
            <div class="event-item">
                <span class="event-state ${event.previous_state}">${event.previous_state}</span>
                <span class="event-arrow">→</span>
                <span class="event-state ${event.current_state}">${event.current_state}</span>
                <span class="event-latency">${event.polling_latency_ms || 0}ms</span>
                <span class="event-time">${_formatTimestamp(event.timestamp)}</span>
            </div>
        `).join('');
    }
    
    function _renderChart(events, currentState) {
        const canvas = document.getElementById('detail-chart');
        if (!canvas) return;
        
        // Resize canvas to container
        const container = document.getElementById('detail-chart-container');
        canvas.style.width = '100%';
        canvas.style.height = '60px';
        
        PortCharts.renderTimeline(canvas, events, currentState);
    }
    
    function _formatTimestamp(isoString) {
        if (!isoString) return '—';
        try {
            const date = new Date(isoString);
            const now = new Date();
            const diffMs = now - date;
            
            if (diffMs < 60000) return `${Math.floor(diffMs / 1000)}s ago`;
            if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)}m ago`;
            if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)}h ago`;
            
            return date.toLocaleString('en-US', {
                month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit'
            });
        } catch {
            return isoString.substring(0, 19);
        }
    }
    
    function _formatDuration(sinceIso) {
        if (!sinceIso) return '—';
        try {
            const since = new Date(sinceIso);
            const now = new Date();
            const diffMs = now - since;
            
            const hours = Math.floor(diffMs / 3600000);
            const minutes = Math.floor((diffMs % 3600000) / 60000);
            
            if (hours > 24) {
                const days = Math.floor(hours / 24);
                return `${days}d ${hours % 24}h`;
            }
            return `${hours}h ${minutes}m`;
        } catch {
            return '—';
        }
    }
    
    // ── Public API ───────────────────────────────────────────
    return { init, open, close, updateIfOpen };
})();
