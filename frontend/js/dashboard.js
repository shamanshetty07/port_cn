/**
 * PortOrange — Dashboard Renderer
 * 
 * Renders the port grid grouped by device. Each port cell shows
 * index, interface name, and a color-coded status indicator.
 * Handles live updates via WebSocket events.
 */

const Dashboard = (() => {
    let _devices = [];
    let _ports = [];
    let _portsByDevice = {};
    
    /**
     * Initialize the dashboard with data from the API.
     */
    async function init() {
        await refresh();
    }
    
    /**
     * Full refresh: fetch devices and ports, re-render everything.
     */
    async function refresh() {
        try {
            const [devData, portData] = await Promise.all([
                PortAPI.getDevices(),
                PortAPI.getPorts()
            ]);
            
            _devices = devData.devices || [];
            _ports = portData.ports || [];
            
            // Group ports by device
            _portsByDevice = {};
            _ports.forEach(port => {
                if (!_portsByDevice[port.device_id]) {
                    _portsByDevice[port.device_id] = [];
                }
                _portsByDevice[port.device_id].push(port);
            });
            
            _renderAll();
            _updateDeviceFilter();
        } catch (error) {
            console.error('Dashboard refresh failed:', error);
        }
    }
    
    /**
     * Update a single port's status in the grid (called from WebSocket).
     */
    function updatePort(data) {
        const { port_id, current_state, is_flapping } = data;
        
        const cell = document.getElementById(`port-${port_id}`);
        if (!cell) return;
        
        // Remove old status classes
        cell.classList.remove('status-up', 'status-down', 'status-unknown', 'status-flapping');
        
        // Add new status
        if (is_flapping) {
            cell.classList.add('status-flapping');
        } else {
            cell.classList.add(`status-${current_state}`);
        }
        
        // Trigger flash animation
        cell.classList.remove('state-changed');
        void cell.offsetWidth; // Force reflow
        cell.classList.add('state-changed');
        
        // Update in-memory port data
        const port = _ports.find(p => p.id === port_id);
        if (port) {
            port.oper_status = current_state;
            port.is_flapping = is_flapping;
        }
        
        // Update device stats
        _updateDeviceStats(data.device_id);
    }
    
    /**
     * Update the global stats bar.
     */
    function updateStats(stats) {
        _animateValue('stat-up-value', stats.ports_up || 0);
        _animateValue('stat-down-value', stats.ports_down || 0);
        _animateValue('stat-unknown-value', stats.ports_unknown || 0);
        _animateValue('stat-flapping-value', stats.ports_flapping || 0);
    }
    
    /**
     * Filter displayed devices.
     */
    function filterByDevice(deviceId) {
        const groups = document.querySelectorAll('.device-group');
        groups.forEach(group => {
            if (deviceId === 'all' || group.dataset.deviceId === deviceId) {
                group.style.display = '';
            } else {
                group.style.display = 'none';
            }
        });
    }
    
    // ── Private Rendering ────────────────────────────────────
    
    function _renderAll() {
        const container = document.getElementById('devices-container');
        const loading = document.getElementById('loading-state');
        
        if (loading) loading.classList.add('hidden');
        
        // Clear existing device groups (keep loading state)
        const existing = container.querySelectorAll('.device-group');
        existing.forEach(el => el.remove());
        
        // Render each device group
        _devices.forEach(device => {
            const ports = _portsByDevice[device.id] || [];
            const group = _createDeviceGroup(device, ports);
            container.appendChild(group);
        });
    }
    
    function _createDeviceGroup(device, ports) {
        const group = document.createElement('div');
        group.className = 'device-group';
        group.dataset.deviceId = device.id;
        group.id = `device-${device.id}`;
        
        // Header
        const header = document.createElement('div');
        header.className = 'device-header';
        
        const portsUp = ports.filter(p => p.oper_status === 'up').length;
        const portsDown = ports.filter(p => p.oper_status === 'down').length;
        const portsFlapping = ports.filter(p => p.is_flapping).length;
        
        header.innerHTML = `
            <div class="device-info">
                <span class="device-status-dot ${device.is_reachable ? '' : 'unreachable'}"></span>
                <div>
                    <div class="device-name">${_escapeHtml(device.name)}</div>
                    <div class="device-host">${_escapeHtml(device.host)} · ${device.driver_type}</div>
                </div>
            </div>
            <div class="device-stats" id="device-stats-${device.id}">
                <span class="device-stat"><span class="dot-up" style="width:6px;height:6px;border-radius:50%;display:inline-block;background:var(--color-up)"></span> <span class="count" data-stat="up">${portsUp}</span></span>
                <span class="device-stat"><span class="dot-down" style="width:6px;height:6px;border-radius:50%;display:inline-block;background:var(--color-down)"></span> <span class="count" data-stat="down">${portsDown}</span></span>
                ${portsFlapping > 0 ? `<span class="device-stat"><span style="width:6px;height:6px;border-radius:50%;display:inline-block;background:var(--color-flapping)"></span> <span class="count" data-stat="flapping">${portsFlapping}</span></span>` : ''}
                <span class="device-stat" style="color:var(--text-muted)">${ports.length} ports</span>
            </div>
        `;
        
        // Port Grid
        const grid = document.createElement('div');
        grid.className = 'port-grid';
        grid.id = `grid-${device.id}`;
        
        ports.sort((a, b) => a.port_index - b.port_index).forEach(port => {
            const cell = _createPortCell(port, device);
            grid.appendChild(cell);
        });
        
        group.appendChild(header);
        group.appendChild(grid);
        return group;
    }
    
    function _createPortCell(port, device) {
        const cell = document.createElement('div');
        cell.className = `port-cell`;
        cell.id = `port-${port.id}`;
        
        if (port.is_flapping) {
            cell.classList.add('status-flapping');
        } else {
            cell.classList.add(`status-${port.oper_status}`);
        }
        
        // Short interface name for display
        let shortIface = port.interface_name || '';
        shortIface = shortIface
            .replace('GigabitEthernet', 'Gi')
            .replace('TenGigabitEthernet', 'Te')
            .replace('FastEthernet', 'Fa');
        
        cell.innerHTML = `
            <span class="port-status-dot"></span>
            <span class="port-index">${port.port_index}</span>
            <span class="port-iface">${_escapeHtml(shortIface)}</span>
        `;
        
        cell.addEventListener('click', () => {
            PortDetail.open(port.id, device);
        });
        
        return cell;
    }
    
    function _updateDeviceStats(deviceId) {
        const ports = _portsByDevice[deviceId] || [];
        const statsEl = document.getElementById(`device-stats-${deviceId}`);
        if (!statsEl) return;
        
        const upEl = statsEl.querySelector('[data-stat="up"]');
        const downEl = statsEl.querySelector('[data-stat="down"]');
        
        if (upEl) upEl.textContent = ports.filter(p => p.oper_status === 'up').length;
        if (downEl) downEl.textContent = ports.filter(p => p.oper_status === 'down').length;
    }
    
    function _updateDeviceFilter() {
        const select = document.getElementById('device-filter');
        if (!select) return;
        
        // Preserve selection
        const currentValue = select.value;
        
        // Clear all except "All Devices"
        while (select.options.length > 1) {
            select.remove(1);
        }
        
        _devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.id;
            option.textContent = device.name;
            select.appendChild(option);
        });
        
        select.value = currentValue || 'all';
    }
    
    function _animateValue(elementId, newValue) {
        const el = document.getElementById(elementId);
        if (!el) return;
        
        const current = parseInt(el.textContent) || 0;
        if (current === newValue) return;
        
        el.textContent = newValue;
        el.style.transform = 'scale(1.2)';
        el.style.transition = 'transform 0.2s ease';
        setTimeout(() => {
            el.style.transform = 'scale(1)';
        }, 200);
    }
    
    function _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
    
    // ── Public API ───────────────────────────────────────────
    return {
        init, refresh, updatePort, updateStats, filterByDevice
    };
})();
