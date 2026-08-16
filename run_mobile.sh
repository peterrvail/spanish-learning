#!/bin/bash
# Launch Streamlit accessible from other devices on the same Wi-Fi network (e.g. iPhone).

cd "$(dirname "$0")"

IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)

if [ -z "$IP" ]; then
  echo "Could not detect local IP automatically."
  echo "Run 'ipconfig getifaddr en0' manually and open that address with :8501 on your iPhone."
  IP="<your-mac-ip>"
fi

echo "======================================"
echo " Spanish Learning System — Mobile Mode"
echo "======================================"
echo ""
echo "On your iPhone (same Wi-Fi network), open Safari and go to:"
echo ""
echo "   http://$IP:8501"
echo ""
echo "Keep this terminal window open while you use the app."
echo "Press Ctrl+C here to stop the server."
echo "======================================"
echo ""

streamlit run app/spanish_drill.py --server.address=0.0.0.0 --server.port=8501
