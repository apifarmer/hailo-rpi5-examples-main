#!/bin/bash

# Set up Hailo environment variables
export TAPPAS_WORKSPACE=/usr/lib/hailo-tappas
export GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/lib/hailo-tappas/lib

# Create and activate virtual environment if it doesn't exist
VENV_DIR="venv_hailo_rpi5_examples"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv $VENV_DIR
fi

# Activate virtual environment
source $VENV_DIR/bin/activate

# Install required packages
pip install -r requirements.txt

# Verify Hailo installation
if ! command -v hailortcli &> /dev/null; then
    echo "Error: Hailo Runtime CLI not found. Please install hailo-runtime package."
    exit 1
fi

# Verify GStreamer Hailo plugins
if ! gst-inspect-1.0 hailonet &> /dev/null; then
    echo "Error: Hailo GStreamer plugins not found. Please install gstreamer1.0-hailo package."
    exit 1
fi

# Download models if they don't exist
if [ ! -d "resources" ] || [ ! "$(ls -A resources/*.hef 2>/dev/null)" ]; then
    echo "Downloading model files..."
    chmod +x download_resources.sh
    ./download_resources.sh --all
fi

echo "Environment setup complete. You can now run the examples."
