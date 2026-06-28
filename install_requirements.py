#!/usr/bin/env python3
"""
Installation script for Audio Looper dependencies
Detects platform and installs appropriate packages
"""

import sys
import subprocess
import platform
import os

def run_command(cmd, description):
    """Run command and handle errors"""
    print(f"Running: {description}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ {description} - Success")
            return True
        else:
            print(f"✗ {description} - Failed")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ {description} - Exception: {e}")
        return False

def detect_platform():
    """Detect current platform"""
    if sys.platform == 'win32':
        return 'windows'
    elif sys.platform == 'darwin':
        return 'mac'
    elif sys.platform.startswith('linux'):
        # Check if Raspberry Pi
        try:
            with open('/proc/cpuinfo', 'r') as f:
                if 'raspberry pi' in f.read().lower():
                    return 'raspberry_pi'
        except:
            pass
        return 'linux'
    else:
        return 'unknown'

def install_python_packages():
    """Install required Python packages"""
    packages = ['pygame', 'pymodbus']
    
    for package in packages:
        cmd = f"{sys.executable} -m pip install {package}"
        if not run_command(cmd, f"Installing {package}"):
            return False
    return True

def install_raspberry_pi_packages():
    """Install Raspberry Pi specific packages"""
    # System packages
    system_packages = [
        'sudo apt-get update',
        'sudo apt-get install -y python3-pygame'
    ]
    
    for cmd in system_packages:
        if not run_command(cmd, f"System install: {cmd.split()[-1]}"):
            print("Warning: System package installation failed")
    return True

def install_windows_packages():
    """Install Windows specific packages"""
    # On Windows, pygame should work with pip
    return install_python_packages()

def setup_audio_directory():
    """Create audio files directory"""
    audio_dir = "audio_files"
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)
        print(f"✓ Created {audio_dir} directory")
        
        # Create placeholder files
        for i in range(1, 9):
            placeholder_file = os.path.join(audio_dir, f"{i}.wav")
            if not os.path.exists(placeholder_file):
                with open(placeholder_file + ".txt", 'w') as f:
                    f.write(f"Place your audio file {i}.wav here\n")
        
        print("✓ Created placeholder files (replace with your .wav files)")
    else:
        print(f"✓ {audio_dir} directory already exists")

def main():
    """Main installation function"""
    current_platform = detect_platform()
    
    print("=" * 50)
    print("AUDIO LOOPER SYSTEM - DEPENDENCY INSTALLER")
    print("=" * 50)
    print(f"Detected platform: {current_platform}")
    print()
    
    success = True
    
    # Install base Python packages
    if not install_python_packages():
        success = False
    
    # Platform-specific installations
    if current_platform == 'raspberry_pi':
        print("\nInstalling Raspberry Pi specific packages...")
        if not install_raspberry_pi_packages():
            success = False
    elif current_platform == 'windows':
        print("\nInstalling Windows specific packages...")
        if not install_windows_packages():
            success = False
    
    # Setup directories
    setup_audio_directory()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ Installation completed successfully!")
        print("\nNext steps:")
        print("1. Place your audio files (1.wav - 8.wav) in the audio_files/ directory")
        print("2. Configure modbus_panel in config.json for the external DIN IO module")
        print("3. Run: python main.py")
    else:
        print("✗ Installation completed with errors")
        print("Some packages may need manual installation")
    
    print("=" * 50)

if __name__ == "__main__":
    main()