import socket
import chess
import chess.engine

board = [
    ["r", "n", "b", "q", "k", "b", "n", "r"], #black pieces
    ["p", "p", "p", "p", "p", "p", "p", "p"], #black pawns
    [".", ".", ".", ".", ".", ".", ".", "."], 
    [".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", "."],
    [".", ".", ".", ".", ".", ".", ".", "."],
    ["P", "P", "P", "P", "P", "P", "P", "P"],  #white pawns
    ["R", "N", "B", "Q", "K", "B", "N", "R"] #white pieces
]


def is_valid_move(board, move):
    try:
        chess.Move.from_uci(move)
        return move in [m.uci() for m in board.legal_moves]
    except:
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
    
    s1, addr1 = clients[0]
    s2, addr2 = clients[1]
    
    board = chess.Board()
    
    while True:
        try:
            move1 = s1.recv(1024).decode('utf-8').strip()
            if not move1 or move1.lower() == "quit":
                print("Player 1 quit. Ending game.")
                s2.sendall(b"Opponent quit. Game over.")
                break
            
            if is_valid_move(board, move1):
                board.push(chess.Move.from_uci(move1))
                print(f"Player 1 move: {move1}")
                s2.sendall(move1.encode('utf-8'))
            else:
                print("Invalid move from Player 1.")
                s1.sendall(b"Invalid move. Try again.")
                continue
            
            move2 = s2.recv(1024).decode('utf-8').strip()
            if not move2 or move2.lower() == "quit":
                print("Player 2 quit. Ending game.")
                s1.sendall(b"Opponent quit. Game over.")
                break
            
            if is_valid_move(board, move2):
                board.push(chess.Move.from_uci(move2))
                print(f"Player 2 move: {move2}")
                s1.sendall(move2.encode('utf-8'))
            else:
                print("Invalid move from Player 2.")
                s2.sendall(b"Invalid move. Try again.")
                continue
            
        except:
            print("Connection lost. Ending game.")
            break
    
    s1.close()
    s2.close()
    server_socket.close()

if __name__ == "__main__":
    start_server()