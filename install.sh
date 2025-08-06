#!/bin/bash

echo "🚀 Installing Advanced Music Bot..."

# Update system
echo "📦 Updating system packages..."
sudo apt-get update -y

# Install system dependencies
echo "🔧 Installing system dependencies..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    cmake \
    libcurl4-openssl-dev \
    libfftw3-dev \
    git \
    build-essential \
    pkg-config \
    sqlite3

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip3 install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p temp/bot temp/messenger temp/shazam logs

# Set permissions
chmod +x bot.py
chmod +x install.sh

# Install vibra for Shazam functionality
echo "🎵 Installing vibra for audio recognition..."
if ! command -v vibra &> /dev/null; then
    echo "Building vibra from source..."
    
    # Remove any existing vibra directory
    rm -rf vibra
    
    # Clone and build vibra
    if git clone https://github.com/bayernmuller/vibra.git; then
        cd vibra
        if mkdir -p build && cd build; then
            if cmake .. && make -j4; then
                if sudo make install; then
                    sudo ldconfig
                    echo "✅ vibra installed successfully"
                else
                    echo "⚠️ vibra installation failed, but bot will work without it"
                fi
            else
                echo "⚠️ vibra build failed, but bot will work without it"
            fi
        else
            echo "⚠️ vibra build setup failed, but bot will work without it"
        fi
        cd ../..
        rm -rf vibra
    else
        echo "⚠️ vibra download failed, but bot will work without it"
    fi
else
    echo "✅ vibra already installed"
fi

echo "🎉 Installation completed!"
echo ""
echo "📝 To run the bot:"
echo "   python3 run.py"
echo ""
echo "🔧 Configuration:"
echo "   - Edit TELEGRAM_TOKEN in bot.py"
echo "   - Edit MEGA_ADMIN_ID in bot.py"
echo ""
echo "📊 Features:"
echo "   ✅ Multi-language support (Uzbek, Russian, English)"
echo "   ✅ Audio recognition (Shazam-like)"
echo "   ✅ YouTube Music search and download"
echo "   ✅ Instagram, TikTok, YouTube downloader"
echo "   ✅ Admin panel with statistics"
echo "   ✅ User management (ban/unban)"
echo "   ✅ Mandatory channel subscription"
echo "   ✅ Broadcast messaging"
echo "   ✅ SQLite database"
echo "   ✅ Rate limiting"
echo "   ✅ Concurrent user support (200+ users)"
