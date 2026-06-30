@echo off
cd /d "%~dp0"
python main.py ^
  --map-file experiments/azhora_scenario4.cmap.json ^
  --turns 450 ^
  --seed azhora-sc4-001 ^
  --ai-narrative on ^
  --ai-narrative-rag ^
  --run-dir reports/runs/azhora_sc4_live
pause
