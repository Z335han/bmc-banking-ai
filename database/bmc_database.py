import sqlite3
import random
from typing import Optional, Dict

class BMCDatabase:
    def __init__(self, db_path: str = "bmc_banking.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # All ticket types in one table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_number VARCHAR(13) PRIMARY KEY,
                ticket_type VARCHAR(3),
                title VARCHAR(200),
                description TEXT,
                status VARCHAR(20) DEFAULT 'New',
                priority VARCHAR(10) DEFAULT 'Medium',
                customer_name VARCHAR(100),
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolution TEXT
            )
        ''')
        
        # AI interactions log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_message TEXT,
                classification VARCHAR(20),
                agent_used VARCHAR(30),
                response TEXT,
                ticket_number VARCHAR(13),
                success BOOLEAN DEFAULT 1,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✅ Database ready: {self.db_path}")
    
    def generate_ticket_number(self, ticket_type: str) -> str:
        """Generate ticket number: INC/REQ/CRQ/PBI/RLM + 10 digits"""
        while True:
            number = f"{ticket_type}{random.randint(1000000000, 9999999999)}"
            if not self.ticket_exists(number):
                return number
    
    def ticket_exists(self, ticket_number: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM tickets WHERE ticket_number = ?', (ticket_number,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    
    def create_ticket(self, ticket_type: str, title: str, description: str, 
                     customer_name: str = "Unknown", priority: str = "Medium") -> str:
        ticket_number = self.generate_ticket_number(ticket_type)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tickets (ticket_number, ticket_type, title, description, 
                                   priority, customer_name)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ticket_number, ticket_type, title, description, priority, customer_name))
            conn.commit()
            conn.close()
            print(f"✅ Created {ticket_type}: {ticket_number}")
            return ticket_number
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def get_ticket(self, ticket_number: str) -> Optional[Dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tickets WHERE ticket_number = ?', (ticket_number,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'number': result[0], 'type': result[1], 'title': result[2],
                    'description': result[3], 'status': result[4], 'priority': result[5],
                    'customer': result[6], 'created': result[7], 'resolution': result[8]
                }
            return None
        except:
            return None
    
    def update_status(self, ticket_number: str, status: str, resolution: str = None) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE tickets SET status = ?, resolution = ? WHERE ticket_number = ?
            ''', (status, resolution, ticket_number))
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except:
            return False
    
    def log_interaction(self, user_msg: str, classification: str, agent: str, 
                       response: str, ticket_num: str = None, success: bool = True):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ai_logs (user_message, classification, agent_used, 
                                   response, ticket_number, success)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_msg, classification, agent, response, ticket_num, success))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Log error: {e}")

def setup_sample_data():
    """Create sample tickets"""
    db = BMCDatabase()
    
    # Sample tickets
    samples = [
        ("INC", "Credit Card Blocked", "Card blocked after suspicious activity", "John Smith", "High"),
        ("REQ", "New Debit Card", "Request new debit card", "Jane Doe", "Medium"),
        ("PBI", "ATM Network Down", "Multiple ATM failures", "System", "Critical"),
        ("CRQ", "System Upgrade", "Core banking upgrade", "IT Team", "High"),
        ("RLM", "Mobile App v2.1", "New mobile app release", "Dev Team", "Medium")
    ]
    
    for ticket_type, title, desc, customer, priority in samples:
        db.create_ticket(ticket_type, title, desc, customer, priority)
    
    # Resolve some tickets
    db.update_status("INC1234567890", "Resolved", "Card unblocked after verification")
    
    print("✅ Sample data created!")
    return db

if __name__ == "__main__":
    setup_sample_data()