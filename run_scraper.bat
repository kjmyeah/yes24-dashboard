@echo off
cd /d "%~dp0"
python scraper.py >> data\scraper_log.txt 2>&1
