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
    
    #Display the board with color if possible
    lines = board_str.strip().split('\n')
    
    #Print the board with some formatting
    print("\n===== CHECKERS BOARD =====")
    print("  A B C D E F G H")  #Column headers
    
    row_num = 8
    for i, line in enumerate(lines):
        if i == 0:  #Skip the first line that has column numbers
            continue
        
        #Print row number
        print(f"{row_num} ", end="")
        row_num -= 1
        
        #Print pieces with potential colors
        for char in line[2:].split():  #Skip the row number and process each cell
            if char == '.':
                print('· ', end="")
            elif char == 'b':
                print('○ ', end="")  #Black piece
            elif char == 'w':
                print('● ', end="")  #White piece
            elif char == 'B':
                print('♔ ', end="")  #Black king
            elif char == 'W':
                print('♚ ', end="")  #White king
            else:
                print(char + ' ', end="")
        print()
    
    print("===========================")

def message_listener(client_socket):
    """Listen for and process messages from the server"""
    global waiting_for_game, client_active
    should_exit = False
    
    while True:
        try:
            server_message = client_socket.recv(1024).decode('utf-8')
            if not server_message:  #Empty message, server closed connection
                print("\nServer closed connection.")
                client_active = False
                try:
                    client_socket.close()
                except:
                    pass
                break
            
            #Check if server rejected the connection
            if "SERVER FULL" in server_message:
                print(server_message)
                client_active = False
                return False
            
            #Detection of game state changes
            if "Game started!" in server_message or "New game started!" in server_message or "Game restarted!" in server_message:
                waiting_for_game = False
                print("Game is starting!")
            elif "Game in progress" in server_message:
                waiting_for_game = False
                print("Joining existing game in progress!")
            elif "Waiting for another player" in server_message:
                waiting_for_game = True
                print("Waiting for another player to join...")
            elif "Your turn" in server_message:
                waiting_for_game = False
                print("\nIt's your turn to move!")
            
            #Check for board display
            if "  A B C D E F G H" in server_message:
                #Extract and display the board between row markers
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
            
            #Always print the message after handling special cases
            print(server_message)
            
            #Check for game events
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
                    client_active = False
                    break
            
            #Handle game ending by a player
            elif "You ended the game" in server_message or "BLACK ended the game" in server_message or "WHITE ended the game" in server_message:
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
                    client_active = False
                    break
            elif "Opponent quit" in server_message:
                print("Opponent quit. Game over.")
                response = input("Wait for another player? (yes/no): ").strip().lower()
                if response == "yes":
                    print("Waiting for another player to connect...")
                    waiting_for_game = True
                else:
                    client_socket.sendall("quit".encode('utf-8'))
                    print("You quit the game.")
                    should_exit = True
                    client_active = False
                    break
        
        except ConnectionResetError:
            print("\nConnection reset by server.")
            client_active = False
            break
        except Exception as e:
            print(f"\nError receiving data: {e}")
            client_active = False
            break
    return should_exit 

#Function to get email preference
def get_email_preference():
    while True:
        """Ask the user if they want to receive a game summary by email"""
        print("\nWould you like to receive a game summary by email when the game ends?")
        choice = input("Enter 'yes' or 'no': ").strip().lower()
        
        if choice == 'yes':
            email = input("Please enter your email address: ").strip()
            if '@' in email:  #Basic validation
                return email
            else:
                print("Invalid email format. No email will be sent.")
                return None
        elif choice == 'no':
            return None
        else:
            print("Invalid choice. Please enter 'yes' or 'no'.")

def start_client(host='127.0.0.1', port=65244):
    """Start the checkers client"""
    global waiting_for_game, client_active
    waiting_for_game = True  #Initialize as waiting
    client_active = True
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        client_socket.connect((host, port))
        print(f"Connecting to server at {host}:{port}")
                
        #Start a thread to listen for server messages
        listener_thread = threading.Thread(target=message_listener, args=(client_socket,), daemon=True)
        listener_thread.start()
        
        #Wait briefly for initial server response
        time.sleep(1)
        
        #Check if connection was rejected
        if not client_active:
            return
        
        #Ask for email preference before starting the game
        email = get_email_preference()
        if email:
            print(f"Email preference set to: {email}")
            client_socket.sendall(f"EMAIL:{email}".encode('utf-8'))
            time.sleep(0.5)  #Give server time to process
        
        #Main input loop
        should_exit = False
        status_message_timer = 0
        waiting_message_count = 0  #To avoid spamming waiting messages

        while not should_exit and client_active:
            try:
                #Only prompt for input if not waiting for a game
                if not waiting_for_game and client_active:
                    #Reset waiting message counter when active
                    waiting_message_count = 0
                    
                    move = input("\nEnter your move (e.g., E2 to E4), 'end game' to end the game, or 'quit' to exit: ")
                    
                    #Check if client is still active before sending
                    if not client_active:
                        print("\nConnection to server lost.")
                        break
                        
                    if move.lower() == "quit":
                        client_socket.sendall("quit".encode('utf-8'))
                        print("You quit the game.")
                        break
                    elif move.lower() == "end game":
                        client_socket.sendall("end game".encode('utf-8'))
                        print("Ending the game...")
                        time.sleep(1)  #Wait for server response
                    else:
                        #Send the move to the server
                        client_socket.sendall(move.encode('utf-8'))
                        time.sleep(0.5)  #Wait for server response
                else:
                    #Don't wait forever if server connection is lost
                    if not client_active:
                        print("\nConnection to server lost while waiting for game.")
                        break
                        
                    time.sleep(1)  #Check every second
                    
                    #Print status message periodically, but not too often
                    current_time = int(time.time())
                    if current_time % 10 == 0 and current_time != status_message_timer:
                        status_message_timer = current_time
                        waiting_message_count += 1
                        
                        #After waiting for a while, allow user to cancel waiting
                        if waiting_message_count > 3:  #After about 30 seconds
                            print("Still waiting for game to start... (press Ctrl+C to quit or type 'force' to try to start game)")
                            
                            #Use select to check if user input is available without blocking
                            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                            if rlist:
                                user_input = input().strip().lower()
                                if user_input == "force":
                                    #Try to force restart the game from client side
                                    print("Attempting to force start/restart game...")
                                    client_socket.sendall("new game".encode('utf-8'))
                                    time.sleep(1)  #Wait for server response
                        else:
                            print("Waiting for game to start... (press Ctrl+C to quit)")
                                    
            except KeyboardInterrupt:
                print("\nKeyboard interrupt received. Exiting...")
                try:
                    client_socket.sendall("quit".encode('utf-8'))
                except:
                    pass
                break
            except BrokenPipeError:
                print("\nConnection to server lost (broken pipe).")
                break
            except ConnectionResetError:
                print("\nConnection reset by server.")
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
    host = '127.0.0.1'  #Default host
    port = 65244  #Default port
    
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
    
    #Get host and port from command line arguments if provided
    host, port = parse_arguments()
    
    #Start the client
    try:
        start_client(host, port)
    except KeyboardInterrupt:
        print("\nClient terminated by user.")
    finally:
        print("Goodbye!")
