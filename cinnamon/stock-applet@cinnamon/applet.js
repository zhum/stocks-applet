const Applet = imports.ui.applet;
const PopupMenu = imports.ui.popupMenu;
const St = imports.gi.St;
const GLib = imports.gi.GLib;
const Soup = imports.gi.Soup;
const Util = imports.misc.util;
const Lang = imports.lang;
const Settings = imports.ui.settings;
const Mainloop = imports.mainloop;
const Cairo = imports.cairo;
const Clutter = imports.gi.Clutter;

function StockApplet(orientation, panel_height, instance_id) {
    this._init(orientation, panel_height, instance_id);
}

StockApplet.prototype = {
    __proto__: Applet.Applet.prototype,

    _init: function(orientation, panel_height, instance_id) {
        Applet.Applet.prototype._init.call(this, orientation, panel_height, instance_id);

        try {
            this.set_applet_tooltip(_("Stock Applet"));

            // Initialize settings
            this.settings = new Settings.AppletSettings(this, "stock-applet@cinnamon", instance_id);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "api-token", "apiToken", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "stock-symbol", "stockSymbol", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "update-interval", "updateInterval", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "show-current-price", "showCurrentPrice", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "show-daily-range", "showDailyRange", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "show-panel-chart", "showPanelChart", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "show-symbol-on-panel", "showSymbolOnPanel", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "chart-width", "chartWidth", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "chart-area-transparency", "chartAreaTransparency", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "chart-line-color", "chartLineColor", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "chart-area-color", "chartAreaColor", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "font-size", "fontSize", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "font-color", "fontColor", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "enable-font-shadow", "enableFontShadow", this.on_settings_changed, null);
            this.settings.bindProperty(Settings.BindingDirection.BIDIRECTIONAL,
                                     "font-shadow-color", "fontShadowColor", this.on_settings_changed, null);

            // Data storage for price history
            this.priceHistory = [];
            this.currentStockInfo = null; // Store current stock info for chart scaling
            this.dataFile = GLib.get_home_dir() + "/.local/share/cinnamon/applets/stock-applet@cinnamon/price_history.txt";

            // Initialize HTTP session
            this.httpSession = new Soup.Session();

            // Ensure data directory exists
            let dataDir = GLib.get_home_dir() + "/.local/share/cinnamon/applets/stock-applet@cinnamon";
            GLib.mkdir_with_parents(dataDir, 0o755);

            // Load existing price history
            this.loadPriceHistory();

            // Initialize display (no label needed)

            // Create panel chart
            if (this.showPanelChart) {
                this.panelChartActor = new St.DrawingArea({
                    width: this.chartWidth || 80,
                    height: panel_height - 4
                });
                this.panelChartActor.connect('repaint', Lang.bind(this, this.drawPanelChart));
                this.actor.add_child(this.panelChartActor);
            }

            // Setup context menu
            this.menuManager = new PopupMenu.PopupMenuManager(this);
            this.menu = new Applet.AppletPopupMenu(this, orientation);
            this.menuManager.addMenu(this.menu);

            this._contentSection = new PopupMenu.PopupMenuSection();
            this.menu.addMenuItem(this._contentSection);


            // Add preferences menu item
            let prefsItem = new PopupMenu.PopupMenuItem(_("Preferences"));
            prefsItem.connect('activate', Lang.bind(this, this.openPreferences));
            this.menu.addMenuItem(prefsItem);

            // Apply initial chart settings
            this.applyChartSettings();

            // Start monitoring
            this.updateStockInfo();
            this.setupTimer();

        } catch (e) {
            global.logError(e);
        }
    },

    setupTimer: function() {
        if (this.timeout) {
            Mainloop.source_remove(this.timeout);
        }
        // Convert minutes to seconds
        let intervalSeconds = (this.updateInterval || 10) * 60;
        this.timeout = Mainloop.timeout_add_seconds(intervalSeconds, Lang.bind(this, this.updateStockInfo));
    },

    applyChartSettings: function() {
        // Force repaint of panel display (chart or text) to apply new settings
        if (this.panelChartActor) {
            // Use a small delay to ensure the actor is ready after rebuild
            Mainloop.timeout_add(50, Lang.bind(this, function() {
                if (this.panelChartActor) {
                    this.panelChartActor.queue_repaint();
                }
                return false; // Don't repeat
            }));
        }
    },

    on_applet_clicked: function() {
        this.menu.toggle();
    },

    on_settings_changed: function() {
        // Debug logging to check settings values
        global.log("Stock Applet Settings Changed:");
        global.log("  chartAreaTransparency: " + this.chartAreaTransparency);
        global.log("  showCurrentPrice: " + this.showCurrentPrice);
        global.log("  chartLineColor: " + this.chartLineColor);
        global.log("  chartAreaColor: " + this.chartAreaColor);
        global.log("  fontSize: " + this.fontSize);
        global.log("  fontColor: " + this.fontColor);
        global.log("  enableFontShadow: " + this.enableFontShadow);
        global.log("  fontShadowColor: " + this.fontShadowColor);

        this.setupTimer();
        this.updateDisplay();
        this.rebuildMenu();
        this.rebuildPanelChart();
        this.applyChartSettings();

        // Force immediate repaint for panel display setting changes
        if (this.panelChartActor) {
            this.panelChartActor.queue_repaint();
        }
    },

    rebuildMenu: function() {
        this.menu.removeAll();

        this._contentSection = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._contentSection);


        let prefsItem = new PopupMenu.PopupMenuItem(_("Preferences"));
        prefsItem.connect('activate', Lang.bind(this, this.openPreferences));
        this.menu.addMenuItem(prefsItem);
    },

    rebuildPanelChart: function() {
        // Remove existing panel chart or text display
        if (this.panelChartActor) {
            this.actor.remove_child(this.panelChartActor);
            this.panelChartActor = null;
        }

        if (this.showPanelChart) {
            // Create new panel chart if enabled
            this.panelChartActor = new St.DrawingArea({
                width: Math.min(this.chartWidth || 80, 120), // Limit width for panel
                height: 24 // Fixed height for panel
            });
            this.panelChartActor.connect('repaint', Lang.bind(this, this.drawPanelChart));
            this.actor.add_child(this.panelChartActor);
        } else {
            // Create text display when chart is disabled
            this.panelChartActor = new St.DrawingArea({
                width: 80, // Fixed width for text
                height: 24 // Fixed height for panel
            });
            this.panelChartActor.connect('repaint', Lang.bind(this, this.drawPanelText));
            this.actor.add_child(this.panelChartActor);
        }
    },

    drawPanelChart: function(area) {
        let cr = area.get_context();
        let [width, height] = area.get_surface_size();

        // Clear background with chart area transparency setting
        let backgroundTransparency = this.chartAreaTransparency !== undefined ? this.chartAreaTransparency : 0.3;
        global.log("Stock Applet Panel Chart: chartAreaTransparency=" + this.chartAreaTransparency + ", using=" + backgroundTransparency);
        cr.setSourceRGBA(0.0, 0.0, 0.0, backgroundTransparency);
        cr.rectangle(0, 0, width, height);
        cr.fill();

        global.log("Stock Applet Panel Chart: priceHistory.length=" + (this.priceHistory ? this.priceHistory.length : 0));

        if (!this.priceHistory || this.priceHistory.length < 2) {
            // Draw simple indicator with chart line color
            let lineColor = this.parseColor(this.chartLineColor || "rgba(51, 204, 51, 1.0)");
            cr.setSourceRGBA(lineColor.r, lineColor.g, lineColor.b, 0.5);
            cr.rectangle(2, height/2 - 1, width - 4, 2);
            cr.fill();
            return;
        }

        // Calculate price range
        let prices = this.priceHistory.map(d => d.price);
        let minPrice = Math.min(...prices);
        let maxPrice = Math.max(...prices);
        let priceRange = maxPrice - minPrice;

        global.log("Stock Applet Panel Chart: minPrice=" + minPrice + ", maxPrice=" + maxPrice + ", range=" + priceRange);

        let margin = 2;
        let chartWidth = width - (margin * 2);
        let chartHeight = height - (margin * 2);

        // If all prices are the same, draw a horizontal line at middle
        if (priceRange === 0) {
            let lineColor = this.parseColor(this.chartLineColor || "rgba(51, 204, 51, 1.0)");
            cr.setSourceRGBA(lineColor.r, lineColor.g, lineColor.b, lineColor.a);
            cr.setLineWidth(2);
            cr.moveTo(margin, height / 2);
            cr.lineTo(width - margin, height / 2);
            cr.stroke();
        } else {
            // Draw fill area first with chart area color
            let areaColor = this.parseColor(this.chartAreaColor || "rgba(51, 204, 51, 0.3)");
            cr.setSourceRGBA(areaColor.r, areaColor.g, areaColor.b, areaColor.a);

            for (let i = 0; i < this.priceHistory.length; i++) {
                let x = margin + (i / (this.priceHistory.length - 1)) * chartWidth;
                let normalizedPrice = (this.priceHistory[i].price - minPrice) / priceRange;
                let y = margin + chartHeight - (normalizedPrice * chartHeight);

                if (i === 0) {
                    cr.moveTo(x, y);
                } else {
                    cr.lineTo(x, y);
                }
            }
            // Close the fill path
            cr.lineTo(width - margin, height - margin);
            cr.lineTo(margin, height - margin);
            cr.closePath();
            cr.fill();

            // Draw chart line on top with chart line color
            let lineColor = this.parseColor(this.chartLineColor || "rgba(51, 204, 51, 1.0)");
            cr.setSourceRGBA(lineColor.r, lineColor.g, lineColor.b, lineColor.a);
            cr.setLineWidth(2);

            for (let i = 0; i < this.priceHistory.length; i++) {
                let x = margin + (i / (this.priceHistory.length - 1)) * chartWidth;
                let normalizedPrice = (this.priceHistory[i].price - minPrice) / priceRange;
                let y = margin + chartHeight - (normalizedPrice * chartHeight);

                if (i === 0) {
                    cr.moveTo(x, y);
                } else {
                    cr.lineTo(x, y);
                }
            }
            cr.stroke();
        }

        // Draw current price text if enabled
        if (this.showCurrentPrice) {
            let currentPrice = this.priceHistory[this.priceHistory.length - 1].price;
            cr.selectFontFace("Sans", Cairo.FontSlant.NORMAL, Cairo.FontWeight.BOLD);
            cr.setFontSize(this.fontSize || 10);

            let priceText = currentPrice.toFixed(2);
            let priceX = 2
            try {
                let textExtents = cr.textExtents(priceText);
                priceX = width - textExtents.width - 2;
            } catch(err) {
            }
            let priceY = height - 2;
            this.drawTextWithShadow(cr, priceText, priceX, priceY);
        }

        // Draw stock symbol if enabled
        if (this.showSymbolOnPanel) {
            let symbol = this.stockSymbol || "NVDA";
            cr.selectFontFace("Sans", Cairo.FontSlant.NORMAL, Cairo.FontWeight.NORMAL);
            cr.setFontSize(this.fontSize || 10);
            let symbolX = 2;
            let symbolY = 10;
            this.drawTextWithShadow(cr, symbol, symbolX, symbolY);
        }
    },

    drawPanelText: function(area) {
        let cr = area.get_context();
        let [width, height] = area.get_surface_size();

        // Clear background with chart area transparency setting
        let backgroundTransparency = this.chartAreaTransparency !== undefined ? this.chartAreaTransparency : 0.3;
        cr.setSourceRGBA(0.0, 0.0, 0.0, backgroundTransparency);
        cr.rectangle(0, 0, width, height);
        cr.fill();

        // Get current price and symbol
        let symbol = this.stockSymbol || "NVDA";
        let price = "---";

        if (this.priceHistory && this.priceHistory.length > 0) {
            let currentPrice = this.priceHistory[this.priceHistory.length - 1].price;
            price = currentPrice.toFixed(2);
        }

        // Create display text
        let displayText = symbol + ": " + price;

        // Set font properties
        cr.selectFontFace("Sans", Cairo.FontSlant.NORMAL, Cairo.FontWeight.NORMAL);
        cr.setFontSize(this.fontSize || 10);

        // Calculate text position (centered)
        let textExtents = cr.textExtents(displayText);
        let textX = (width - textExtents.width) / 2;
        let textY = height / 2 + textExtents.height / 2;

        // Draw text with shadow
        this.drawTextWithShadow(cr, displayText, textX, textY);
    },

    openPreferences: function() {
        Util.spawn(['cinnamon-settings', 'applets', 'stock-applet@cinnamon']);
    },

    loadPriceHistory: function() {
        try {
            if (GLib.file_test(this.dataFile, GLib.FileTest.EXISTS)) {
                let [success, contents] = GLib.file_get_contents(this.dataFile);
                if (success) {
                    let lines = contents.toString().trim().split('\n');
                    this.priceHistory = [];
                    for (let line of lines) {
                        if (line.trim()) {
                            let parts = line.split(': ');
                            if (parts.length === 2) {
                                this.priceHistory.push({
                                    timestamp: parseInt(parts[0]),
                                    price: parseFloat(parts[1])
                                });
                            }
                        }
                    }
                }
            }
        } catch (e) {
            global.logError("Error loading price history: " + e);
            this.priceHistory = [];
        }
    },

    savePriceData: function(price) {
        try {
            let timestamp = Math.floor(Date.now() / 1000);
            let line = timestamp + ": " + price + "\n";

            // Add to memory
            this.priceHistory.push({
                timestamp: timestamp,
                price: price
            });

            // Keep only last 24 hours of data (assuming 10-minute intervals, that's 144 points)
            let maxPoints = 144;
            if (this.priceHistory.length > maxPoints) {
                this.priceHistory = this.priceHistory.slice(-maxPoints);
            }

            // Write to file
            let content = "";
            for (let data of this.priceHistory) {
                content += data.timestamp + ": " + data.price + "\n";
            }
            GLib.file_set_contents(this.dataFile, content);

        } catch (e) {
            global.logError("Error saving price data: " + e);
        }
    },

    getStockInfo: function() {
        try {
            if (!this.apiToken || this.apiToken.trim() === "") {
                return {
                    error: "no_token",
                    current: null,
                    high: null,
                    low: null
                };
            }

            let symbol = this.stockSymbol || "NVDA";
            let url = "https://finnhub.io/api/v1/quote?token=" + this.apiToken + "&symbol=" + symbol;

            try {
                // Use curl as a fallback for HTTP requests
                let command = ['curl', '-s', '-X', 'GET', url];
                let [success, stdout, stderr] = GLib.spawn_command_line_sync(command.join(' '));

                if (success && stdout) {
                    let responseText = stdout.toString();
                    if (responseText) {
                        try {
                            let data = JSON.parse(responseText);
                            if (data.c !== undefined) {
                                return {
                                    current: data.c,
                                    high: data.h,
                                    low: data.l,
                                    symbol: symbol
                                };
                            }
                        } catch (e) {
                            global.logError("Error parsing stock data: " + e);
                        }
                    }
                }
            } catch (e) {
                global.logError("HTTP request failed: " + e);
            }

            return {
                error: "fetch_failed",
                current: null,
                high: null,
                low: null
            };

        } catch (e) {
            global.logError("Error getting stock info: " + e);
            return {
                error: "error",
                current: null,
                high: null,
                low: null
            };
        }
    },

    updateStockInfo: function() {
        let info = this.getStockInfo();

        if (info.error === "no_token") {
            this.set_applet_tooltip("Please set your Finnhub API token in preferences");
        } else if (info.error) {
            this.set_applet_tooltip("Error fetching stock data");
        } else {
            // Save price data
            if (info.current !== null) {
                this.savePriceData(info.current);
            }
            this.updateDisplay(info);
        }

        return true; // Continue the timer
    },

    updateDisplay: function(info) {
        if (!info) {
            info = this.getStockInfo();
        }

        // Store current stock info for chart scaling
        this.currentStockInfo = info;

        if (info.error === "no_token") {
            this.set_applet_tooltip("Please set your Finnhub API token in preferences");
            return;
        }

        if (info.error) {
            this.set_applet_tooltip("Error fetching stock data");
            return;
        }

        let symbol = info.symbol || this.stockSymbol || "STOCK";

        // Update comprehensive tooltip
        this.updateTooltip(info, symbol);

        // Redraw panel display (chart or text) if visible
        if (this.panelChartActor) {
            this.panelChartActor.queue_repaint();
        }
    },

    parseColor: function(colorString) {
        // Parse rgba color string like "rgba(51, 204, 51, 1.0)"
        let match = colorString.match(/rgba?\(([^)]+)\)/);
        if (match) {
            let values = match[1].split(',').map(v => parseFloat(v.trim()));
            if (values.length >= 3) {
                return {
                    r: values[0] / 255,
                    g: values[1] / 255,
                    b: values[2] / 255,
                    a: values.length > 3 ? values[3] : 1.0
                };
            }
        }
        // Default green color
        return { r: 0.2, g: 0.8, b: 0.2, a: 1.0 };
    },

    drawTextWithShadow: function(cr, text, x, y) {
        // Draw shadow first if enabled
        if (this.enableFontShadow) {
            let shadowColor = this.parseColor(this.fontShadowColor || "rgba(0, 0, 0, 0.8)");
            cr.setSourceRGBA(shadowColor.r, shadowColor.g, shadowColor.b, shadowColor.a);
            cr.moveTo(x + 1, y + 1); // Offset shadow by 1 pixel right and down
            cr.showText(text);
        }

        // Draw main text
        let fontColor = this.parseColor(this.fontColor || "rgba(255, 255, 255, 1.0)");
        cr.setSourceRGBA(fontColor.r, fontColor.g, fontColor.b, fontColor.a);
        cr.moveTo(x, y);
        cr.showText(text);
    },

    updateTooltip: function(info, symbol) {
        let tooltipLines = [];

        // Current stock info (today's data)
        if (info && !info.error) {
            tooltipLines.push("Stock: " + symbol);
            if (info.current !== null) {
                tooltipLines.push("Current: $" + info.current.toFixed(2));
            }
            if (info.high !== null && info.low !== null) {
                tooltipLines.push("Today's Range: $" + info.low.toFixed(2) + " - $" + info.high.toFixed(2));
            }
        } else {
            tooltipLines.push("Stock: " + symbol);
            tooltipLines.push("No current data available");
        }

        // Historical data from chart (shown period)
        if (this.priceHistory && this.priceHistory.length >= 2) {
            let prices = this.priceHistory.map(d => d.price);
            let minPrice = Math.min(...prices);
            let maxPrice = Math.max(...prices);

            // Find timestamps for min and max prices
            let minTimestamp = null;
            let maxTimestamp = null;
            for (let data of this.priceHistory) {
                if (data.price === minPrice && minTimestamp === null) {
                    minTimestamp = data.timestamp;
                }
                if (data.price === maxPrice && maxTimestamp === null) {
                    maxTimestamp = data.timestamp;
                }
            }

            tooltipLines.push(""); // Empty line separator
            tooltipLines.push("Chart Period:");

            if (minTimestamp) {
                let minDate = new Date(minTimestamp * 1000);
                let minTime = minDate.toLocaleDateString("en-US", {
                    month: "short", day: "2-digit",
                    hour: "2-digit", minute: "2-digit", hour12: false
                });
                tooltipLines.push("Lowest: $" + minPrice.toFixed(2) + " (" + minTime + ")");
            }

            if (maxTimestamp) {
                let maxDate = new Date(maxTimestamp * 1000);
                let maxTime = maxDate.toLocaleDateString("en-US", {
                    month: "short", day: "2-digit",
                    hour: "2-digit", minute: "2-digit", hour12: false
                });
                tooltipLines.push("Highest: $" + maxPrice.toFixed(2) + " (" + maxTime + ")");
            }
        }

        let tooltipText = tooltipLines.join("\n");
        this.set_applet_tooltip(tooltipText);
    },


    on_applet_removed_from_panel: function() {
        if (this.timeout) {
            Mainloop.source_remove(this.timeout);
        }
    }
};

function main(metadata, orientation, panel_height, instance_id) {
    return new StockApplet(orientation, panel_height, instance_id);
}