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
import random
from pathlib import Path
import requests
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Add email bridge import
import server_bridge

# Set up email credentials at startup
print("Setting up email functionality...")
server_bridge.setup_email_credentials()

from dnslib import DNSLabel, QTYPE, RR, dns
from dnslib.server import DNSServer, DNSHandler, BaseResolver, DNSLogger
from dnslib.dns import DNSRecord

import numpy as np
import gradio as gr
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import queue

# === Game Constants ===
EMPTY = 0
BLACK = 1
WHITE = 2
BLACK_KING = 3
WHITE_KING = 4

# === Ad Blocker Constants ===
UPSTREAM_DNS = "8.8.8.8"
BLOCKLIST_SOURCES = [
    "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
    "https://adaway.org/hosts.txt",
    "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=0&mimetype=plaintext",
    "https://winhelp2002.mvps.org/hosts.txt",
    "https://someonewhocares.org/hosts/hosts"
]

# Domains to check - mix of ad domains and common non-ad domains
AD_DOMAINS_TO_CHECK = [
    # Ad domains (likely to be blocked)
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "adservice.google.com",
    "ads.youtube.com",
    "ad.doubleclick.net",
    "tracking.example.com",
    "ads.example.com",
    "analytics.example.com",
    "metrics.example.com",
    
    # Non-ad domains (should not be blocked)
    "google.com",
    "youtube.com",
    "github.com",
    "wikipedia.org",
    "stackoverflow.com",
    "microsoft.com",
    "apple.com",
    "ubuntu.com",
    "python.org",
    "gradio.app"
]

# Global variables
clients = []
client_names = []
game_state = "waiting"  # "waiting", "playing", "over"
message_queues = {}  # For client communication
board = None
current_turn = BLACK  # Track whose turn it is
game_ender = None  # Track who ended the game
ad_blocker_status = "Ad blocker not initialized"
current_domain = random.choice(AD_DOMAINS_TO_CHECK)  # Track current displayed domain
current_domain_status = "Not checked yet"

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
                proxy_r = request.send(self.upstream_dns, 12553)
            else:
                proxy_r = request.send(self.upstream_dns, 12553, tcp=True)
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

class CheckersBoard:
    def __init__(self):
        self.board = np.zeros((8, 8), dtype=int)
        self.current_player = BLACK
        self.setup_board()

    def setup_board(self):
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 == 1:
                    if row < 3:
                        self.board[row][col] = WHITE
                    elif row > 4:
                        self.board[row][col] = BLACK

    def is_valid_position(self, row, col):
        return 0 <= row < 8 and 0 <= col < 8

    def get_piece(self, row, col):
        if not self.is_valid_position(row, col):
            return EMPTY
        return self.board[row][col]

    def is_player_piece(self, row, col):
        piece = self.get_piece(row, col)
        if self.current_player == BLACK:
            return piece in (BLACK, BLACK_KING)
        else:
            return piece in (WHITE, WHITE_KING)

    def is_opponent_piece(self, row, col):
        piece = self.get_piece(row, col)
        if self.current_player == BLACK:
            return piece in (WHITE, WHITE_KING)
        else:
            return piece in (BLACK, BLACK_KING)

    def is_king(self, row, col):
        piece = self.get_piece(row, col)
        return piece in (BLACK_KING, WHITE_KING)

    def make_king(self, row, col):
        piece = self.get_piece(row, col)
        if piece == BLACK and row == 0:
            self.board[row][col] = BLACK_KING
        elif piece == WHITE and row == 7:
            self.board[row][col] = WHITE_KING

    def get_move_directions(self, row, col):
        piece = self.get_piece(row, col)
        if piece in (BLACK_KING, WHITE_KING):
            return [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        elif piece == BLACK:
            return [(-1, -1), (-1, 1)]
        elif piece == WHITE:
            return [(1, -1), (1, 1)]
        return []

    def get_legal_moves(self):
        moves, jumps = [], []
        for row in range(8):
            for col in range(8):
                if self.is_player_piece(row, col):
                    jumps += self.get_jumps(row, col)
                    if not jumps:
                        moves += self.get_moves(row, col)
        return jumps if jumps else moves

    def get_moves(self, row, col):
        moves = []
        for dr, dc in self.get_move_directions(row, col):
            r, c = row + dr, col + dc
            if self.is_valid_position(r, c) and self.get_piece(r, c) == EMPTY:
                moves.append(((row, col), (r, c), []))
        return moves

    def get_jumps(self, row, col, captured=None):
        if captured is None:
            captured = []
        jumps = []
        for dr, dc in self.get_move_directions(row, col):
            jump_row, jump_col = row + 2 * dr, col + 2 * dc
            cap_row, cap_col = row + dr, col + dc
            if (self.is_valid_position(jump_row, jump_col) and
                    self.get_piece(jump_row, jump_col) == EMPTY and
                    self.is_opponent_piece(cap_row, cap_col) and
                    (cap_row, cap_col) not in captured):
                new_captured = captured + [(cap_row, cap_col)]
                jumps.append(((row, col), (jump_row, jump_col), new_captured))
                jumps.extend(self.get_jumps(jump_row, jump_col, new_captured))
        return jumps

    def make_move(self, from_pos, to_pos):
        legal_moves = self.get_legal_moves()
        for move in legal_moves:
            move_from, move_to, captured = move
            if move_from == from_pos and move_to == to_pos:
                fr, fc = move_from
                tr, tc = move_to
                self.board[fr][fc], self.board[tr][tc] = EMPTY, self.board[fr][fc]
                for cr, cc in captured:
                    self.board[cr][cc] = EMPTY
                self.make_king(tr, tc)
                self.current_player = WHITE if self.current_player == BLACK else BLACK
                return True
        return False

    def is_game_over(self):
        return not self.get_legal_moves()

    def get_winner(self):
        return WHITE if self.current_player == BLACK else BLACK

    def board_to_string(self):
        lines = ["  A B C D E F G H"]
        for i in range(8):
            line = f"{8-i} "
            for j in range(8):
                piece = self.board[i][j]
                line += {EMPTY: ".", BLACK: "b", WHITE: "w", BLACK_KING: "B", WHITE_KING: "W"}[piece] + " "
            lines.append(line)
        return "\n".join(lines)

    def coords_to_notation(self, row, col):
        return f"{chr(col + ord('A'))}{8 - row}"

# === Helper Functions ===
def notation_to_coords(notation):
    col = ord(notation[0].upper()) - ord('A')
    row = 8 - int(notation[1])
    return row, col

def broadcast_to_clients(message_black, message_white=None):
    """Send messages to connected clients, with customized messages per player"""
    if message_white is None:
        message_white = message_black  # If no specific white message, use the same for both
        
    # Send to BLACK player (if connected)
    if len(clients) > 0:
        try:
            clients[0].sendall(message_black.encode('utf-8'))
        except:
            pass
            
    # Send to WHITE player (if connected)
    if len(clients) > 1:
        try:
            clients[1].sendall(message_white.encode('utf-8'))
        except:
            pass

def update_game_status():
    """Update the game status based on current state"""
    global game_state, game_ender
    
    if len(clients) == 0:
        return "Waiting for players to connect..."
    elif len(clients) == 1:
        return "Waiting for second player..."
    elif game_state == "over":
        if game_ender:
            return f"Game ended by {game_ender}."
        else:
            winner = "BLACK" if board.get_winner() == BLACK else "WHITE"
            return f"Game over! {winner} wins."
    else:
        turn = "BLACK" if board.current_player == BLACK else "WHITE"
        return f"Game in progress. {turn}'s turn."

def get_player_status():
    """Return a formatted string of player connection status"""
    players = "BLACK: "
    players += "Connected" if len(clients) > 0 else "Waiting"
    players += "\nWHITE: "
    players += "Connected" if len(clients) > 1 else "Waiting"
    return players

def check_domain_status(domain):
    """Check if a domain is blocked by directly examining the blocklist"""
    global current_domain_status, ad_blocker
    
    try:
        # Check directly against the blocklist
        if domain.lower() in ad_blocker.blocklist:
            # Update stats when checking domain
            ad_blocker.total_count += 1
            ad_blocker.blocked_count += 1
            current_domain_status = "🔴 Blocked"
            return f"Domain: {domain}\nStatus: 🔴 Blocked"
        elif ad_blocker.allowlist and domain.lower() in ad_blocker.allowlist:
            # Update stats when checking domain
            ad_blocker.total_count += 1
            current_domain_status = "🟢 Allowed (Allowlisted)"
            return f"Domain: {domain}\nStatus: 🟢 Allowed (Allowlisted)"
        else:
            # Update stats when checking domain
            ad_blocker.total_count += 1
            current_domain_status = "🟢 Allowed"
            return f"Domain: {domain}\nStatus: 🟢 Allowed"
    except Exception as e:
        current_domain_status = "⚪ Unknown"
        return f"Domain: {domain}\nStatus: ⚪ Unknown (Error: {str(e)})"




def get_ad_blocker_status():
    """Return a formatted string of ad blocker status"""
    global current_domain, current_domain_status, ad_blocker
    
    status = "Ad Blocker Status\n\n"
    status += check_domain_status(current_domain)
    
    # Add stats
    try:
        if ad_blocker and hasattr(ad_blocker, 'get_stats'):
            stats = ad_blocker.get_stats()
            status += f"\n\n📊 Stats: {stats['blocked']} blocked / {stats['total']} total ({stats['percent_blocked']}%)"
            status += f"\n⏱ Uptime: {stats['uptime']}"
    except Exception as e:
        status += f"\n\n[Error getting stats: {str(e)}]"
    
    return status

def refresh_domain():
    """Select a new random domain to display"""
    global current_domain
    current_domain = random.choice(AD_DOMAINS_TO_CHECK)
    return get_ad_blocker_status()

# === GUI Code ===
def draw_board_gui(board_obj=None):
    if board_obj is None and board is not None:
        board_obj = board
    elif board_obj is None:
        # Create a new board if none exists
        board_obj = CheckersBoard()
    
    fig, ax = plt.subplots(figsize=(5, 5))
    for row in range(8):
        for col in range(8):
            color = "#f0d9b5" if (row + col) % 2 == 0 else "#b58863"
            ax.add_patch(patches.Rectangle((col, row), 1, 1, facecolor=color))

    for row in range(8):
        for col in range(8):
            piece = board_obj.board[row][col]
            if piece != EMPTY:
                clr = "#3B1F0B" if piece in (BLACK, BLACK_KING) else "#FFF5DC"
                ax.add_patch(plt.Circle((col + 0.5, row + 0.5), 0.35, color=clr, ec="black", linewidth=1.5))
                # Add a crown for kings
                if piece in (BLACK_KING, WHITE_KING):
                    ax.text(col + 0.5, row + 0.5, "♔", fontsize=16, 
                           ha='center', va='center', 
                           color="#B58863" if piece == BLACK_KING else "#3B1F0B")

    ax.set_xlim(0, 8)
    ax.set_ylim(0, 8)
    ax.set_xticks(range(8))
    ax.set_yticks(range(8))
    ax.set_xticklabels(['A','B','C','D','E','F','G','H'])
    ax.set_yticklabels(['8','7','6','5','4','3','2','1'])
    ax.tick_params(left=False, bottom=False)
    ax.set_aspect('equal')
    plt.gca().invert_yaxis()
    return fig

def move_piece_gui(start, end):
    global board, game_state
    
    if game_state != "playing":
        return draw_board_gui(board), "Game not in active play state. Cannot make move.", get_player_status(), get_ad_blocker_status()
    
    try:
        sr, sc = notation_to_coords(start.strip())
        er, ec = notation_to_coords(end.strip())
        
        # Validate that the correct player is moving
        piece = board.get_piece(sr, sc)
        is_black_piece = piece in (BLACK, BLACK_KING)
        is_white_piece = piece in (WHITE, WHITE_KING)
        
        if (is_black_piece and board.current_player != BLACK) or (is_white_piece and board.current_player != WHITE):
            return draw_board_gui(board), "<span style='color:red'>Not your turn!</span>", get_player_status(), get_ad_blocker_status()
        
        if not board.make_move((sr, sc), (er, ec)):
            return draw_board_gui(board), "<span style='color:red'>Invalid move.</span>", get_player_status(), get_ad_blocker_status()
        
        # Update board status
        board_str = board.board_to_string()
        move_msg = f"\nMove made: {start} to {end}\n{board_str}\n"
        # ADDED: Record move for email summary
        player_color = "BLACK" if board.current_player == WHITE else "WHITE"  # Player who just moved
        server_bridge.record_move(player_color, start, end, board_str)
        
        if board.is_game_over():
            game_state = "over"
            winner = "BLACK" if board.get_winner() == BLACK else "WHITE"
            
            # Send different messages to each player
            black_msg = f"\nGame over! {'You win!' if winner == 'BLACK' else 'WHITE wins.'}\n{board_str}\n"
            white_msg = f"\nGame over! {'You win!' if winner == 'WHITE' else 'BLACK wins.'}\n{board_str}\n"
            broadcast_to_clients(black_msg, white_msg)

            # ADDED: Generate and send game summary by email
            server_bridge.on_game_end("Game completed", winner)
            
            return draw_board_gui(board), f"Game over! {winner} wins.", get_player_status(), get_ad_blocker_status()
        else:
            next_player = "BLACK" if board.current_player == BLACK else "WHITE"
            
            # Send different messages to each player
            if next_player == "BLACK":
                black_msg = f"{move_msg}\nYour turn, BLACK\n"
                white_msg = f"{move_msg}\nBLACK is playing now\n"
            else:
                black_msg = f"{move_msg}\nWHITE is playing now\n"
                white_msg = f"{move_msg}\nYour turn, WHITE\n"
                
            broadcast_to_clients(black_msg, white_msg)
            
            
            return draw_board_gui(board), f"Move made: {start} to {end}. {next_player}'s turn now.", get_player_status(), get_ad_blocker_status()
            
    except Exception as e:
        return draw_board_gui(board), f"<span style='color:red'>Error: {str(e)}</span>", get_player_status(), get_ad_blocker_status()

def restart_game():
    """Restart the game by creating a new board and updating all clients"""
    global board, game_state, game_ender
    
    if len(clients) < 2:
        return draw_board_gui(board), "Need 2 players to restart game", get_player_status(), get_ad_blocker_status()
    
    board = CheckersBoard()
    game_state = "playing"
    game_ender = None  # Reset game ender

    # ADDED: Reset game history for email summary #noted
    server_bridge.on_game_start()
    
    board_str = board.board_to_string()
    
    # Send different messages to each player
    black_msg = f"\nGame restarted!\n{board_str}\n\nYour turn, BLACK\n"
    white_msg = f"\nGame restarted!\n{board_str}\n\nBLACK's turn first\n"
    broadcast_to_clients(black_msg, white_msg)
    
    return draw_board_gui(board), "Game restarted! BLACK's turn first.", get_player_status(), get_ad_blocker_status()

def end_game(player=None):
    """End the current game and notify all clients"""
    global board, game_state, game_ender
    
    if game_state != "playing":
        return draw_board_gui(board), "No active game to end.", get_player_status(), get_ad_blocker_status()
    
    game_state = "over"
    
    # Set who ended the game
    if player:
        game_ender = player
    else:
        current_player = "BLACK" if board.current_player == BLACK else "WHITE"
        game_ender = current_player
    
    # Send different messages to each player
    if game_ender == "BLACK":
        black_msg = "\nYou ended the game.\n"
        white_msg = "\nBLACK ended the game.\n"
    else:  # WHITE
        black_msg = "\nWHITE ended the game.\n"
        white_msg = "\nYou ended the game.\n"
        
    broadcast_to_clients(black_msg, white_msg)
    print("i am here to intitiate")
    # ADDED: Generate and send game summary by email
    server_bridge.on_game_end(f"Game ended by {game_ender}", None)
    print("i am initiating email send")
    
    return draw_board_gui(board), f"Game ended by {game_ender}.", get_player_status(), get_ad_blocker_status()

def refresh_status():
    """Function to get updated game status and player information"""
    status = update_game_status()
    players = get_player_status()
    ad_status = get_ad_blocker_status()
    board_fig = draw_board_gui(board)
    return board_fig, status, players, ad_status

# === Client Handler ===
def handle_client(client_socket, client_id):
    """Handle communication with a client"""
    global board, game_state, game_ender
    
    player_color = "BLACK" if client_id == 0 else "WHITE"
    try:
        client_socket.sendall(f"Connected as {player_color}\n".encode('utf-8'))
        
        # Send initial game state
        if board:
            client_socket.sendall(board.board_to_string().encode('utf-8'))
        else:
            client_socket.sendall("Waiting for another player...\n".encode('utf-8'))
        
        # Check if the game can start now
        if len(clients) == 2 and game_state == "waiting":
            game_state = "playing"
            board = CheckersBoard()

            
            # ADDED: Initialize game history for email summary
            server_bridge.on_game_start()
            
            # Send different messages to each player
            black_msg = f"\nGame started! Both players connected.\n{board.board_to_string()}\n\nYour turn, BLACK\n"
            white_msg = f"\nGame started! Both players connected.\n{board.board_to_string()}\n\nBLACK's turn first\n"
            broadcast_to_clients(black_msg, white_msg)
        
        # Main client communication loop
        while True:
            try:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break

                # ADDED: Handle email registration
                if data.startswith("EMAIL:"):
                    handled, response = server_bridge.handle_email_preference(data, player_color)
                    if handled:
                        print(f"Player {player_color} email preference: {response}")
                        continue
                
                if data.lower() == "quit":
                    # Set who ended the game
                    if game_state == "playing":
                        game_state = "over"
                        game_ender = player_color

                        # ADDED: Send game summary by email when player quits
                        server_bridge.on_game_end(f"Player {player_color} quit", None)
                    
                    opponent_msg = f"\nOpponent ({player_color}) quit. Game over.\n"
                    player_msg = f"\nYou've quit the game.\n"
                    
                    if client_id == 0:  # BLACK player quit
                        broadcast_to_clients(player_msg, opponent_msg)
                    else:  # WHITE player quit
                        broadcast_to_clients(opponent_msg, player_msg)
                        
                    break
                
                # Process moves from client
                if game_state == "playing" and " to " in data:
                    # Check if it's this player's turn
                    curr_player_color = "BLACK" if board.current_player == BLACK else "WHITE"
                    if curr_player_color != player_color:
                        client_socket.sendall("Not your turn!\n".encode('utf-8'))
                        continue
                    
                    # Parse the move
                    parts = data.split(" to ")
                    start, end = parts[0].strip(), parts[1].strip()
                    
                    try:
                        sr, sc = notation_to_coords(start)
                        er, ec = notation_to_coords(end)
                        
                        if not board.make_move((sr, sc), (er, ec)):
                            client_socket.sendall("Invalid move. Try again.\n".encode('utf-8'))
                            continue
                        
                        # Update GUI (this won't actually happen here, we'll update via queue)
                        board_str = board.board_to_string()
                        move_msg = f"\nMove made: {start} to {end}\n{board_str}\n"

                        # ADDED: Record move for email summary
                        server_bridge.record_move(player_color, start, end, board_str)
                        
                        # Check for game over
                        if board.is_game_over():
                            game_state = "over"
                            winner = "BLACK" if board.get_winner() == BLACK else "WHITE"

                            # ADDED: Send game summary by email
                            server_bridge.on_game_end("Game completed", winner)
                            
                            # Send different messages to each player
                            black_msg = f"\nGame over! {'You win!' if winner == 'BLACK' else 'WHITE wins.'}\n{board_str}\n"
                            white_msg = f"\nGame over! {'You win!' if winner == 'WHITE' else 'BLACK wins.'}\n{board_str}\n"
                            broadcast_to_clients(black_msg, white_msg)
                        else:
                            next_player = "BLACK" if board.current_player == BLACK else "WHITE"
                            
                            # Send different messages to each player
                            if next_player == "BLACK":
                                black_msg = f"{move_msg}\nYour turn, BLACK\n"
                                white_msg = f"{move_msg}\nBLACK is playing now\n"
                            else:
                                black_msg = f"{move_msg}\nWHITE is playing now\n"
                                white_msg = f"{move_msg}\nYour turn, WHITE\n"
                                
                            broadcast_to_clients(black_msg, white_msg)
                        
                    except Exception as e:
                        client_socket.sendall(f"Error processing move: {str(e)}\n".encode('utf-8'))
                
                # Handle end game command from client
                if data.lower() == "end game" and game_state == "playing":
                    end_game(player_color)

                    # ADDED: Send game summary by email
                    server_bridge.on_game_end(f"Game ended by {player_color}", None)
            
            except ConnectionResetError:
                print(f"Client {player_color} disconnected.")
                break
            except Exception as e:
                print(f"Error handling client {player_color}: {str(e)}")
                break
    
    finally:
        # Handle client disconnect
        if client_socket in clients:
            client_idx = clients.index(client_socket)
            clients.pop(client_idx)
            
            try:
                client_socket.close()
            except:
                pass
            
            if len(clients) < 2 and game_state == "playing":
                game_state = "waiting"
                broadcast_to_clients(f"\nPlayer {player_color} disconnected. Waiting for players...\n")

# === Server Socket Code ===
def socket_thread():
    """Thread to handle incoming socket connections"""
    global board, game_state
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(('127.0.0.1', 65244))
        server.listen(2)
        print("Server listening on 127.0.0.1:65244")
        
        while True:
            if len(clients) < 2:
                client, addr = server.accept()
                print(f"Connected to {addr}")
                
                # Add client to our list
                clients.append(client)
                client_id = len(clients) - 1
                
                # Start a thread to handle this client
                threading.Thread(target=handle_client, args=(client, client_id), daemon=True).start()
            else:
                # Wait before checking again
                time.sleep(1)
    
    except Exception as e:
        print(f"Server error: {str(e)}")
    finally:
        server.close()

# === UI Refresh Thread ===
def ui_refresh_thread(refresh_btn):
    """Thread to periodically trigger UI refresh"""
    while True:
        time.sleep(2)  # Refresh every 2 seconds
        try:
            # Use the refresh button's click method to trigger an update
            # This is a workaround since we can't directly update UI components from a thread
            refresh_btn.click()
        except:
            pass

# === Launch Everything ===
game_state = "waiting"
game_ender = None  # Initialize game_ender

# Initialize ad blocker
BLOCKLIST_FILE = "blocklist.txt"
ALLOWLIST_FILE = "allowlist.txt"

# Create empty blocklist if needed
if not os.path.exists(BLOCKLIST_FILE):
    with open(BLOCKLIST_FILE, 'w') as f:
        f.write("# Blocklist - Domains listed here will be blocked\n")
        f.write("# Add one domain per line\n")
        f.write("0.0.0.0 doubleclick.net\n")
        f.write("0.0.0.0 googleadservices.com\n")

# Create empty allowlist if needed
if not os.path.exists(ALLOWLIST_FILE):
    with open(ALLOWLIST_FILE, 'w') as f:
        f.write("# Allowlist - Domains listed here will never be blocked\n")
        f.write("# Add one domain per line\n")
        f.write("google.com\n")
        f.write("youtube.com\n")

# Initialize DNS resolver
ad_blocker = BlocklistResolver(UPSTREAM_DNS, BLOCKLIST_FILE, ALLOWLIST_FILE)

# Start DNS server in background
dns_server = DNSServer(ad_blocker, port=12553, address="127.0.0.1")
dns_thread = threading.Thread(target=dns_server.start, daemon=True)
dns_thread.start()

with gr.Blocks() as demo:
    gr.Markdown("### Checkers Game with Ad Blocker")
    
    with gr.Row():
        with gr.Column(scale=3):
            status_output = gr.Textbox(label="Game Status", interactive=False, value="Waiting for players...")
            board_output = gr.Plot(label="Checkers Board")
            
            with gr.Row():
                start_input = gr.Textbox(label="From (e.g., E2)")
                end_input = gr.Textbox(label="To (e.g., E4)")
            
            with gr.Row():
                move_btn = gr.Button("Make Move")
                restart_btn = gr.Button("Restart Game")
                end_game_btn = gr.Button("End Game")
        
        with gr.Column(scale=1):
            gr.Markdown("### Game Info")
            players_info = gr.Textbox(label="Connected Players", interactive=False, value="BLACK: Waiting\nWHITE: Waiting")
            
            gr.Markdown("### Ad Blocker Status")
            ad_blocker_info = gr.Textbox(label="Domain Status", interactive=False, value="Initializing...")
            domain_refresh_btn = gr.Button("Refresh Domain")
            
            gr.Markdown("### Rules")
            gr.Markdown("""
            - BLACK moves first
            - Regular checkers can only move diagonally forward
            - Kings can move diagonally in any direction
            - Captures are mandatory
            - Multiple captures in one turn are allowed
            """)
    
    # Set up event handlers
    move_btn.click(fn=move_piece_gui, inputs=[start_input, end_input], outputs=[board_output, status_output, players_info, ad_blocker_info])
    restart_btn.click(fn=restart_game, outputs=[board_output, status_output, players_info, ad_blocker_info])
    domain_refresh_btn.click(fn=refresh_domain, outputs=[ad_blocker_info])
    
    # For the End Game button, we'll use the current player
    end_game_btn.click(
        fn=lambda: end_game(
            "BLACK" if board and board.current_player == BLACK else "WHITE"
        ), 
        outputs=[board_output, status_output, players_info, ad_blocker_info]
    )
    
    # Set up refresh mechanism
    refresh_btn = gr.Button("Refresh", visible=False)
    refresh_btn.click(fn=refresh_status, outputs=[board_output, status_output, players_info, ad_blocker_info])
    
    # Initialize the board
    demo.load(lambda: (draw_board_gui(CheckersBoard()), update_game_status(), get_player_status(), get_ad_blocker_status()), 
             outputs=[board_output, status_output, players_info, ad_blocker_info])
    
    # Start server socket in background thread
    threading.Thread(target=socket_thread, daemon=True).start()
    
    # Start UI refresh thread
    threading.Thread(target=ui_refresh_thread, args=(refresh_btn,), daemon=True).start()

demo.launch(share=True)
