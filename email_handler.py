
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import datetime
import threading

class EmailHandler:
    def __init__(self, smtp_server="smtp.gmail.com", smtp_port=587):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = "xxxx@iitdh.ac.in"
        self.sender_password = "abcd" #enter your password generated from apps.google.com
        
        # Player email addresses
        self.player_emails = {
            "BLACK": None,
            "WHITE": None
        }
        
        # Game history for summary
        self.game_history = []
        self.game_start_time = None
        
    def set_player_email(self, player_color, email):
        """Set email address for a player"""
        if email and "@" in email:  # Basic validation
            self.player_emails[player_color] = email
            return True
        return False
    
    def get_player_email(self, player_color):
        """Get email address for a player"""
        return self.player_emails[player_color]
    
    def reset_game(self):
        """Reset game history when starting a new game"""
        self.game_history = []
        self.game_start_time = datetime.datetime.now()
    
    def add_move(self, player_color, from_pos, to_pos, board_state):
        """Add a move to the game history"""
        timestamp = datetime.datetime.now()
        move_entry = {
            "timestamp": timestamp,
            "player": player_color,
            "from": from_pos,
            "to": to_pos,
            "board": board_state
        }
        self.game_history.append(move_entry)
    
    def generate_game_summary(self, end_reason="Game completed", winner=None):
        """Generate a text summary of the game"""
        if not self.game_history:
            return "No game data available."
        
        summary = "CHECKERS GAME SUMMARY\n"
        summary += "=====================\n\n"
        
        # Game metadata
        summary += f"Date: {self.game_start_time.strftime('%Y-%m-%d')}\n"
        summary += f"Start time: {self.game_start_time.strftime('%H:%M:%S')}\n"
        summary += f"End time: {datetime.datetime.now().strftime('%H:%M:%S')}\n"
        summary += f"End reason: {end_reason}\n"
        if winner:
            summary += f"Winner: {winner}\n"
        summary += "\n"
        
        # Game moves
        summary += "MOVES:\n"
        summary += "------\n"
        for i, move in enumerate(self.game_history, 1):
            time_str = move["timestamp"].strftime('%H:%M:%S')
            summary += f"{i}. {move['player']} moved from {move['from']} to {move['to']} ({time_str})\n"
        
        summary += "\n"
        summary += "FINAL BOARD STATE:\n"
        summary += "----------------\n"
        if self.game_history:
            summary += self.game_history[-1]["board"]
        
        return summary
    
    def save_summary_to_file(self, summary):
        """Save the summary to a file and return the filename"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"checkers_game_{timestamp}.txt"
        
        with open(filename, "w") as f:
            f.write(summary)
        
        return filename
    
    def send_game_summary(self, end_reason="Game completed", winner=None):
        """Generate summary and send to players who provided email addresses"""
        if not self.sender_email or not self.sender_password:
            print("Email credentials not configured. Can't send summary.")
            return False
        print("hii")
        summary = self.generate_game_summary(end_reason, winner)
        filename = self.save_summary_to_file(summary)
        
        # Send emails in background thread to avoid blocking
        threading.Thread(
            target=self._send_emails,
            args=(summary, filename),
            daemon=True
        ).start()
        
        return True
    
    def _send_emails(self, summary, filename):
        """Internal method to send emails to players"""
        # Check if any players provided an email
        print("sending email now")
        recipients = [email for email in self.player_emails.values() if email]
        if not recipients:
            print("No recipients to send emails to.")
            return
        
        try:
            # Connect to server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                
                # Send to each recipient separately
                for recipient in recipients:
                    # Create a new message for each recipient
                    message = MIMEMultipart()
                    message["From"] = self.sender_email
                    message["To"] = recipient
                    message["Subject"] = "Your Checkers Game Summary"
                    
                    # Attach the body
                    body = "Thank you for playing Checkers! Please find attached the summary of your game."
                    message.attach(MIMEText(body, "plain"))
                    
                    # Attach the file
                    with open(filename, "rb") as file:
                        attachment = MIMEApplication(file.read(), Name=filename)
                    attachment["Content-Disposition"] = f'attachment; filename="{filename}"'
                    message.attach(attachment)
                    
                    # Send email
                    server.sendmail(self.sender_email, recipient, message.as_string())
                    print(f"Email sent to {recipient}")
            
            print("All emails sent successfully!")
            
        except Exception as e:
            print(f"Failed to send emails: {str(e)}")
        
        # Clean up the file
        try:
            os.remove(filename)
        except:
            pass
