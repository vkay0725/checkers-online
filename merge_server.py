import socket
import numpy as np
import threading
import gradio as gr
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import time
import queue

# === Game Constants ===
EMPTY = 0
BLACK = 1
WHITE = 2
BLACK_KING = 3
WHITE_KING = 4

# Global variables
clients = []
client_names = []
game_state = "waiting"  # "waiting", "playing", "over"
message_queues = {}  # For client communication
board = None
current_turn = BLACK  # Track whose turn it is
game_ender = None  # Track who ended the game

# === Game Logic ===
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
        lines = ["  0 1 2 3 4 5 6 7"]
        for i in range(8):
            line = f"{i} "
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
        return draw_board_gui(board), "Game not in active play state. Cannot make move.", get_player_status()
    
    try:
        sr, sc = notation_to_coords(start.strip())
        er, ec = notation_to_coords(end.strip())
        
        # Validate that the correct player is moving
        piece = board.get_piece(sr, sc)
        is_black_piece = piece in (BLACK, BLACK_KING)
        is_white_piece = piece in (WHITE, WHITE_KING)
        
        if (is_black_piece and board.current_player != BLACK) or \
           (is_white_piece and board.current_player != WHITE):
            return draw_board_gui(board), "<span style='color:red'>Not your turn!</span>", get_player_status()
        
        if not board.make_move((sr, sc), (er, ec)):
            return draw_board_gui(board), "<span style='color:red'>Invalid move.</span>", get_player_status()
        
        # Update board status
        board_str = board.board_to_string()
        move_msg = f"\nMove made: {start} to {end}\n{board_str}\n"
        
        if board.is_game_over():
            game_state = "over"
            winner = "BLACK" if board.get_winner() == BLACK else "WHITE"
            
            # Send different messages to each player
            black_msg = f"\nGame over! {'You win!' if winner == 'BLACK' else 'WHITE wins.'}\n{board_str}\n"
            white_msg = f"\nGame over! {'You win!' if winner == 'WHITE' else 'BLACK wins.'}\n{board_str}\n"
            broadcast_to_clients(black_msg, white_msg)
            
            return draw_board_gui(board), f"Game over! {winner} wins.", get_player_status()
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
            
            return draw_board_gui(board), f"Move made: {start} to {end}. {next_player}'s turn now.", get_player_status()
            
    except Exception as e:
        return draw_board_gui(board), f"<span style='color:red'>Error: {str(e)}</span>", get_player_status()

def restart_game():
    """Restart the game by creating a new board and updating all clients"""
    global board, game_state, game_ender
    
    if len(clients) < 2:
        return draw_board_gui(board), "Need 2 players to restart game", get_player_status()
    
    board = CheckersBoard()
    game_state = "playing"
    game_ender = None  # Reset game ender
    
    board_str = board.board_to_string()
    
    # Send different messages to each player
    black_msg = f"\nGame restarted!\n{board_str}\n\nYour turn, BLACK\n"
    white_msg = f"\nGame restarted!\n{board_str}\n\nBLACK's turn first\n"
    broadcast_to_clients(black_msg, white_msg)
    
    return draw_board_gui(board), "Game restarted! BLACK's turn first.", get_player_status()

def end_game(player=None):
    """End the current game and notify all clients"""
    global board, game_state, game_ender
    
    if game_state != "playing":
        return draw_board_gui(board), "No active game to end.", get_player_status()
    
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
    
    return draw_board_gui(board), f"Game ended by {game_ender}.", get_player_status()

def refresh_status():
    """Function to get updated game status and player information"""
    status = update_game_status()
    players = get_player_status()
    board_fig = draw_board_gui(board)
    return board_fig, status, players

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
                
                if data.lower() == "quit":
                    # Set who ended the game
                    if game_state == "playing":
                        game_state = "over"
                        game_ender = player_color
                    
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
                        
                        # Check for game over
                        if board.is_game_over():
                            game_state = "over"
                            winner = "BLACK" if board.get_winner() == BLACK else "WHITE"
                            
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

with gr.Blocks() as demo:
    gr.Markdown("### Checkers Game")
    
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
            
            gr.Markdown("### Rules")
            gr.Markdown("""
            - BLACK moves first
            - Regular checkers can only move diagonally forward
            - Kings can move diagonally in any direction
            - Captures are mandatory
            - Multiple captures in one turn are allowed
            """)
      # Fixed ad space block
            with gr.Column(scale=1):
                gr.Markdown("### Ad Space")
            # Use gr.Group instead of gr.Box
                ad_box = gr.Group()  # Changed from gr.Box() to gr.Group()
                with ad_box:
                    gr.HTML("""
                    <div style="width: 100%; height: 250px; border: 2px dashed #999; display: flex; align-items: center; justify-content: center; background-color: #f9f9f9;">
                        <span style="color: #aaa;">[ Ad Area ]</span>
                    </div>
                """)

    
    # Set up event handlers
    move_btn.click(fn=move_piece_gui, inputs=[start_input, end_input], outputs=[board_output, status_output, players_info])
    restart_btn.click(fn=restart_game, outputs=[board_output, status_output, players_info])
    
    # For the End Game button, we'll use the current player
    end_game_btn.click(
        fn=lambda: end_game(
            "BLACK" if board and board.current_player == BLACK else "WHITE"
        ), 
        outputs=[board_output, status_output, players_info]
    )
    
    # Set up refresh mechanism
    refresh_btn = gr.Button("Refresh", visible=False)
    refresh_btn.click(fn=refresh_status, outputs=[board_output, status_output, players_info])
    
    # Initialize the board
    demo.load(lambda: (draw_board_gui(CheckersBoard()), update_game_status(), get_player_status()), 
             outputs=[board_output, status_output, players_info])
    
    # Start server socket in background thread
    threading.Thread(target=socket_thread, daemon=True).start()
    
    # Start UI refresh thread
    threading.Thread(target=ui_refresh_thread, args=(refresh_btn,), daemon=True).start()

demo.launch(share=True)