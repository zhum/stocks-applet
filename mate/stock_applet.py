#!/usr/bin/python3

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('MatePanelApplet', '4.0')

from gi.repository import Gtk, MatePanelApplet, GLib, Gdk   # pyright: ignore[reportAttributeAccessIssue] # noqa: E402,E501
import cairo                                           # noqa
import json                                            # noqa
import os                                              # noqa
import re                                              # noqa
import time                                            # noqa
import urllib.request                                  # noqa
import urllib.error                                    # noqa
from collections import deque                          # noqa


class StockApplet:
    def __init__(self, applet):
        self.applet = applet
        self.config_file = os.path.expanduser("~/.config/stock-applet.json")

        # Load preferences
        self.preferences = {
            'show_current_price': True,
            'show_daily_range': True,
            'show_chart': False,
            'stock_symbol': 'NVDA',
            'api_token': '',
            'update_interval': 10,  # minutes
            'chart_width': 50,  # Width of each individual chart
            'chart_transparency': 50,  # Chart fill transparency (0-100)
            'chart_font_size': 10,  # Font size for chart labels
            'chart_line_color': (0.2, 0.8, 0.2),  # RGB for line color (green)
            'chart_fill_color': (0.2, 0.8, 0.2),  # RGB for fill color (green)
            'chart_text_color': (1.0, 1.0, 1.0),  # RGB for text color (white)
            'show_symbol_on_chart': True  # Show stock symbol on chart
        }
        self.load_preferences()

        # Data storage for charts (last 144 data points = 24 hours
        # at 10min intervals)
        self.max_data_points = 144
        self.price_data = deque(maxlen=self.max_data_points)
        self.timestamps = deque(maxlen=self.max_data_points)
        self.current_stock_info = None  # Store current stock info for
        #                                 chart scaling

        # Price history file
        self.data_file = os.path.expanduser(
            "~/.local/share/mate-applets/stock-applet/price_history.txt")
        self.ensure_data_directory()
        self.load_price_history()

        self.chart_window = None

        # Create container for switching between label and drawing area
        self.container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.container.set_homogeneous(False)
        # Make container expand to fill applet space
        self.container.set_vexpand(True)
        self.container.set_hexpand(False)
        self.container.set_hexpand(False)
        self.applet.add(self.container)

        # Initialize display widgets
        self.label = Gtk.Label()
        self.label.set_text("Stock: --")
        self.label.set_has_tooltip(True)
        self.label.set_valign(Gtk.Align.CENTER)  # Center vertically in panel
        self.label.set_halign(Gtk.Align.START)

        # Individual chart drawing areas
        self.chart_areas = {}
        self.create_chart_areas()

        # Add appropriate widget based on preferences
        self.update_panel_display()

        # Configure applet to fill panel space
        self.applet.set_vexpand(True)
        self.applet.set_hexpand(False)
        self.applet.set_halign(Gtk.Align.START)

        # Set MATE panel applet size flags to expand and fill
        try:
            # Request to expand and fill available space
            self.applet.set_flags(MatePanelApplet.AppletFlags.EXPAND_MAJOR |
                                  MatePanelApplet.AppletFlags.EXPAND_MINOR)
        except Exception:
            pass  # Fallback if MATE flags not available

        self.applet.show_all()

        # Connect to size allocation changes to update chart dimensions
        self.applet.connect('size-allocate', self.on_applet_size_allocate)

        # Setup context menu
        self.setup_menu()

        self.update_stock_info()
        # Update every 10 minutes by default (600 seconds)
        interval_minutes = self.preferences.get('update_interval', 10)
        self.timer_id = GLib.timeout_add_seconds(
            interval_minutes * 60, self.update_stock_info)

    def get_stock_data(self):
        """Get stock price data from Finnhub API"""
        data = {'current_price': 0.0, 'high': 0.0, 'low': 0.0, 'error': None}

        try:
            if not self.preferences['api_token'] or \
               self.preferences['api_token'].strip() == "":
                data['error'] = "no_token"
                return data

            symbol = self.preferences['stock_symbol'] or "NVDA"
            url = "https://finnhub.io/api/v1/quote?token=" + \
                  f"{self.preferences['api_token']}&symbol={symbol}"

            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    response_data = response.read().decode('utf-8')
                    stock_data = json.loads(response_data)
                    if 'c' in stock_data:
                        data['current_price'] = float(stock_data['c'])
                        data['high'] = float(stock_data.get('h', 0))
                        data['low'] = float(stock_data.get('l', 0))
                        return data
                    else:
                        data['error'] = "invalid_response"
            except (urllib.error.URLError, urllib.error.HTTPError):
                data['error'] = "fetch_failed"
            except (json.JSONDecodeError, ValueError, KeyError):
                data['error'] = "parse_error"

        except Exception as e:
            data['error'] = f"fetch_error: {str(e)}"

        return data

    def get_stock_display(self):
        """Get formatted stock price string"""
        data = self.get_stock_data()

        if data['error'] == "no_token":
            return "Stock: No Token"
        elif data['error']:
            return "Stock: Error"

        return self.format_display(current_price=data['current_price'],
                                   high=data['high'], low=data['low'])

    def format_display(self, current_price=None, high=None, low=None):
        """Format display string based on preferences"""
        parts = []
        symbol = self.preferences['stock_symbol'] or "STOCK"

        if current_price is not None and \
           self.preferences['show_current_price']:
            parts.append(f"${current_price:.2f}")

        if high is not None and low is not None and \
           self.preferences['show_daily_range']:
            parts.append(f"[{low:.2f}..{high:.2f}]")

        if not parts:
            return f"{symbol}: --"

        return " | ".join(parts) if len(parts) > 1 else parts[0]

    def update_stock_info(self):
        """Update stock information and refresh displays"""
        # Get raw data and store for charts
        data = self.get_stock_data()

        # Store current stock info for chart scaling
        self.current_stock_info = data

        # Save price data if we got valid data
        if not data.get('error') and data.get('current_price') is not None:
            self.save_price_data(data['current_price'])

        # Update chart window if open
        if self.chart_window and self.chart_window.get_visible():
            self.chart_drawing_area.queue_draw()

        # Update panel display based on mode
        if self.preferences['show_chart']:
            for area in self.chart_areas.values():
                area.queue_draw()
        else:
            if data.get('error') == "no_token":
                self.label.set_text("Stock: No Token")
            elif data.get('error'):
                self.label.set_text("Stock: Error")
            else:
                stock_info = self.format_display(
                    current_price=data.get('current_price'),
                    high=data.get('high'),
                    low=data.get('low'))
                symbol = self.preferences['stock_symbol'] or "STOCK"
                self.label.set_text(f"{symbol}: {stock_info}")
        # Update tooltip with comprehensive information
        self.update_tooltip()

        return True

    def update_tooltip(self):
        """Update tooltip with comprehensive price information"""
        tooltip_lines = []
        symbol = self.preferences['stock_symbol'] or "STOCK"

        # Current stock info (today's data)
        if (self.current_stock_info and
                not self.current_stock_info.get('error')):
            current_price = self.current_stock_info.get('current_price')
            daily_high = self.current_stock_info.get('high')
            daily_low = self.current_stock_info.get('low')

            tooltip_lines.append(f"Stock: {symbol}")
            if current_price is not None:
                tooltip_lines.append(f"Current: ${current_price:.2f}")

            if daily_high is not None and daily_low is not None:
                tooltip_lines.append(
                    f"Today's Range: ${daily_low:.2f} - ${daily_high:.2f}")
        else:
            tooltip_lines.append(f"Stock: {symbol}")
            tooltip_lines.append("No current data available")

        # Historical data from chart (shown period)
        if self.timestamps and self.price_data:
            # Get valid data points with timestamps
            valid_data = []
            for i, (timestamp, price) in enumerate(
                    zip(self.timestamps, self.price_data)):
                if timestamp is not None and price is not None:
                    valid_data.append((timestamp, price))

            if len(valid_data) >= 2:
                # Find min and max from shown data
                prices = [price for _, price in valid_data]
                min_price = min(prices)
                max_price = max(prices)

                # Find timestamps for min and max prices
                min_timestamp = None
                max_timestamp = None
                for timestamp, price in valid_data:
                    if price == min_price and min_timestamp is None:
                        min_timestamp = timestamp
                    if price == max_price and max_timestamp is None:
                        max_timestamp = timestamp

                tooltip_lines.append("")  # Empty line separator
                tooltip_lines.append("Chart Period:")

                if min_timestamp:
                    min_time = time.strftime(
                        "%b %d %H:%M",
                        time.localtime(min_timestamp))
                    tooltip_lines.append(
                        f"Lowest: ${min_price:.2f} ({min_time})")

                if max_timestamp:
                    max_time = time.strftime(
                        "%b %d %H:%M",
                        time.localtime(max_timestamp))
                    tooltip_lines.append(
                        f"Highest: ${max_price:.2f} ({max_time})")

        tooltip_text = "\n".join(tooltip_lines)
        self.label.set_tooltip_text(tooltip_text)

        # Also update chart area tooltips
        for chart_area in self.chart_areas.values():
            chart_area.set_tooltip_text(tooltip_text)

    def ensure_data_directory(self):
        """Ensure the data directory exists"""
        data_dir = os.path.dirname(self.data_file)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, mode=0o755, exist_ok=True)

    def load_price_history(self):
        """Load price history from file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    lines = f.read().strip().split('\n')
                    for line in lines:
                        if line.strip():
                            parts = line.split(': ')
                            if len(parts) == 2:
                                try:
                                    timestamp = float(parts[0])
                                    price = float(parts[1])
                                    self.timestamps.append(timestamp)
                                    self.price_data.append(price)
                                except ValueError:
                                    continue
        except Exception as e:
            print(f"Error loading price history: {e}")

    def save_price_data(self, price):
        """Save new price data to file"""
        try:
            timestamp = time.time()

            # Add to memory
            self.timestamps.append(timestamp)
            self.price_data.append(price)

            # Write all data to file
            with open(self.data_file, 'w') as f:
                for i in range(len(self.timestamps)):
                    f.write(f"{self.timestamps[i]}: {self.price_data[i]}\n")

        except Exception as e:
            print(f"Error saving price data: {e}")

    def load_preferences(self):
        """Load preferences from config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    saved_prefs = json.load(f)
                    self.preferences.update(saved_prefs)
        except Exception:
            pass  # Use defaults if loading fails

    def save_preferences(self):
        """Save preferences to config file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.preferences, f, indent=2)
        except Exception:
            pass  # Silently fail if saving fails

    def setup_menu(self):
        """Setup right-click context menu"""
        action_group = Gtk.ActionGroup("StockAppletActions")

        chart_action = Gtk.Action("Chart", "Show Charts",
                                  "Show Stock charts", None)
        chart_action.connect("activate", self.show_chart)
        action_group.add_action(chart_action)

        preferences_action = Gtk.Action("Preferences", "Preferences",
                                        "Configure Stock Applet", None)
        preferences_action.connect("activate", self.show_preferences)
        action_group.add_action(preferences_action)

        menu_xml = '''
        <menuitem name="Chart" action="Chart" />
        <separator/>
        <menuitem name="Preferences" action="Preferences" />
        '''

        self.applet.setup_menu(menu_xml, action_group)

    def show_preferences(self, action):
        """Show preferences dialog"""
        dialog = Gtk.Dialog("Stock Applet Preferences", None,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("OK", Gtk.ResponseType.OK)
        dialog.set_default_size(400, 300)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_border_width(10)

        # API Token
        token_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        token_label = Gtk.Label("API Token:")
        token_label.set_size_request(120, -1)
        token_box.pack_start(token_label, False, False, 0)
        self.token_entry = Gtk.Entry()
        self.token_entry.set_text(self.preferences.get('api_token', ''))
        self.token_entry.set_placeholder_text("Get free token at finnhub.io")
        token_box.pack_start(self.token_entry, True, True, 0)
        content.pack_start(token_box, False, False, 0)

        # Stock Symbol
        symbol_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        symbol_label = Gtk.Label("Stock Symbol:")
        symbol_label.set_size_request(120, -1)
        symbol_box.pack_start(symbol_label, False, False, 0)
        self.symbol_entry = Gtk.Entry()
        self.symbol_entry.set_text(
            self.preferences.get('stock_symbol', 'NVDA'))
        self.symbol_entry.set_placeholder_text("e.g., NVDA, AAPL, TSLA")
        symbol_box.pack_start(self.symbol_entry, True, True, 0)
        content.pack_start(symbol_box, False, False, 0)

        # Update Interval
        interval_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        interval_label = Gtk.Label("Update Interval:")
        interval_label.set_size_request(120, -1)
        interval_box.pack_start(interval_label, False, False, 0)
        self.interval_spin = Gtk.SpinButton()
        self.interval_spin.set_range(1, 60)
        self.interval_spin.set_increments(1, 5)
        self.interval_spin.set_value(
            self.preferences.get('update_interval', 10))
        interval_box.pack_start(self.interval_spin, False, False, 0)
        interval_minutes_label = Gtk.Label("minutes")
        interval_box.pack_start(interval_minutes_label, False, False, 0)
        content.pack_start(interval_box, False, False, 0)

        # Display options
        self.current_price_check = Gtk.CheckButton("Show Current Price")
        self.current_price_check.set_active(
            self.preferences['show_current_price'])
        content.pack_start(self.current_price_check, False, False, 0)

        self.daily_range_check = Gtk.CheckButton("Show Daily Range")
        self.daily_range_check.set_active(
            self.preferences['show_daily_range'])
        content.pack_start(self.daily_range_check, False, False, 0)

        # Add separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        content.pack_start(separator, False, False, 5)

        chart_text = "Show Charts in Panel (instead of text)"
        self.chart_view_check = Gtk.CheckButton(chart_text)
        self.chart_view_check.set_active(self.preferences['show_chart'])
        content.pack_start(self.chart_view_check, False, False, 0)

        # Chart width control
        width_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                            spacing=10)
        width_label = Gtk.Label("Chart Width:")
        width_box.pack_start(width_label, False, False, 0)

        self.chart_width_spin = Gtk.SpinButton()
        self.chart_width_spin.set_range(30, 100)
        self.chart_width_spin.set_increments(5, 10)
        self.chart_width_spin.set_value(self.preferences['chart_width'])
        width_box.pack_start(self.chart_width_spin, False, False, 0)

        content.pack_start(width_box, False, False, 0)

        # Chart transparency control
        transparency_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                   spacing=10)
        transparency_label = Gtk.Label("Chart Transparency (%):")
        transparency_box.pack_start(transparency_label, False, False, 0)

        self.chart_transparency_spin = Gtk.SpinButton()
        self.chart_transparency_spin.set_range(0, 100)
        self.chart_transparency_spin.set_increments(5, 10)
        self.chart_transparency_spin.set_value(
            self.preferences['chart_transparency'])
        transparency_box.pack_start(
            self.chart_transparency_spin, False, False, 0)

        content.pack_start(transparency_box, False, False, 0)

        # Chart font size control
        font_size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                spacing=10)
        font_size_label = Gtk.Label("Chart Font Size:")
        font_size_box.pack_start(font_size_label, False, False, 0)

        self.chart_font_size_spin = Gtk.SpinButton()
        self.chart_font_size_spin.set_range(6, 16)
        self.chart_font_size_spin.set_increments(1, 2)
        self.chart_font_size_spin.set_value(
            self.preferences['chart_font_size'])
        font_size_box.pack_start(
            self.chart_font_size_spin, False, False, 0)

        content.pack_start(font_size_box, False, False, 0)

        # Chart line color control
        line_color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                 spacing=10)
        line_color_label = Gtk.Label("Chart Line Color:")
        line_color_box.pack_start(line_color_label, False, False, 0)

        self.chart_line_color_button = Gtk.ColorButton()
        line_color = self.preferences['chart_line_color']
        rgba = Gdk.RGBA()
        rgba.red = line_color[0]
        rgba.green = line_color[1]
        rgba.blue = line_color[2]
        rgba.alpha = 1.0
        self.chart_line_color_button.set_rgba(rgba)
        line_color_box.pack_start(
            self.chart_line_color_button, False, False, 0)

        content.pack_start(line_color_box, False, False, 0)

        # Chart fill color control
        fill_color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                 spacing=10)
        fill_color_label = Gtk.Label("Chart Fill Color:")
        fill_color_box.pack_start(fill_color_label, False, False, 0)

        self.chart_fill_color_button = Gtk.ColorButton()
        fill_color = self.preferences['chart_fill_color']
        rgba = Gdk.RGBA()
        rgba.red = fill_color[0]
        rgba.green = fill_color[1]
        rgba.blue = fill_color[2]
        rgba.alpha = 1.0
        self.chart_fill_color_button.set_rgba(rgba)
        fill_color_box.pack_start(
            self.chart_fill_color_button, False, False, 0)

        content.pack_start(fill_color_box, False, False, 0)

        # Chart text color control
        text_color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                 spacing=10)
        text_color_label = Gtk.Label("Chart Text Color:")
        text_color_box.pack_start(text_color_label, False, False, 0)

        self.chart_text_color_button = Gtk.ColorButton()
        text_color = self.preferences['chart_text_color']
        rgba = Gdk.RGBA()
        rgba.red = text_color[0]
        rgba.green = text_color[1]
        rgba.blue = text_color[2]
        rgba.alpha = 1.0
        self.chart_text_color_button.set_rgba(rgba)
        text_color_box.pack_start(
            self.chart_text_color_button, False, False, 0)

        content.pack_start(text_color_box, False, False, 0)

        # Show symbol on chart checkbox
        self.show_symbol_check = Gtk.CheckButton("Show stock symbol on chart")
        self.show_symbol_check.set_active(
            self.preferences['show_symbol_on_chart'])
        content.pack_start(self.show_symbol_check, False, False, 0)

        dialog.show_all()

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            # Save preferences
            old_chart_mode = self.preferences['show_chart']
            old_chart_width = self.preferences['chart_width']
            old_transparency = self.preferences['chart_transparency']
            old_font_size = self.preferences['chart_font_size']
            old_interval = self.preferences['update_interval']

            # Save new values
            self.preferences['api_token'] = self.token_entry.get_text().strip()
            self.preferences['stock_symbol'] = \
                self.symbol_entry.get_text().strip().upper()
            self.preferences['update_interval'] = \
                int(self.interval_spin.get_value())
            self.preferences['show_current_price'] = \
                self.current_price_check.get_active()
            self.preferences['show_daily_range'] = \
                self.daily_range_check.get_active()
            # self.preferences['show_chart'] =
            #   self.chart_view_check.get_active()
            self.preferences['chart_width'] = \
                int(self.chart_width_spin.get_value())
            self.preferences['chart_transparency'] = \
                int(self.chart_transparency_spin.get_value())
            self.preferences['chart_font_size'] = \
                int(self.chart_font_size_spin.get_value())

            # Save color preferences
            line_rgba = self.chart_line_color_button.get_rgba()
            self.preferences['chart_line_color'] = (
                line_rgba.red, line_rgba.green, line_rgba.blue)

            fill_rgba = self.chart_fill_color_button.get_rgba()
            self.preferences['chart_fill_color'] = (
                fill_rgba.red, fill_rgba.green, fill_rgba.blue)

            text_rgba = self.chart_text_color_button.get_rgba()
            self.preferences['chart_text_color'] = (
                text_rgba.red, text_rgba.green, text_rgba.blue)

            self.preferences['show_symbol_on_chart'] = \
                self.show_symbol_check.get_active()

            self.save_preferences()

            # Restart timer if interval changed
            if old_interval != self.preferences['update_interval']:
                self.restart_timer()

            # Switch display mode if chart preference changed
            if old_chart_mode != self.preferences['show_chart']:
                self.update_panel_display()
            # Update chart size if width changed
            elif (old_chart_width != self.preferences['chart_width'] or
                  old_transparency != self.preferences['chart_transparency'] or
                  old_font_size != self.preferences['chart_font_size']):
                if self.preferences['show_chart']:
                    for area in self.chart_areas.values():
                        area.queue_draw()

            # Update display immediately
            self.update_stock_info()

        dialog.destroy()

    def restart_timer(self):
        """Restart the update timer with new interval"""
        if hasattr(self, 'timer_id') and self.timer_id:
            GLib.source_remove(self.timer_id)
        interval_minutes = self.preferences.get('update_interval', 10)
        self.timer_id = GLib.timeout_add_seconds(
            interval_minutes * 60, self.update_stock_info)

    def show_chart(self, action):
        """Show chart window"""
        if self.chart_window:
            self.chart_window.present()
            return

        self.chart_window = Gtk.Window()
        self.chart_window.set_title("Stock Chart")
        self.chart_window.set_default_size(600, 400)
        self.chart_window.set_position(Gtk.WindowPosition.CENTER)

        # Create drawing area
        self.chart_drawing_area = Gtk.DrawingArea()
        self.chart_drawing_area.connect('draw', self.on_chart_draw)

        self.chart_window.add(self.chart_drawing_area)
        self.chart_window.connect('delete-event', self.on_chart_window_delete)
        self.chart_window.show_all()

    def on_chart_window_delete(self, window, event):
        """Handle chart window close"""
        window.hide()
        return True  # Don't destroy, just hide

    def on_chart_draw(self, widget, cr):
        """Draw the charts"""
        allocation = widget.get_allocation()
        width = allocation.width
        height = allocation.height

        # Clear background
        cr.set_source_rgb(0.1, 0.1, 0.1)
        cr.paint()

        if not self.timestamps or len(self.timestamps) < 2:
            # No data yet
            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face("Arial", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(16)
            text = "Collecting data..."
            text_extents = cr.text_extents(text)
            cr.move_to((width - text_extents.width) / 2, height / 2)
            cr.show_text(text)
            return

        # Chart area margins
        margin_left = 60
        margin_right = 20
        margin_top = 20
        margin_bottom = 40

        chart_width = width - margin_left - margin_right
        chart_height = height - margin_top - margin_bottom

        # Draw enabled charts
        charts_to_draw = []
        if self.preferences['show_current_price'] and len(self.price_data) > 0:
            # Calculate dynamic min/max combining historical data
            # and daily high/low
            prices = [p for p in self.price_data if p is not None]
            if prices:
                min_price = min(prices)
                max_price = max(prices)

                # Include daily high/low from current stock info if available
                if (self.current_stock_info and
                        not self.current_stock_info.get('error')):
                    if self.current_stock_info.get('low') is not None:
                        min_price = min(
                            min_price, self.current_stock_info['low'])
                    if self.current_stock_info.get('high') is not None:
                        max_price = max(
                            max_price, self.current_stock_info['high'])

                # Add some padding (5%) to avoid touching chart edges
                price_range = max_price - min_price
                if price_range == 0:
                    price_range = max_price * 0.01
                    # 1% range if prices are identical
                padding = price_range * 0.05
                min_price -= padding
                max_price += padding

                line_color = self.preferences['chart_line_color']
                charts_to_draw.append(('Stock Price ($)', self.price_data,
                                       line_color, max_price, min_price))

        if not charts_to_draw:
            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face("Arial", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(16)
            text = "No charts enabled"
            text_extents = cr.text_extents(text)
            cr.move_to((width - text_extents.width) / 2, height / 2)
            cr.show_text(text)
            return

        # Draw grid
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.set_line_width(1)

        # Vertical grid lines
        for i in range(0, 11):
            x = margin_left + (chart_width * i / 10)
            cr.move_to(x, margin_top)
            cr.line_to(x, margin_top + chart_height)
            cr.stroke()

        # Horizontal grid lines
        for i in range(0, 6):
            y = margin_top + (chart_height * i / 5)
            cr.move_to(margin_left, y)
            cr.line_to(margin_left + chart_width, y)
            cr.stroke()

        # Draw Y-axis labels
        text_color = self.preferences['chart_text_color']
        cr.set_source_rgb(*text_color)
        cr.select_font_face("Arial", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)

        # Draw Y-axis labels with actual price values
        if charts_to_draw:
            # Use the first chart's min/max values for scale
            _, _, _, max_val, min_val = charts_to_draw[0]
            price_range = max_val - min_val

            # Handle case where price range is very small
            if price_range < 0.01:
                price_range = max_val * 0.01
                # Use 1% of max price as minimum range

            for i in range(0, 6):
                # Calculate actual price value for this grid line
                price_value = max_val - (price_range * i / 5)
                y = margin_top + (chart_height * i / 5)
                cr.move_to(5, y + 4)
                cr.show_text(f"${price_value:.2f}")

        # Draw charts
        for name, data, line_color, max_val, min_val in charts_to_draw:
            if not any(d is not None for d in data):
                continue

            valid_points = [(i, val) for i, val in enumerate(data)
                            if val is not None]
            if len(valid_points) < 2:
                continue

            # Calculate transparency alpha value (0-1)
            alpha = self.preferences['chart_transparency'] / 100.0

            # Handle case where all values are the same
            # (avoid division by zero)
            if max_val == min_val:
                # If all prices are the same,
                # draw a horizontal line in the middle
                max_val = min_val + (min_val * 0.01 if min_val > 0 else 0.01)

            # Draw filled area
            fill_color = self.preferences['chart_fill_color']
            cr.set_source_rgba(*fill_color, alpha)
            first_point = True
            for i, value in valid_points:
                x = margin_left + (chart_width * i / (len(data) - 1))
                # Normalize value between min_val and max_val
                normalized_value = (value - min_val) / (max_val - min_val)
                y = margin_top + chart_height - \
                    (chart_height * normalized_value)

                if first_point:
                    cr.move_to(x, y)
                    first_point = False
                else:
                    cr.line_to(x, y)

            # Close the path by drawing to bottom corners
            if valid_points:
                last_x = margin_left + (
                    chart_width * (len(data) - 1) / (len(data) - 1))
                first_x = margin_left
                cr.line_to(last_x, margin_top + chart_height)
                cr.line_to(first_x, margin_top + chart_height)
                cr.close_path()
                cr.fill()

            # Draw line border
            cr.set_source_rgb(*line_color)
            cr.set_line_width(2)
            first_point = True
            for i, value in valid_points:
                x = margin_left + (chart_width * i / (len(data) - 1))
                # Use same normalization for price charts
                prices = [v for v in data if v is not None]
                if prices:
                    min_val = min(prices)
                    max_val = max(prices)
                    if max_val > min_val:
                        normalized = (value - min_val) / \
                            (max_val - min_val)
                    else:
                        normalized = 0.5
                    y = margin_top + chart_height - (chart_height * normalized)
                else:
                    y = margin_top + chart_height / 2

                if first_point:
                    cr.move_to(x, y)
                    first_point = False
                else:
                    cr.line_to(x, y)

            cr.stroke()

        # Draw legend
        legend_y = margin_top + 10
        for i, (name, data, line_color, max_val, min_val) in \
                enumerate(charts_to_draw):
            cr.set_source_rgb(*line_color)
            cr.rectangle(margin_left + 10, legend_y + i * 20, 15, 3)
            cr.fill()

            text_color = self.preferences['chart_text_color']
            cr.set_source_rgb(*text_color)
            cr.move_to(margin_left + 30, legend_y + i * 20 + 10)
            cr.show_text(name)

        # Draw stock symbol if enabled
        if self.preferences['show_symbol_on_chart']:
            symbol = self.preferences['stock_symbol'] or "STOCK"
            text_color = self.preferences['chart_text_color']
            cr.set_source_rgb(*text_color)
            cr.select_font_face("Arial", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(self.preferences['chart_font_size'] + 2)
            text_extents = cr.text_extents(symbol)
            # Position on second line, right side
            cr.move_to(width - text_extents.width - 10,
                       margin_top + 30 + text_extents.height)
            cr.show_text(symbol)

    def create_chart_areas(self):
        """Create individual drawing areas for each chart type"""
        # Get panel height from applet allocation, with fallback
        # try:
        #     applet_allocation = self.applet.get_allocation()
        #     container_allocation = self.container.get_allocation()

        #     # Use the larger of applet or container height
        #     available_height = max(
        #         applet_allocation.height,
        #         container_allocation.height)

        #     # Use almost full height, leaving minimal margin (1px each side)
        #     chart_height = max(16, available_height - 2)
        # except Exception:
        #     chart_height = 24  # Fallback to original hardcoded value

        chart_width = self.preferences['chart_width']

        # Stock Price chart
        self.chart_areas['price'] = Gtk.DrawingArea()
        # Set only width, let height expand naturally
        self.chart_areas['price'].set_size_request(chart_width, -1)
        self.chart_areas['price'].set_has_tooltip(True)
        # Make chart area expand to fill available space
        self.chart_areas['price'].set_vexpand(True)
        self.chart_areas['price'].set_hexpand(True)
        self.chart_areas['price'].set_valign(Gtk.Align.FILL)
        self.chart_areas['price'].set_halign(Gtk.Align.FILL)
        self.chart_areas['price'].connect(
            'draw', lambda w, cr:
            self.draw_individual_chart(w, cr, 'price'))

    def update_chart_dimensions(self):
        """Update chart dimensions based on current panel size"""
        if not hasattr(self, 'chart_areas') or not self.chart_areas:
            return

        # # Get panel height from applet allocation, with fallback
        # try:
        #     applet_allocation = self.applet.get_allocation()
        #     container_allocation = self.container.get_allocation()
        #
        #     # Use the larger of applet or container height
        #     available_height = max(
        #         applet_allocation.height,
        #         container_allocation.height)
        #
        #     # Use almost full height, leaving minimal margin (1px each side)
        #     chart_height = max(16, available_height - 2)
        # except Exception:
        #     chart_height = 24  # Fallback

        chart_width = self.preferences['chart_width']

        # Update size requests for all chart areas
        # (only width, let height expand)
        for chart_area in self.chart_areas.values():
            chart_area.set_size_request(chart_width, -1)

    def draw_individual_chart(self, widget, cr, chart_type):
        """Draw individual chart for specific metric"""
        allocation = widget.get_allocation()
        width = allocation.width
        height = allocation.height

        # Chart configuration
        config = {
            'price': {'data': self.price_data,
                      'color': self.preferences['chart_line_color'],
                      'label': 'price',
                      'enabled': self.preferences['show_current_price']}
        }

        chart_config = config[chart_type]

        # Clear background
        cr.set_source_rgb(0.1, 0.1, 0.1)
        cr.paint()

        # Draw border
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, width - 1, height - 1)
        cr.stroke()

        if not self.timestamps or len(self.timestamps) < 2:
            # No data yet - show loading
            cr.set_source_rgb(0.6, 0.6, 0.6)
            cr.select_font_face("Arial", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(10)
            text = chart_config['label']
            text_extents = cr.text_extents(text)
            cr.move_to((width - text_extents.width) / 2, height / 2 + 2)
            cr.show_text(text)
            return

        data = chart_config['data']
        color = chart_config['color']

        if not any(d is not None for d in data):
            # No valid data
            cr.set_source_rgb(0.5, 0.5, 0.5)
            cr.select_font_face("Arial", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(10)
            text = "N/A"
            text_extents = cr.text_extents(text)
            cr.move_to((width - text_extents.width) / 2, height / 2 + 2)
            cr.show_text(text)
            return

        # Draw chart
        margin = 2
        chart_width = width - (margin * 2)
        chart_height = height - (margin * 2)

        valid_points = [(i, val) for i, val in enumerate(data)
                        if val is not None]
        if len(valid_points) >= 2:
            # Calculate transparency alpha value (0-1)
            alpha = self.preferences['chart_transparency'] / 100.0

            # Draw filled area
            fill_color = self.preferences['chart_fill_color']
            cr.set_source_rgba(*fill_color, alpha)
            first_point = True
            for i, value in valid_points:
                x = margin + (chart_width * i / (len(data) - 1))
                y = margin + chart_height - (chart_height * value / 100)

                if first_point:
                    cr.move_to(x, y)
                    first_point = False
                else:
                    cr.line_to(x, y)

            # Close the path by drawing to bottom corners
            if valid_points:
                last_x = margin + (
                    chart_width * (len(data) - 1) / (len(data) - 1))
                first_x = margin
                cr.line_to(last_x, margin + chart_height)
                cr.line_to(first_x, margin + chart_height)
                cr.close_path()
                cr.fill()

            # Draw line border
            cr.set_source_rgb(*color)
            cr.set_line_width(1.5)
            first_point = True
            for i, value in valid_points:
                x = margin + (chart_width * i / (len(data) - 1))
                if chart_type == 'price':
                    # Use dynamic scaling for price charts
                    prices = [v for v in data if v is not None]
                    if prices:
                        min_val = min(prices)
                        max_val = max(prices)
                        if max_val > min_val:
                            normalized = (value - min_val) / \
                                (max_val - min_val)
                        else:
                            normalized = 0.5
                        y = margin + chart_height - (chart_height * normalized)
                    else:
                        y = margin + chart_height / 2
                else:
                    # Use percentage scaling for other chart types
                    y = margin + chart_height - (chart_height * value / 100)

                if first_point:
                    cr.move_to(x, y)
                    first_point = False
                else:
                    cr.line_to(x, y)

            cr.stroke()

        # Draw current value in top-left corner
        # Draw current value in top-left corner
        current_value = data[-1] if data[-1] is not None else 0
        text_color = self.preferences['chart_text_color']
        cr.set_source_rgb(*text_color)
        cr.select_font_face("Arial", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(self.preferences['chart_font_size'])

        # Create label with prefix
        if chart_type == 'price':
            prefix = ""
            # Format price value properly
            if current_value > 0:
                text = f"{prefix}{current_value:.1f}"
            else:
                text = f"{prefix}--"
        else:
            prefix = "?"  # Default fallback
            text = f"{prefix}:{int(current_value)}%"

        cr.move_to(3, self.preferences['chart_font_size'] + 2)
        cr.show_text(text)

        # Draw stock symbol on second line if enabled
        if (self.preferences['show_symbol_on_chart'] and
                chart_type == 'price'):
            symbol = self.preferences['stock_symbol'] or "STOCK"
            text_color = self.preferences['chart_text_color']
            cr.set_source_rgb(*text_color)
            cr.set_font_size(self.preferences['chart_font_size'] - 1)
            cr.move_to(3, (self.preferences['chart_font_size'] + 2) * 2)
            cr.show_text(symbol)

    def update_panel_display(self):
        """Update the panel display based on preferences"""
        if self.preferences['show_chart']:
            # Remove label if present
            if self.label.get_parent():
                self.container.remove(self.label)
            # Add chart areas
            for area in self.chart_areas.values():
                if area.get_parent() is None:
                    self.container.add(area)
        else:
            # Remove chart areas if present
            for area in self.chart_areas.values():
                if area.get_parent() is not None:
                    self.container.remove(area)
            # Add label if not present
            if self.label.get_parent() is None:
                self.container.add(self.label)

        self.container.show_all()

    def on_applet_size_allocate(self, allocation):
        """Handle size allocation changes"""
        self.update_chart_dimensions()

    def applet_factory(self, iid, data):
        if iid != "StockApplet":
            return False

        StockApplet(self)
        return True


def applet_factory(applet, iid, data):
    if iid != "StockApplet":
        return False

    StockApplet(applet)
    return True


def main():
    import sys
    import signal

    # Handle SIGINT and SIGTERM gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)

    try:
        MatePanelApplet.Applet.factory_main("StockAppletFactory", True,
                                            MatePanelApplet.Applet.__gtype__,
                                            applet_factory, None)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
