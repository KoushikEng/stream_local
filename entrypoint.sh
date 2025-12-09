#!/bin/sh

# Default: Enable preprocessing (Assume powerful x86 or Apple Silicon)
ARGS="/media"

# Get Architecture and Kernel Info
ARCH=$(uname -m)
KERNEL=$(uname -r)

# Logic:
# 1. If we are on ARM (aarch64)...
# 2. AND we are NOT on Docker Desktop for Mac (which uses 'linuxkit' kernel)...
# 3. THEN we assume it's a slow SBC (Raspberry Pi, etc.) and disable preprocessing.

if [ "$ARCH" = "x86_64" ]; then
    apk add --no-cache ffmpeg
    echo "Detected x86_64 Architecture. Keeping preprocessing ON."
elif [ "$ARCH" = "aarch64" ]; then
    if echo "$KERNEL" | grep -q "linuxkit"; then
        apk add --no-cache ffmpeg
        echo "Detected Apple Silicon (Docker Desktop). Keeping preprocessing ON."
    else
        echo "Detected Low-Power ARM Device (likely Raspberry Pi). Disabling preprocessing."
        ARGS="/media --no-preprocessing"
    fi
fi

# Execute the application
exec python main.py $ARGS "$@"