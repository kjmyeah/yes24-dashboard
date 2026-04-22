@echo off
cd /d "%~dp0"
python insight_generator.py >> data\insight_log.txt 2>&1
