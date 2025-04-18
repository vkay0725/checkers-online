import socket
import time
import threading
import sys
import os
import select

def clear_screen():
    """Clear the console screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_board(board_str):
    """Display the board nicely in the console"""
    clear_screen()
    
    # Display the board with color if possible
    lines = board_str.strip().split('\n')
    
    # Print the board with some formatting
    print("\n===== CHECKERS BOARD =====")
    print("  A B C D E F G H")  # Column headers
    
    row_num = 8
    for i, line in enumerate(lines):
        if i == 0:  # Skip the first line that has column numbers
            continue
        
        # Print row number
        print(f"{row_num} ", end="")
        row_num -= 1
        
        # Print pieces with potential colors
        for char in line[2:].split():  # Skip the row number and process each cell
            if char == '.':
                print('· ', end="")
            elif char == 'b':
                print('○ ', end="")  # Black piece
            elif char == 'w':
                print('● ', end="")  # White piece
            elif char == 'B':
                print('♔ ', end="")  # Black king
            elif char == 'W':
                print('♚ ', end="")  # White king
            else:
                print(char + ' ', end="")
        print()
    
    print("===========================")

def message_listener(client_socket):
    """Listen for and process messages from the server"""
    global waiting_for_game  # Add this global variable
    should_exit = False  # Add a new flag to control client exit
    
    while True:
        try:
            server_message = client_socket.recv(1024).decode('utf-8')
            if not server_message:  # Empty message, server closed connection
                print("\nServer closed connection.")
                break
            
            # Check if server rejected the connection
            if "SERVER FULL" in server_message:
                print(server_message)
                return False  # Return False to indicate rejection
            
            # Print the message first (including player assignment)
            print(server_message)
            # Check for board display
            if "  A B C D E F G H" in server_message:
                # Extract and display the board between row markers
                lines = server_message.split('\n')
                board_start = -1
                board_end = -1
                for i, line in enumerate(lines):
                    if "  A B C D E F G H" in line:
                        board_start = i
                    if board_start >= 0 and i > board_start and line.strip() == "":
                        board_end = i
                        break
                if board_start >= 0:
                    if board_end < 0:
                        board_end = len(lines)
                    board_str = '\n'.join(lines[board_start:board_end])
                    display_board(board_str)

            # # Check for board update
            # if "Board Updated" in server_message or "Game started" in server_message:
            #     # Extract and display the board
            #     board_start = server_message.find('  0 1 2 3 4 5 6 7')
            #     if board_start != -1:
            #         board_end = server_message.find('\n\n', board_start)
            #         if board_end == -1:
            #             board_end = len(server_message)
            #         board_str = server_message[board_start:board_end]
            #         display_board(board_str)
            
            # Check for game events
            if "Game over" in server_message or "wins" in server_message:
                print("Game has ended.")
                response = input("Play again? (yes/no): ").strip().lower()
                if response == "yes":
                    print("Requesting new game...")
                    client_socket.sendall("new game".encode('utf-8'))
                    waiting_for_game = True
                    print("Waiting for server to restart game...")
                else:
                    print("Thanks for playing!")
                    client_socket.sendall("quit".encode('utf-8'))
                    should_exit = True
                    break
            
            # Handle game ending by a player
            if "You ended the game" in server_message or "BLACK ended the game" in server_message or "WHITE ended the game" in server_message:
                print("Game was ended.")
                response = input("Play another game? (yes/no): ").strip().lower()
                if response == "yes":
                    print("Requesting new game...")
                    client_socket.sendall("new game".encode('utf-8'))
                    waiting_for_game = True
                    print("Waiting for server to restart game...")
                else:
                    print("Thanks for playing!")
                    client_socket.sendall("quit".encode('utf-8'))
                    should_exit = True
                    break
            if "Opponent quit" in server_message:
                print("Opponent quit. Game over.")
                response = input("Wait for another player? (yes/no): ").strip().lower()
                if response == "yes":
                    print("Waiting for another player to connect...")
                    waiting_for_game = True
                else:
                    client_socket.sendall("quit".encode('utf-8'))
                    print("You quit the game.")
                    should_exit = True
                    break
            
            if "Your turn" in server_message:
                waiting_for_game = False  # Reset waiting flag
                print("\nIt's your turn to move!")
        
        except ConnectionResetError:
            print("\nConnection reset by server.")
            break
        except Exception as e:
            print(f"\nError receiving data: {e}")
            break
    return should_exit 

# ADDED: New function to get email preference
def get_email_preference():
    """Ask the user if they want to receive a game summary by email"""
    print("\nWould you like to receive a game summary by email when the game ends?")
    choice = input("Enter 'yes' or 'no': ").strip().lower()
    
    if choice == 'yes':
        email = input("Please enter your email address: ").strip()
        if '@' in email:  # Basic validation
            return email
        else:
            print("Invalid email format. No email will be sent.")
    return None

def start_client(host='127.0.0.1', port=65244):
    """Start the checkers client"""
    global waiting_for_game
    waiting_for_game = False
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        client_socket.connect((host, port))
        print(f"Connecting to server at {host}:{port}")
                
        # Start a thread to listen for server messages
        listener_thread = threading.Thread(target=message_listener, args=(client_socket,), daemon=True)
        listener_thread.start()
        # Wait briefly for initial server response
        time.sleep(1)
        # Check if connection was rejected
        if not listener_thread.is_alive():
            return  # Exit if the listener thread has already exited (meaning we got rejected)
        # ADDED: Ask for email preference before starting the game
        email = get_email_preference()
        if email:
            print(f"Email preference set to: {email}")
            client_socket.sendall(f"EMAIL:{email}".encode('utf-8'))
            time.sleep(0.5)  # Give server time to process
        # Main input loop
        should_exit = False
        while not should_exit:
            try:
                # Only prompt for input if not waiting for a game
                if not waiting_for_game:
                    move = input("\nEnter your move (e.g., E2 to E4), 'end game' to end the game, or 'quit' to exit: ")
                    
                    if move.lower() == "quit":
                        client_socket.sendall("quit".encode('utf-8'))
                        print("You quit the game.")
                        break
                    elif move.lower() == "end game":
                        client_socket.sendall("end game".encode('utf-8'))
                        print("Ending the game...")
                        time.sleep(1)  # Wait for server response
                    else:
                        # Send the move to the server
                        client_socket.sendall(move.encode('utf-8'))
                        
                        # Wait a bit for the server to process
                        time.sleep(0.5)
                else:
                    time.sleep(1)  # Check every second, but don't print anything
                    
                    # Every 10 seconds, print a status update (not every iteration)
                    if int(time.time()) % 10 == 0:
                        print("Still waiting for game to start... (press Ctrl+C to quit)")
                                    
            except KeyboardInterrupt:
                print("\nKeyboard interrupt received. Exiting...")
                client_socket.sendall("quit".encode('utf-8'))
                break
            except Exception as e:
                print(f"Error sending data: {e}")
                break
    
    except ConnectionRefusedError:
        print("Could not connect to the server. Make sure the server is running.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            client_socket.close()
        except:
            pass
        print("Disconnected from server.")

def parse_arguments():
    """Parse command line arguments for host and port"""
    host = '127.0.0.1'  # Default host
    port = 65244  # Default port
    
    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"Invalid port number: {sys.argv[2]}. Using default port {port}.")
    
    return host, port

if __name__ == "__main__":
    print("Welcome to Checkers Client!")
    print("==========================")
    
    # Get host and port from command line arguments if provided
    host, port = parse_arguments()
    
    # Start the client
    try:
        start_client(host, port)
    except KeyboardInterrupt:
        print("\nClient terminated by user.")
    finally:
        print("Goodbye!")
