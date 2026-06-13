@echo off
echo Building ORCAV executable...
uv run pyinstaller --noconsole --name ORCAV --add-data "orcav/gui/resources;orcav/gui/resources" -y run.py

echo Copying license files...
copy LICENSE dist\ORCAV\LICENSE > nul
copy THIRD-PARTY-LICENSES.md dist\ORCAV\THIRD-PARTY-LICENSES.md > nul

echo Build complete! The executable is located in the dist\ORCAV folder.
pause
