#!/bin/bash

# Install script for MATE Stock Applet

echo "Installing MATE Stock Applet..."

# Make applet executable
chmod +x stock_applet.py

# Copy files to system directories
sudo cp stock_applet.py /usr/lib/mate-applets/
sudo cp org.mate.panel.StockApplet.mate-panel-applet /usr/share/mate-panel/applets/
sudo cp stock-applet.desktop /usr/share/applications/
sudo cp org.mate.panel.applet.StockAppletFactory.service /usr/share/dbus-1/services/

# Set proper permissions
sudo chmod +x /usr/lib/mate-applets/stock_applet.py

echo "Installation complete!"
echo "Restart MATE panel: mate-panel --replace &"
echo "You can now add the Stock Applet to your MATE panel by:"
echo "1. Right-clicking on the panel"
echo "2. Selecting 'Add to Panel...'"
echo "3. Finding 'Stock Applet' in the list"
echo ""
echo "To configure the applet:"
echo "- Set your Finnhub API token (get one free at https://finnhub.io)"
echo "- Choose your stock symbol (e.g., NVDA, AAPL, TSLA)"
echo "- Configure update interval and display preferences"
