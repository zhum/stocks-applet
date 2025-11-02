# Stock Applet for Cinnamon

A modern Cinnamon desktop applet that monitors stock prices with real-time updates, historical charts, and comprehensive customization options.

## Features

- **📈 Real-time Stock Monitoring**: Live price updates with configurable intervals
- **🎨 Interactive Charts**: Popup charts with price history and trend analysis
- **💡 Smart Tooltips**: Current price, daily range, and historical extremes with timestamps
- **🎨 Customizable Colors**: Line and fill colors with color picker interface
- **📊 Symbol Display**: Optional stock symbol overlay on charts
- **🔐 Secure API**: Native HTTPS requests (no curl dependency)
- **💾 Data Persistence**: Local price history storage and management
- **⚡ Performance**: Lightweight with efficient memory usage

## Installation

### Automatic Installation

1. Copy the applet to your user directory:

   ```bash
   mkdir -p ~/.local/share/cinnamon/applets/
   cp -r stock-applet@cinnamon ~/.local/share/cinnamon/applets/
   ```

2. Restart Cinnamon:

   ```bash
   # Press Alt+F2, type 'r', press Enter
   # OR restart Cinnamon manually
   cinnamon --replace &
   ```

3. Add to panel:
   - Right-click on Cinnamon panel
   - Select "Applets"
   - Find "Stock Applet" in the Downloaded tab
   - Click the '+' button to add

### Manual Installation (Development)

If you're developing or testing:

```bash
# Install to development location
ln -sf $(pwd)/stock-applet@cinnamon ~/.local/share/cinnamon/applets/

# Restart Cinnamon and add through Applets menu
```

## Requirements

- **Desktop**: Cinnamon Desktop Environment
- **API**: Finnhub API token ([get free token](https://finnhub.io))
- **Network**: Internet connection for stock data
- **Dependencies**: All dependencies are built into Cinnamon (GJS, Soup, etc.)

## Configuration

### Initial Setup

1. Get a free API token from [Finnhub.io](https://finnhub.io)
2. Right-click the applet → "Configure..."
3. Enter your API token in the "API Token" field
4. Set your preferred stock symbol (e.g., NVDA, AAPL, TSLA)

### Settings Options

Access settings by right-clicking the applet and selecting "Configure...":

| Setting | Description | Options |
|---------|-------------|---------|
| **API Token** | Your Finnhub API key | Required for data fetching |
| **Stock Symbol** | Symbol to monitor | NVDA, AAPL, TSLA, MSFT, etc. |
| **Update Interval** | Data refresh frequency | 1-60 minutes (default: 10) |
| **Show Current Price** | Display current price | On/Off |
| **Show Daily Range** | Display daily high/low | On/Off |
| **Show Price Chart** | Enable popup chart | On/Off |
| **Chart Width** | Chart width in pixels | 100-400px (default: 200) |
| **Chart Height** | Chart height in pixels | 50-200px (default: 100) |
| **Chart Line Color** | Color for chart line | Color picker |
| **Chart Fill Color** | Color for chart fill area | Color picker with transparency |
| **Show Symbol on Chart** | Display symbol on chart | On/Off |

## Usage

### Panel Display

**Text Mode**: `NVDA: $875.50 [860.25..890.75]`

- Stock symbol with current price
- Daily trading range in brackets (optional)

### Interactive Charts

Click the applet to show popup chart featuring:

- Historical price trends with customizable colors
- Fill area with transparency support
- Price labels (min, max, current)
- Optional stock symbol display
- Real-time updates

### Comprehensive Tooltips

Hover over the applet for detailed information:

- **Current Data**: Symbol, current price, daily range
- **Historical Data**: Chart period lowest/highest prices with timestamps
- **Format**: Timestamps in "MMM DD HH:MM" format for easy reading

### Error Handling

- **"No Token"**: API token not configured
- **"Error"**: Network or API issues
- Graceful fallback with informative messages

## Technical Details

### Data Storage

- **Location**: `~/.local/share/cinnamon/applets/stock-applet@cinnamon/price_history.txt`
- **Format**: `timestamp: price` (one entry per line)
- **Retention**: Last 144 data points (24 hours at 10-minute intervals)
- **Automatic Cleanup**: Old data rotated out automatically

### Network Architecture

- **HTTP Library**: Native GJS Soup library
- **Security**: HTTPS requests with proper error handling
- **Timeout**: 10-second timeout for reliability
- **No External Dependencies**: No curl or external tools required

### Performance Features

- **Memory Efficient**: Automatic data cleanup and rotation
- **Non-blocking**: Asynchronous API calls don't freeze UI
- **Lightweight**: Minimal CPU and memory footprint
- **Responsive**: Immediate UI updates for settings changes

### Color Customization

- **Line Color**: Full color picker with RGBA support
- **Fill Color**: Separate fill color with transparency control
- **Real-time Preview**: Colors update immediately in preferences
- **Persistence**: Color settings saved automatically

## File Structure

```text
stock-applet@cinnamon/
├── applet.js              # Main applet implementation
├── metadata.json          # Applet metadata and compatibility
├── settings-schema.json   # Configuration schema
└── README.md             # This documentation
```

## API Integration

### Finnhub API

- **Endpoint**: `https://finnhub.io/api/v1/quote`
- **Authentication**: Token-based API key
- **Rate Limits**: Free tier provides sufficient quota for personal use
- **Data Fields**: Current price (c), daily high (h), daily low (l)

### Example API Response

```json
{
  "c": 875.50,    // Current price
  "h": 890.75,    // Daily high
  "l": 860.25,    // Daily low
  "o": 870.00,    // Open price
  "pc": 865.30,   // Previous close
  "t": 1640995200 // Timestamp
}
```

## Development

### Testing Changes

```bash
# Edit applet files
nano applet.js

# Restart Cinnamon to reload
killall cinnamon-session
# OR press Alt+F2, type 'r', press Enter

# Check logs for errors
journalctl -f | grep cinnamon
```

### Debugging

- **Console Logs**: Check with `journalctl -f | grep stock-applet`
- **Settings Issues**: Remove and re-add applet
- **API Problems**: Verify token and network connectivity

## Troubleshooting

### Common Issues

#### No Data Showing

- ✅ Verify API token in settings
- ✅ Check internet connection
- ✅ Use valid stock symbols (AAPL, NVDA, MSFT)
- ✅ Check Cinnamon logs for errors

#### Charts Not Displaying

- ✅ Enable "Show Price Chart" in settings
- ✅ Verify chart dimensions are reasonable
- ✅ Check if popup is opening off-screen

#### Settings Not Saving

- ✅ Restart Cinnamon after making changes
- ✅ Check file permissions in ~/.local/share/cinnamon/
- ✅ Remove and re-add applet if persistent

#### Performance Issues

- ✅ Increase update interval for slower networks
- ✅ Reduce chart size if system is slow
- ✅ Check for memory leaks in system monitor

### Getting Help

1. Check Cinnamon logs: `journalctl -f | grep cinnamon`
2. Verify applet is loaded: Look for stock-applet messages
3. Test API manually: `curl "https://finnhub.io/api/v1/quote?symbol=AAPL&token=YOUR_TOKEN"`
4. Reset settings: Remove applet and re-add

## Version History

- **v2.0**: Complete rewrite with modern features
  - Native HTTPS requests (no curl dependency)
  - Customizable chart colors
  - Comprehensive tooltips with timestamps
  - Optional symbol display on charts
  - Enhanced error handling

- **v1.0**: Initial release
  - Basic stock price monitoring
  - Simple chart display
  - Text mode support

## License

Apache-2.0 License - see [LICENSE](../LICENSE) for details.

---

**Part of the Stock Applet project - providing real-time stock monitoring for Linux desktop environments.**
