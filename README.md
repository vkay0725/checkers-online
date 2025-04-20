# Checkers online

An online checkers game with DNS Adblocing functionality and SMTP mail summary feature, for Computer Networks spring 2025, IIT Dharwad

## Setup Guide

### Prerequisites
- Python 3+
- dnslib package
- requests package
- gradio package

### Installation and Setup

1. **Create and activate a Python virtual environment:**
   ```bash
   # Create virtual environment
   python3 -m venv venv
   
   # Activate virtual environment
   # On Linux/macOS:
   source venv/bin/activate
   # On Windows:
   # venv\Scripts\activate
   ```

2. **Install required packages:**
   ```bash
   pip install dnslib
   pip install requests
   pip install gradio
   ```

3. **Run the setup script:**
   ```bash
   ./setup.sh
   ```

4. **Follow the instructions displayed in the terminal.**

5. **Start the DNS adblocker with admin privileges:**
   ```bash
   sudo ./dns_adblocker.py --download --port 53
   ```

6. **Launch the application components on different terminals:**
   ```bash
   python3 server_combine.py
   python3 client_combine.py
   ```

## ⚠️ Important Note
Before launching the application, ensure that the server email credentials (email ID and app password) are included in the `email_handler.py` file within the 'EmailHandler' class.

Ensure the following files are located in the same directory as the other project files:
- `server_bridge.py`
- `email_handler.py`
