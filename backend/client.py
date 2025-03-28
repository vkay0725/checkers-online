import socket

def start_client(host='127.0.0.1', port=65244):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((host, port))
    print(f"Connected to server at {host}:{port}")
    
    while True:
        move = input("Enter your chess move (or 'quit' to exit): ")
        client_socket.sendall(move.encode('utf-8'))
        
        if move.lower() == "quit":
            break
        
        response = client_socket.recv(1024).decode('utf-8')
        if not response or response.lower() == "opponent quit. game over.":
            print("Opponent quit. Game over.")
            break
        print(f"Opponent's move: {response}")
    
    client_socket.close()
    print("Disconnected from server.")

if __name__ == "__main__":
    start_client()