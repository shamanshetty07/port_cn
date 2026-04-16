/**
 * PortOrange — Sparkline Charts
 * 
 * Lightweight Canvas-based sparkline renderer for showing
 * port up/down timeline segments over the past 24 hours.
 */

const PortCharts = (() => {
    
    /**
     * Render a 24-hour timeline chart on a canvas element.
     * Events should be sorted by timestamp ascending.
     * 
     * @param {HTMLCanvasElement} canvas 
     * @param {Array} events - Array of {timestamp, previous_state, current_state}
     * @param {string} currentState - Current port oper_status
     */
    function renderTimeline(canvas, events, currentState) {
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);
        
        const width = rect.width;
        const height = rect.height;
        const padding = 4;
        const barHeight = height - padding * 2;
        const barY = padding;
        
        // Clear
        ctx.clearRect(0, 0, width, height);
        
        // Time range: last 24 hours
        const now = new Date();
        const start = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        const totalMs = now.getTime() - start.getTime();
        
        // Colors
        const colors = {
            up: '#22c55e',
            down: '#ef4444',
            unknown: '#334155',
            flapping: '#f59e0b'
        };
        
        if (!events || events.length === 0) {
            // No events — entire bar is current state
            ctx.fillStyle = colors[currentState] || colors.unknown;
            ctx.beginPath();
            ctx.roundRect(padding, barY, width - padding * 2, barHeight, 4);
            ctx.fill();
            
            _drawTimeLabels(ctx, width, height, start, now);
            return;
        }
        
        // Build segments from events
        const segments = [];
        let lastState = events[0].previous_state || 'unknown';
        let lastTime = start;
        
        for (const event of events) {
            const eventTime = new Date(event.timestamp);
            if (eventTime < start) {
                lastState = event.current_state;
                continue;
            }
            
            if (eventTime > lastTime) {
                segments.push({
                    state: lastState,
                    start: lastTime,
                    end: eventTime
                });
            }
            
            lastState = event.current_state;
            lastTime = eventTime;
        }
        
        // Final segment to now
        segments.push({
            state: lastState,
            start: lastTime,
            end: now
        });
        
        // Draw segments
        const drawWidth = width - padding * 2;
        
        for (let i = 0; i < segments.length; i++) {
            const seg = segments[i];
            const x1 = padding + ((seg.start.getTime() - start.getTime()) / totalMs) * drawWidth;
            const x2 = padding + ((seg.end.getTime() - start.getTime()) / totalMs) * drawWidth;
            const segWidth = Math.max(x2 - x1, 1);
            
            ctx.fillStyle = colors[seg.state] || colors.unknown;
            
            // Round corners on first and last segment
            if (i === 0 && i === segments.length - 1) {
                ctx.beginPath();
                ctx.roundRect(x1, barY, segWidth, barHeight, 4);
                ctx.fill();
            } else if (i === 0) {
                ctx.beginPath();
                ctx.roundRect(x1, barY, segWidth + 1, barHeight, [4, 0, 0, 4]);
                ctx.fill();
            } else if (i === segments.length - 1) {
                ctx.beginPath();
                ctx.roundRect(x1 - 1, barY, segWidth + 1, barHeight, [0, 4, 4, 0]);
                ctx.fill();
            } else {
                ctx.fillRect(x1, barY, segWidth + 1, barHeight);
            }
        }
        
        // Draw transition markers
        for (const event of events) {
            const eventTime = new Date(event.timestamp);
            if (eventTime < start) continue;
            
            const x = padding + ((eventTime.getTime() - start.getTime()) / totalMs) * drawWidth;
            ctx.strokeStyle = 'rgba(241, 245, 249, 0.4)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(x, barY);
            ctx.lineTo(x, barY + barHeight);
            ctx.stroke();
        }
        
        _drawTimeLabels(ctx, width, height, start, now);
    }
    
    function _drawTimeLabels(ctx, width, height, start, end) {
        ctx.fillStyle = '#64748b';
        ctx.font = '10px Inter, sans-serif';
        ctx.textBaseline = 'top';
        
        // Start label
        ctx.textAlign = 'left';
        ctx.fillText('-24h', 4, height - 14);
        
        // Middle
        ctx.textAlign = 'center';
        ctx.fillText('-12h', width / 2, height - 14);
        
        // End label
        ctx.textAlign = 'right';
        ctx.fillText('now', width - 4, height - 14);
    }
    
    // ── Public API ───────────────────────────────────────────
    return { renderTimeline };
})();
