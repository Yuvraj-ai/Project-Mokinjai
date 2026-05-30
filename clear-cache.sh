#!/bin/bash
cd "$(dirname "$0")/frontend"
echo "==> Killing any running Vite dev servers..."
pkill -f "vite" 2>/dev/null || true
sleep 1

echo "==> Clearing Vite cache..."
rm -rf node_modules/.vite dist .vite

echo "==> Done!"
echo ""
echo "Now run:"
echo "  cd frontend && npm run dev"
echo ""
echo "Then hard-refresh your browser:"
echo "  Linux/Windows: Ctrl+Shift+R"
echo "  Mac: Cmd+Shift+R"
