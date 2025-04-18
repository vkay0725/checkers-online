#!/usr/bin/env python3
import argparse
import datetime
import sys
import time
import threading
import traceback
import socket
import os
import re
from pathlib import Path
import requests

from dnslib import DNSLabel, QTYPE, RR, dns
from dnslib.server import DNSServer, DNSHandler, BaseResolver, DNSLogger
from dnslib.dns import DNSRecord

# Default upstream DNS server
UPSTREAM_DNS = "8.8.8.8"

# Blocklist sources
BLOCKLIST_SOURCES = [
    "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
    "https://adaway.org/hosts.txt",
    "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=0&mimetype=plaintext",
    "https://winhelp2002.mvps.org/hosts.txt",
    "https://someonewhocares.org/hosts/hosts"
]

class BlocklistResolver(BaseResolver):
    def __init__(self, upstream_dns, blocklist_path, allowlist_path=None):
        self.upstream_dns = upstream_dns
        self.blocklist_path = blocklist_path
        self.allowlist_path = allowlist_path
        self.blocklist = set()
        self.allowlist = set()
        self.load_blocklist()
        if allowlist_path:
            self.load_allowlist()
        self.blocked_count = 0
        self.total_count = 0
        self.start_time = time.time()

    def load_blocklist(self):
        """Load blocklist from file"""
        try:
            if not os.path.exists(self.blocklist_path):
                print(f"Blocklist file not found: {self.blocklist_path}")
                return
                
            with open(self.blocklist_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Skip comments and empty lines
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Handle hosts file format (IP domain)
                        parts = line.split()
                        if len(parts) >= 2:
                            domain = parts[1].lower()
                            # Skip localhost entries
                            if domain not in ('localhost', 'localhost.localdomain', 'local'):
                                self.blocklist.add(domain)
            print(f"Loaded {len(self.blocklist)} domains into blocklist")
        except Exception as e:
            print(f"Error loading blocklist: {e}")
    
    def load_allowlist(self):
        """Load allowlist from file"""
        try:
            if not os.path.exists(self.allowlist_path):
                print(f"Allowlist file not found: {self.allowlist_path}")
                return
                
            with open(self.allowlist_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.allowlist.add(line.lower())
            print(f"Loaded {len(self.allowlist)} domains into allowlist")
        except Exception as e:
            print(f"Error loading allowlist: {e}")
            
    def resolve(self, request, handler):
        """Resolve a DNS request, first checking against blocklist"""
        domain = str(request.q.qname)
        self.total_count += 1
        
        # Remove trailing dot from domain
        if domain.endswith('.'):
            domain = domain[:-1]
        
        domain = domain.lower()
            
        # Check if domain is in allowlist
        if self.allowlist and domain in self.allowlist:
            # Allow this domain even if it's in blocklist
            pass
        # Check if domain is in blocklist
        elif domain in self.blocklist:
            self.blocked_count += 1
            print(f"Blocked: {domain}")
            
            # Create a response with 0.0.0.0 for blocked domains
            reply = request.reply()
            reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=dns.A("0.0.0.0"), ttl=60))
            return reply
            
        # If not blocked, forward to upstream DNS
        try:
            if handler.protocol == 'udp':
                proxy_r = request.send(self.upstream_dns, 53)
            else:
                proxy_r = request.send(self.upstream_dns, 53, tcp=True)
            reply = DNSRecord.parse(proxy_r)
            return reply
        except Exception as e:
            print(f"Error forwarding: {e}")
            return request.reply()
    
    def get_stats(self):
        """Return current statistics"""
        uptime = time.time() - self.start_time
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return {
            "blocked": self.blocked_count,
            "total": self.total_count,
            "percent_blocked": round((self.blocked_count / max(1, self.total_count)) * 100, 2),
            "uptime": f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        }

def download_blocklists(sources, output_path):
    """Download and combine blocklists from multiple sources"""
    try:
        print(f"Downloading blocklists from {len(sources)} sources...")
        combined_domains = set()
        
        for url in sources:
            try:
                print(f"Downloading from {url}...")
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                # Process the downloaded list
                for line in response.text.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) >= 2 and re.match(r'^(\d{1,3}\.){3}\d{1,3}$', parts[0]):
                            domain = parts[1].lower()
                            # Skip localhost entries
                            if domain not in ('localhost', 'localhost.localdomain', 'local'):
                                combined_domains.add(domain)
            except Exception as e:
                print(f"Error downloading from {url}: {e}")
        
        # Write combined list to file
        with open(output_path, 'w') as f:
            f.write(f"# Combined blocklist - Updated {datetime.datetime.now()}\n")
            f.write(f"# Sources: {', '.join(sources)}\n")
            f.write(f"# Total domains: {len(combined_domains)}\n\n")
            
            for domain in sorted(combined_domains):
                f.write(f"0.0.0.0 {domain}\n")
                
        print(f"Blocklist downloaded with {len(combined_domains)} domains to {output_path}")
    except Exception as e:
        print(f"Error downloading blocklists: {e}")
        sys.exit(1)

def create_empty_allowlist(path):
    """Create an empty allowlist file with instructions"""
    if not os.path.exists(path):
        with open(path, 'w') as f:
            f.write("# Allowlist - Domains listed here will never be blocked\n")
            f.write("# Add one domain per line\n")
            f.write("# Example:\n")
            f.write("# google.com\n")
            f.write("# ads.example.com\n")
        print(f"Created empty allowlist at {path}")

def print_stats_periodically(resolver):
    """Print statistics every minute"""
    while True:
        time.sleep(60)
        stats = resolver.get_stats()
        print(f"Stats: {stats['blocked']} blocked out of {stats['total']} queries ({stats['percent_blocked']}%) - Uptime: {stats['uptime']}")

def main():
    parser = argparse.ArgumentParser(description='Simple DNS Ad Blocker')
    parser.add_argument('--port', default=12553, type=int, help='Port to listen on')
    parser.add_argument('--upstream', default=UPSTREAM_DNS, help='Upstream DNS server')
    parser.add_argument('--blocklist', default='blocklist.txt', help='Path to blocklist file')
    parser.add_argument('--allowlist', default='allowlist.txt', help='Path to allowlist file')
    parser.add_argument('--download', action='store_true', help='Download blocklists before starting')
    parser.add_argument('--bind', default='0.0.0.0', help='IP address to bind to')
    args = parser.parse_args()
    
    if args.download:
        download_blocklists(BLOCKLIST_SOURCES, args.blocklist)
    
    if not os.path.exists(args.blocklist):
        print(f"Blocklist file not found: {args.blocklist}")
        print("Use --download to download blocklists")
        sys.exit(1)
    
    # Create empty allowlist if it doesn't exist
    create_empty_allowlist(args.allowlist)
    
    resolver = BlocklistResolver(args.upstream, args.blocklist, args.allowlist)
    
    # Create DNS server
    udp_server = DNSServer(resolver, port=args.port, address=args.bind)
    tcp_server = DNSServer(resolver, port=args.port, address=args.bind, tcp=True)
    
    print(f"Starting DNS Ad Blocker on {args.bind}:{args.port}")
    print(f"Using upstream DNS: {args.upstream}")
    
    # Start servers in separate threads
    udp_server.start_thread()
    tcp_server.start_thread()
    
    # Start stats thread
    stats_thread = threading.Thread(target=print_stats_periodically, args=(resolver,), daemon=True)
    stats_thread.start()
    
    try:
        while udp_server.isAlive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down")
        udp_server.stop()
        tcp_server.stop()

if __name__ == '__main__':
    main()