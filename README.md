# checkers-online
online checkers game with dns adblocker and smtp email summary

DNS Adblocker Setup Guide
Prerequisites
Make sure you have the following installed:

Python 3+

dnslib

requests

gradio

Installation
Install the required Python packages:

bash
Copy
Edit
pip install dnslib 
pip install requests
pip install gradio
Installation and Setup
Run the setup script:

bash
Copy
Edit
./setup.sh
Follow the instructions displayed in the terminal.

Start the DNS adblocker with admin privileges:

bash
Copy
Edit
sudo ./dns_adblocker.py --download --port 53
Launch the application components in separate terminals:

bash
Copy
Edit
python3 dns_adblocker.py
python3 server_combine.py
python3 client_combine.py
Important Note
Make sure the following files are in the same directory as the other project files:

server_bridge.py

email_handler.py




