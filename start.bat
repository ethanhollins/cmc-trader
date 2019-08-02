@echo off
title CMCTrader
cd /d %~dp0
cmd /k "start /affinity 1 py Loader.py"