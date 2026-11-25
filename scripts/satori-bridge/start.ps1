$ErrorActionPreference = "Stop"
$BridgeRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
python (Join-Path $BridgeRoot "bridge.py") --serve --host 127.0.0.1 --port 8788
