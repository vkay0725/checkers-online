import socket

def start_client(host='127.0.0.1', port=65244):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        client_socket.connect((host, port))
        print(f"Connected to server at {host}:{port}")
        
        # Get player assignment and initial board
        player_assignment = client_socket.recv(1024).decode('utf-8')
        print(player_assignment)
        
        # Get initial board state
        initial_board = client_socket.recv(1024).decode('utf-8')
        print(initial_board)
        
        while True:
            # Get server message (either "Your turn" or "Waiting for opponent")
            server_message = client_socket.recv(1024).decode('utf-8')
            print(server_message)
            
            if "Game over" in server_message or "wins" in server_message:
                break
                
            if "Your turn" in server_message:
                # It's our turn to move
                move = input("Enter your move (row,col-row,col) or 'quit' to exit: ")
                client_socket.sendall(move.encode('utf-8'))
                
                if move.lower() == "quit":
                    print("You quit the game.")
                    break
                
                # Check if the move was invalid
                response = client_socket.recv(1024).decode('utf-8')
                if "Invalid move" in response:
                    print(response)
                    move = input(response)
                    client_socket.sendall(move.encode('utf-8'))
                    
                    if move.lower() == "quit":
                        print("You quit the game.")
                        break
            
            elif "Opponent quit" in server_message:
                print("Opponent quit. Game over.")
                break
    
    except ConnectionRefusedError:
        print("Could not connect to the server. Make sure the server is running.")
    except ConnectionResetError:
        print("Connection to server was reset. Server might have closed.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client_socket.close()
        print("Disconnected from server.")

if __name__ == "__main__":
    start_client()