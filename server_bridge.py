from email_handler import EmailHandler
import os

# Create an instance of EmailHandler
email_handler = EmailHandler()

# def setup_email_credentials():
#     """Function to set up email credentials interactively if not set as environment variables"""
#     if not os.environ.get("CHECKERS_EMAIL") or not os.environ.get("CHECKERS_PASSWORD"):
#         print("Email credentials not found in environment variables.")
#         print("To enable email functionality, please provide credentials:")
        
#         email = input("Email address for sending game summaries: ")
#         password = input("Password or app password: ")
        
#         # If the user doesn't want to configure email, that's fine
#         if not email or not password:
#             print("Email credentials not provided. Email functionality will be disabled.")
#             return
            
#         os.environ["CHECKERS_EMAIL"] = email
#         os.environ["CHECKERS_PASSWORD"] = password
#         print("Email credentials set. Game summaries will be sent when games end.")
#     else:
#         print("Email credentials found in environment variables.")
def setup_email_credentials():
    """Function to set up email credentials - using hard-coded values"""
    print("Email credentials configured. Game summaries will be sent when games end.")
    # No need to do anything since credentials are hard-coded in EmailHandler

def handle_email_preference(message, player_color):
    """Process email preference message from client"""
    if message.startswith("EMAIL:"):
        email = message[6:].strip()  # Extract email from the message
        success = email_handler.set_player_email(player_color, email)
        return True, f"Email preference set to: {email}" if success else "Invalid email format"
    return False, ""

def record_move(player_color, from_pos, to_pos, board_state):
    """Record a move in the game history for the summary"""
    email_handler.add_move(player_color, from_pos, to_pos, board_state)

def on_game_start():
    """Reset game history when a new game starts"""
    email_handler.reset_game()

def on_game_end(end_reason="Game completed", winner=None):
    """Generate and send game summary when a game ends"""
    print("entered game end function")
    email_handler.send_game_summary(end_reason, winner)