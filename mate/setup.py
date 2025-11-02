#!/usr/bin/env python3

from distutils.core import setup

setup(
    name='stock-applet',
    version='1.0.0',
    description='Stock Chart Applet',
    author='Sergey Zhumatiy',
    author_email='sergzhum@gmail.com',
    scripts=['stock_applet.py'],
    data_files=[
        ('/usr/lib/mate-applets/', ['stock_applet.py']),
        ('/usr/share/mate-panel/applets/', ['org.mate.panel.StockApplet.mate-panel-applet']),
        ('/usr/share/applications/', ['stock-applet.desktop']),
    ],
)