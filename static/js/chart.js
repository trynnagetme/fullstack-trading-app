// DOM elements
const symbolSelect = document.getElementById('symbol-select');
const chartContainer = document.getElementById('chart-container');
const loadingOverlay = document.getElementById('loading-overlay');
const errorMessageDiv = document.getElementById('error-message');

// Chart state
let chart = null;
let candlestickSeries = null;
let volumeSeries = null;
let currentResolution = 'D';
let currentSymbol = null;

// Helper: show/hide loading
function setLoading(show) {
    loadingOverlay.style.display = show ? 'flex' : 'none';
}

// Helper: show error message
function showError(msg) {
    errorMessageDiv.textContent = msg;
    errorMessageDiv.style.display = 'block';
    setTimeout(() => {
        errorMessageDiv.style.display = 'none';
    }, 5000);
}

// Initialize Lightweight Chart
function initChart() {
    if (typeof LightweightCharts === 'undefined') {
        console.warn('LightweightCharts not loaded yet, retrying...');
        setTimeout(initChart, 500);
        return;
    }
    
    const chartContainer = document.getElementById('chart-container');
    if (!chartContainer) {
        console.error('Chart container not found');
        return;
    }
    
    const width = chartContainer.clientWidth;
    const height = chartContainer.clientHeight;
    if (width === 0 || height === 0) {
        setTimeout(initChart, 100);
        return;
    }
    
    try {
        chart = LightweightCharts.createChart(chartContainer, {
            width, height,
            layout: { backgroundColor: '#131722', textColor: '#d1d4dc', fontSize: 12 },
            grid: { vertLines: { color: '#2a2e39' }, horzLines: { color: '#2a2e39' } },
            crosshair: { mode: 'normal', vertLine: { width: 1, color: '#758696', style: 'dotted' }, horzLine: { width: 1, color: '#758696', style: 'dotted' } },
            rightPriceScale: { borderColor: '#2a2e39', scaleMargins: { top: 0.1, bottom: 0.1 } },
            timeScale: { borderColor: '#2a2e39', timeVisible: true, secondsVisible: false, tickMarkFormatter: (time) => new Date(time * 1000).toLocaleDateString() },
        });
        
        candlestickSeries = chart.addSeries('Candlestick', {
            upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
            wickUpColor: '#26a69a', wickDownColor: '#ef5350',
            priceFormat: { type: 'price', precision: 2, minMove: 0.01 }
        });
        
        volumeSeries = chart.addSeries('Histogram', {
            color: '#26a69a', priceFormat: { type: 'volume' },
            priceScaleId: '', scaleMargins: { top: 0.8, bottom: 0 }
        });
        
        document.getElementById('loading-overlay').style.display = 'none';
        window.addEventListener('resize', () => chart?.applyOptions({ width: chartContainer.clientWidth, height: chartContainer.clientHeight }));
        
        console.log('Chart initialized with v5 CDN');
    } catch (error) {
        console.error('Chart init error:', error);
        showError('Chart init failed: ' + error.message);
    }
}
// Load list of stocks from backend
async function loadStockList() {
    try {
        const response = await fetch('/api/stocks');
        if (!response.ok) throw new Error('Failed to load stocks');
        const stocks = await response.json();
        
        if (stocks.length === 0) {
            symbolSelect.innerHTML = '<option value="">No stocks found</option>';
            showError('No stocks in database. Run populate_stocks.py first.');
            return;
        }
        
        symbolSelect.innerHTML = stocks.map(s => 
            `<option value="${s.symbol}">${s.symbol} - ${s.name}</option>`
        ).join('');
        
        // Load first symbol by default
        if (stocks.length > 0 && !currentSymbol) {
            currentSymbol = stocks[0].symbol;
            loadChartData(currentSymbol);
        }
    } catch (error) {
        console.error('Error loading stocks:', error);
        symbolSelect.innerHTML = '<option value="">Error loading stocks</option>';
        showError('Could not load stock list. Is the backend running?');
    }
}

// Fetch OHLC data from your FastAPI endpoint
async function loadChartData(symbol, resolution = 'D') {
    if (!symbol) return;
    
    setLoading(true);
    
    try {
        // Calculate date range: last 2 years (you can adjust)
        const to = Math.floor(Date.now() / 1000);
        const from = to - (2 * 365 * 24 * 60 * 60); // ~2 years
        
        const url = `/api/bars/${symbol}?resolution=${resolution}&from=${from}&to=${to}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.s === 'error') {
            throw new Error(data.errmsg || 'Unknown error from server');
        }
        
        if (data.s === 'no_data' || !data.t || data.t.length === 0) {
            showError(`No price data for ${symbol}. Run populate_prices.py first.`);
            candlestickSeries.setData([]);
            volumeSeries.setData([]);
            setLoading(false);
            return;
        }
        
        // Transform data for Lightweight Charts
        const candleData = data.t.map((timestamp, idx) => ({
            time: timestamp,  // Lightweight Charts expects seconds
            open: data.o[idx],
            high: data.h[idx],
            low: data.l[idx],
            close: data.c[idx],
        }));
        
        const volumeData = data.t.map((timestamp, idx) => ({
            time: timestamp,
            value: data.v[idx],
            color: data.c[idx] >= data.o[idx] ? '#26a69a' : '#ef5350',
        }));
        
        candlestickSeries.setData(candleData);
        volumeSeries.setData(volumeData);
        
        // Fit all data into view
        chart.timeScale().fitContent();
        
    } catch (error) {
        console.error('Error loading chart data:', error);
        showError(`Failed to load data for ${symbol}: ${error.message}`);
        candlestickSeries.setData([]);
        volumeSeries.setData([]);
    } finally {
        setLoading(false);
    }
}

// Handle symbol change
function onSymbolChange() {
    const newSymbol = symbolSelect.value;
    if (newSymbol && newSymbol !== currentSymbol) {
        currentSymbol = newSymbol;
        loadChartData(currentSymbol, currentResolution);
    }
}

// Handle resolution change (only D for now)
function onResolutionChange(resolution) {
    currentResolution = resolution;
    if (currentSymbol) {
        loadChartData(currentSymbol, resolution);
    }
    // Update active button style
    document.querySelectorAll('.timeframe-btn').forEach(btn => {
        if (btn.dataset.resolution === resolution) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

// Event listeners
symbolSelect.addEventListener('change', onSymbolChange);

document.querySelectorAll('.timeframe-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        onResolutionChange(btn.dataset.resolution);
    });
});

// Initialize
initChart();
loadStockList();