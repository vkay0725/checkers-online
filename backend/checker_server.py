import socket
import numpy as np

# Constants for pieces
EMPTY = 0
BLACK = 1  # Player 1
WHITE = 2  # Player 2
BLACK_KING = 3
WHITE_KING = 4

class CheckersBoard:
    def __init__(self):
        # Initialize 8x8 board
        self.board = np.zeros((8, 8), dtype=int)
        self.current_player = BLACK  # Black (Player 1) starts
        self.setup_board()
        
    def setup_board(self):
        # Set up the initial board
        for row in range(8):
            for col in range(8):
                # Only use black squares
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
            return piece == BLACK or piece == BLACK_KING
        else:
            return piece == WHITE or piece == WHITE_KING
    
    def is_opponent_piece(self, row, col):
        piece = self.get_piece(row, col)
        if self.current_player == BLACK:
            return piece == WHITE or piece == WHITE_KING
        else:
            return piece == BLACK or piece == BLACK_KING
    
    def is_king(self, row, col):
        piece = self.get_piece(row, col)
        return piece == BLACK_KING or piece == WHITE_KING
    
    def make_king(self, row, col):
        piece = self.get_piece(row, col)
        if piece == BLACK and row == 0:
            self.board[row][col] = BLACK_KING
        elif piece == WHITE and row == 7:
            self.board[row][col] = WHITE_KING
    
    def get_move_directions(self, row, col):
        piece = self.get_piece(row, col)
        
        if piece == BLACK_KING or piece == WHITE_KING:
            return [(-1, -1), (-1, 1), (1, -1), (1, 1)]  # Kings can move in all diagonal directions
        elif piece == BLACK:
            return [(-1, -1), (-1, 1)]  # Black moves up
        elif piece == WHITE:
            return [(1, -1), (1, 1)]  # White moves down
        return []
    
    def get_legal_moves(self):
        moves = []
        jumps = []
        
        # Check all board positions
        for row in range(8):
            for col in range(8):
                if self.is_player_piece(row, col):
                    # Check for jumps
                    piece_jumps = self.get_jumps(row, col)
                    if piece_jumps:
                        jumps.extend(piece_jumps)
                    
                    # Check for regular moves if no jumps
                    if not jumps:
                        piece_moves = self.get_moves(row, col)
                        if piece_moves:
                            moves.extend(piece_moves)
        
        # If jumps are available, they are mandatory
        if jumps:
            return jumps
        return moves
    
    def get_moves(self, row, col):
        moves = []
        for dr, dc in self.get_move_directions(row, col):
            new_row, new_col = row + dr, col + dc
            if self.is_valid_position(new_row, new_col) and self.get_piece(new_row, new_col) == EMPTY:
                moves.append(((row, col), (new_row, new_col), []))
        return moves
    
    def get_jumps(self, row, col, captured=None):
        if captured is None:
            captured = []
        
        jumps = []
        for dr, dc in self.get_move_directions(row, col):
            jump_row, jump_col = row + 2*dr, col + 2*dc
            capture_row, capture_col = row + dr, col + dc
            
            if (self.is_valid_position(jump_row, jump_col) and 
                self.get_piece(jump_row, jump_col) == EMPTY and 
                self.is_opponent_piece(capture_row, capture_col) and
                (capture_row, capture_col) not in captured):
                
                new_captured = captured + [(capture_row, capture_col)]
                jumps.append(((row, col), (jump_row, jump_col), new_captured))
                
                # Check for multiple jumps
                next_jumps = self.get_multi_jumps(jump_row, jump_col, new_captured)
                jumps.extend(next_jumps)
                
        return jumps
    
    def get_multi_jumps(self, row, col, captured):
        multi_jumps = []
        piece = self.get_piece(row, col)
        
        # Temporarily set the piece at the new position to check for more jumps
        temp = self.board[row][col]
        self.board[row][col] = self.current_player if not self.is_king(row, col) else (BLACK_KING if self.current_player == BLACK else WHITE_KING)
        
        # Get more jumps from this position
        next_jumps = self.get_jumps(row, col, captured)
        
        # If there are more jumps, format them correctly
        for _, (next_row, next_col), next_captured in next_jumps:
            if len(next_captured) > len(captured):
                multi_jumps.append(((row, col), (next_row, next_col), next_captured))
        
        # Restore the board
        self.board[row][col] = temp
        
        return multi_jumps
    
    def make_move(self, from_pos, to_pos):
        from_row, from_col = from_pos
        to_row, to_col = to_pos
        
        # Find the move in legal moves
        legal_moves = self.get_legal_moves()
        selected_move = None
        
        for move in legal_moves:
            move_from, move_to, captured = move
            if move_from == from_pos and move_to == to_pos:
                selected_move = move
                break
        
        if not selected_move:
            return False
        
        # Execute the move
        piece = self.get_piece(from_row, from_col)
        self.board[from_row][from_col] = EMPTY
        self.board[to_row][to_col] = piece
        
        # Remove captured pieces
        _, _, captured = selected_move
        for cap_row, cap_col in captured:
            self.board[cap_row][cap_col] = EMPTY
        
        # Check for king promotion
        self.make_king(to_row, to_col)
        
        # Switch player
        self.current_player = WHITE if self.current_player == BLACK else BLACK
        
        return True
    
    def parse_move(self, move_str):
        try:
            # Format expected: "from_row,from_col-to_row,to_col"
            parts = move_str.split("-")
            from_part = parts[0].split(",")
            to_part = parts[1].split(",")
            
            from_pos = (int(from_part[0]), int(from_part[1]))
            to_pos = (int(to_part[0]), int(to_part[1]))
            
            return from_pos, to_pos
        except:
            return None
    
    def is_game_over(self):
        # Game is over if current player has no legal moves
        return len(self.get_legal_moves()) == 0
    
    def get_winner(self):
        # If the current player has no legal moves, the opponent wins
        if self.is_game_over():
            return WHITE if self.current_player == BLACK else BLACK
        return None
    
    def board_to_string(self):
        result = "  0 1 2 3 4 5 6 7\n"
        for i in range(8):
            result += f"{i} "
            for j in range(8):
                piece = self.board[i][j]
                if piece == EMPTY:
                    result += ". "
                elif piece == BLACK:
                    result += "b "
                elif piece == WHITE:
                    result += "w "
                elif piece == BLACK_KING:
                    result += "B "
                elif piece == WHITE_KING:
                    result += "W "
            result += "\n"
        return result

def is_valid_move(board, move_str):
    move_tuple = board.parse_move(move_str)
    if not move_tuple:
        return False
    
    from_pos, to_pos = move_tuple
    legal_moves = board.get_legal_moves()
    
    for move in legal_moves:
        move_from, move_to, _ = move
        if move_from == from_pos and move_to == to_pos:
            return True
    
    return False

def start_server(host='127.0.0.1', port=65244):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(2)
    print(f"Server listening on {host}:{port}")
    
    clients = []
    for i in range(2):
        client_socket, client_address = server_socket.accept()
        print(f"Connected to {client_address}")
        clients.append((client_socket, client_address))
    
    s1, addr1 = clients[0]  # Black player (Player 1)
    s2, addr2 = clients[1]  # White player (Player 2)
    
    # Send initial player assignments
    s1.sendall(b"You are playing as BLACK (b)")
    s2.sendall(b"You are playing as WHITE (w)")
    
    board = CheckersBoard()
    
    # Send initial board state to both players
    board_str = board.board_to_string()
    s1.sendall(f"\nInitial board:\n{board_str}".encode('utf-8'))
    s2.sendall(f"\nInitial board:\n{board_str}".encode('utf-8'))
    
    game_over = False
    
    while not game_over:
        try:
            # Get current player's socket
            current_socket = s1 if board.current_player == BLACK else s2
            waiting_socket = s2 if board.current_player == BLACK else s1
            
            # Tell players whose turn it is
            player_name = "BLACK" if board.current_player == BLACK else "WHITE"
            current_socket.sendall(f"\nYour turn ({player_name}).\nEnter move (row,col-row,col): ".encode('utf-8'))
            waiting_socket.sendall(f"\nWaiting for {player_name} to move...".encode('utf-8'))
            
            # Get move from current player
            valid_move = False
            while not valid_move:
                move_str = current_socket.recv(1024).decode('utf-8').strip()
                
                if not move_str or move_str.lower() == "quit":
                    print(f"Player {player_name} quit. Ending game.")
                    waiting_socket.sendall(b"Opponent quit. Game over.")
                    game_over = True
                    break
                
                if is_valid_move(board, move_str):
                    from_pos, to_pos = board.parse_move(move_str)
                    board.make_move(from_pos, to_pos)
                    valid_move = True
                    print(f"Player {player_name} move: {move_str}")
                else:
                    current_socket.sendall(b"Invalid move. Try again: ")
            
            if game_over:
                break
            
            # Send updated board to both players
            board_str = board.board_to_string()
            s1.sendall(f"\nBoard after move:\n{board_str}".encode('utf-8'))
            s2.sendall(f"\nBoard after move:\n{board_str}".encode('utf-8'))
            
            # Check if game is over
            if board.is_game_over():
                winner = "BLACK" if board.get_winner() == BLACK else "WHITE"
                s1.sendall(f"\nGame over! {winner} wins!".encode('utf-8'))
                s2.sendall(f"\nGame over! {winner} wins!".encode('utf-8'))
                game_over = True
            
        except Exception as e:
            print(f"Error: {e}")
            print("Connection lost. Ending game.")
            game_over = True
            break
    
    s1.close()
    s2.close()
    server_socket.close()

if __name__ == "__main__":
    start_server()