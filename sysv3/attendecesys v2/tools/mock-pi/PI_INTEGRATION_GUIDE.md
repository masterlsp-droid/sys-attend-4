# Raspberry Pi Integration Guide

This guide explains how to take the `pi_server.py` script and run it on an actual Raspberry Pi. The script acts as an edge-processing node that handles face recognition and enrollment tasks locally on the Pi.

## 1. Prerequisites on the Raspberry Pi

Before running the server, you need to install the required dependencies. The `face_recognition` library requires some system-level C++ libraries to compile `dlib`.

Open a terminal on your Raspberry Pi and run the following commands:

```bash
# Update system packages
sudo apt-get update
sudo apt-get upgrade -y

# Install build tools and dlib dependencies
sudo apt-get install build-essential cmake -y
sudo apt-get install libopenblas-dev liblapack-dev -y
sudo apt-get install libx11-dev libgtk-3-dev -y

# Install Python 3 and pip (if not already installed)
sudo apt-get install python3 python3-pip -y
```

## 2. Install Python Packages

Once the system dependencies are ready, install the required Python libraries. This step might take some time because compiling `dlib` on a Raspberry Pi can take a while (sometimes 15-30 minutes).

```bash
pip3 install Flask flask-cors numpy Pillow
pip3 install dlib
pip3 install face_recognition
```

## 3. Running the Server

Transfer this folder (`mock-pi`) to your Raspberry Pi. You can do this via SCP, a USB drive, or by downloading the zip file directly on the Pi.

Navigate to the directory where `pi_server.py` is located and start the server:

```bash
cd path/to/mock-pi
python3 pi_server.py
```

You should see an output saying:
`Starting Pi Server on port 5000...`

## 4. Connecting the Main System to the Pi

By default, the script runs on `0.0.0.0:5000`, making it accessible on your local network.

1. **Find the Pi's IP Address**:
   On the Pi, run the command `hostname -I` to find its IP address (e.g., `192.168.1.100`).

2. **Configure the Main System**:
   In your main application (or frontend settings), you will need to point the "Pi IP Address" or API URL to the Pi's address. 
   Format: `http://<PI_IP_ADDRESS>:5000`
   
   Example: `http://192.168.1.100:5000`

## 5. Running on Boot (Optional but Recommended)

If you want the server to start automatically whenever the Raspberry Pi turns on, you can set it up as a systemd service or use `cron`.

**Using crontab:**
1. Run `crontab -e`
2. Add the following line at the bottom of the file (replace with your actual paths):
   ```
   @reboot /usr/bin/python3 /home/pi/mock-pi/pi_server.py > /home/pi/mock-pi/server.log 2>&1
   ```

## Note on Camera Integration
Currently, `pi_server.py` expects base64-encoded images to be sent to its `/api/recognize` and `/api/enroll` endpoints over HTTP. If you intend for the Pi to capture images directly via an attached Raspberry Pi Camera Module or USB Webcam, you will need to add a Python script to capture photos (e.g., using `picamera` or `opencv-python`) and pass those images directly into the `face_recognition` logic.
