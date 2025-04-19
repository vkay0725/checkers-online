
# 🕹️ Checkers-online  
An online Checkers game bundled with a DNS Adblocker and SMTP email summary feature.

---

## 📦 DNS Adblocker Setup Guide

### ✅ Prerequisites

Make sure you have the following installed:

- Python 3+
- [`dnslib`](https://pypi.org/project/dnslib/)
- [`requests`](https://pypi.org/project/requests/)
- [`gradio`](https://pypi.org/project/gradio/)

---

### 📥 Installation

Install the required Python packages:

```bash
pip install dnslib 
pip install requests
pip install gradio
```

---

### ⚙️ Installation and Setup

1. **Run the setup script:**

    ```bash
    ./setup.sh
    ```

2. **Follow the instructions** displayed in the terminal.

3. **Start the DNS adblocker with admin privileges:**

    ```bash
    sudo ./dns_adblocker.py --download --port 53
    ```

4. **Launch the application components in separate terminals:**

    ```bash
    python3 dns_adblocker.py
    python3 server_combine.py
    python3 client_combine.py
    ```

---

### ⚠️ Important Note

Ensure the following files are located in the same directory as the other project files:

- `server_bridge.py`
- `email_handler.py`

---

Let me know if you want me to add a game usage section, email summary details, or a section for contributors/license!



