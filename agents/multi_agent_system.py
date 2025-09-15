import os
import re
import time
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, Any
import sys

# Add parent directory 
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def call_llm(self, prompt: str, system_msg: str = None) -> tuple:
        start = time.time()
        try:
            messages = []
            if system_msg:
                messages.append({"role": "system", "content": system_msg})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=300
            )
            
            processing_time = int((time.time() - start) * 1000)
            return response.choices[0].message.content.strip(), processing_time
        except Exception as e:
            return f"Error: {str(e)}", int((time.time() - start) * 1000)

class ClassifierAgent(BaseAgent):
    def __init__(self):
        super().__init__("Classifier")
    
    def process(self, user_input: str) -> Dict[str, Any]:
        # Rule-based check for ticket numbers
        if re.search(r'(INC|REQ|CRQ|PBI|RLM)\d{10}', user_input.upper()):
            return {
                'success': True,
                'classification': 'query',
                'confidence': 0.95,
                'method': 'rule_based',
                'processing_time_ms': 5
            }
        
        # LLM classification for sentiment
        system_msg = """Classify as: positive_feedback, negative_feedback, or query
        Respond with only the classification."""
        
        prompt = f"Message: '{user_input}'"
        llm_response, time_ms = self.call_llm(prompt, system_msg)
        
        classification = llm_response.lower().strip()
        if classification not in ['positive_feedback', 'negative_feedback', 'query']:
            classification = 'unknown'
        
        return {
            'success': classification != 'unknown',
            'classification': classification,
            'confidence': 0.8,
            'method': 'llm_based',
            'processing_time_ms': time_ms
        }

class FeedbackHandlerAgent(BaseAgent):
    def __init__(self, db):
        super().__init__("FeedbackHandler")
        self.db = db
    
    def process(self, user_input: str, classification: str, customer_name: str = "Valued Customer") -> Dict[str, Any]:
        if classification == 'positive_feedback':
            return self._handle_positive(user_input, customer_name)
        elif classification == 'negative_feedback':
            return self._handle_negative(user_input, customer_name)
        
        return {'success': False, 'response': 'Invalid classification'}
    
    def _handle_positive(self, user_input: str, customer_name: str) -> Dict[str, Any]:
        system_msg = f"""Create a warm thank you response for positive banking feedback.
        Customer name: {customer_name}
        Keep under 80 words."""
        
        response, time_ms = self.call_llm(f"Feedback: '{user_input}'", system_msg)
        
        self.db.log_interaction(user_input, 'positive_feedback', 'FeedbackHandler', response)
        
        return {
            'success': True,
            'response': response,
            'action': 'thanked_customer',
            'processing_time_ms': time_ms
        }
    
    def _handle_negative(self, user_input: str, customer_name: str) -> Dict[str, Any]:
        # Create incident for negative feedback
        ticket_number = self.db.create_ticket(
            'INC', 
            'Customer Complaint', 
            user_input, 
            customer_name, 
            'High'
        )
        
        response = f"We sincerely apologize for the inconvenience, {customer_name}. " \
                  f"A new incident {ticket_number} has been created and our team " \
                  f"will address this issue promptly."
        
        self.db.log_interaction(user_input, 'negative_feedback', 'FeedbackHandler', 
                               response, ticket_number)
        
        return {
            'success': True,
            'response': response,
            'action': 'incident_created',
            'ticket_number': ticket_number,
            'processing_time_ms': 100
        }

class QueryHandlerAgent(BaseAgent):
    def __init__(self, db):
        super().__init__("QueryHandler")
        self.db = db
    
    def process(self, user_input: str) -> Dict[str, Any]:
        # Extract ticket number
        ticket_match = re.search(r'(INC|REQ|CRQ|PBI|RLM)\d{10}', user_input.upper())
        
        if not ticket_match:
            return {
                'success': False,
                'response': 'Please provide a valid ticket number (INC/REQ/CRQ/PBI/RLM + 10 digits)',
                'processing_time_ms': 5
            }
        
        ticket_number = ticket_match.group(0)
        ticket_details = self.db.get_ticket(ticket_number)
        
        if not ticket_details:
            response = f"Ticket {ticket_number} not found. Please verify the number."
            self.db.log_interaction(user_input, 'query', 'QueryHandler', response, ticket_number, False)
            return {
                'success': False,
                'response': response,
                'ticket_number': ticket_number,
                'processing_time_ms': 50
            }
        
        # Generate response based on ticket status
        response = self._generate_status_response(ticket_details)
        
        self.db.log_interaction(user_input, 'query', 'QueryHandler', response, ticket_number)
        
        return {
            'success': True,
            'response': response,
            'ticket_number': ticket_number,
            'ticket_details': ticket_details,
            'processing_time_ms': 75
        }
    
    def _generate_status_response(self, ticket: Dict) -> str:
        ticket_type = ticket['type']
        number = ticket['number']
        status = ticket['status']
        title = ticket['title']
        
        type_names = {
            'INC': 'Incident', 'REQ': 'Service Request', 'CRQ': 'Change Request',
            'PBI': 'Problem', 'RLM': 'Release'
        }
        
        type_name = type_names.get(ticket_type, 'Ticket')
        
        if status == 'New':
            return f"Your {type_name} {number} '{title}' has been logged and is awaiting assignment."
        elif status == 'In Progress':
            return f"Your {type_name} {number} '{title}' is currently being worked on by our team."
        elif status == 'Resolved':
            resolution = ticket.get('resolution', 'Issue resolved.')
            return f"Your {type_name} {number} '{title}' has been resolved. {resolution}"
        elif status == 'Closed':
            return f"Your {type_name} {number} '{title}' has been closed."
        else:
            return f"Your {type_name} {number} is currently '{status}'."

class MultiAgentOrchestrator:
    def __init__(self, db):
        self.db = db
        self.classifier = ClassifierAgent()
        self.feedback_handler = FeedbackHandlerAgent(db)
        self.query_handler = QueryHandlerAgent(db)
    
    def process_message(self, user_input: str, customer_name: str = "Valued Customer") -> Dict[str, Any]:
        """Main orchestrator method"""
        start_time = time.time()
        
        # Step 1: Classify the message
        classification_result = self.classifier.process(user_input)
        
        if not classification_result['success']:
            return {
                'success': False,
                'response': 'Unable to understand your message. Please try again.',
                'total_processing_time_ms': int((time.time() - start_time) * 1000)
            }
        
        classification = classification_result['classification']
        
        # Step 2: Route to appropriate handler
        if classification in ['positive_feedback', 'negative_feedback']:
            result = self.feedback_handler.process(user_input, classification, customer_name)
            agent_path = f"Classifier → FeedbackHandler"
            
        elif classification == 'query':
            result = self.query_handler.process(user_input)
            agent_path = f"Classifier → QueryHandler"
            
        else:
            return {
                'success': False,
                'response': 'Unable to process your request.',
                'total_processing_time_ms': int((time.time() - start_time) * 1000)
            }
        
        # Add orchestration metadata
        result.update({
            'classification': classification,
            'classification_confidence': classification_result.get('confidence', 0),
            'agent_path': agent_path,
            'total_processing_time_ms': int((time.time() - start_time) * 1000)
        })
        
        return result

# Test the system
if __name__ == "__main__":
    from database.bmc_database import setup_sample_data
    
    # Setup database with sample data
    db = setup_sample_data()
    
    # Initialize orchestrator
    orchestrator = MultiAgentOrchestrator(db)
    
    # Test cases
    test_cases = [
        ("Thanks for resolving my issue quickly!", "John Smith"),
        ("My credit card is still not working", "Jane Doe"),  
        ("What's the status of INC1234567890?", "Mike Johnson"),
        ("Can you check REQ9876543210?", "Sarah Wilson")
    ]
    
    print("🧪 Testing Multi-Agent System")
    print("=" * 50)
    
    for i, (message, customer) in enumerate(test_cases, 1):
        print(f"\nTest {i}: {message}")
        result = orchestrator.process_message(message, customer)
        
        if result['success']:
            print(f"✅ Classification: {result['classification']}")
            print(f"   Agent Path: {result['agent_path']}")
            print(f"   Response: {result['response']}")
            print(f"   Time: {result['total_processing_time_ms']}ms")
            
            if 'ticket_number' in result:
                print(f"   Ticket: {result['ticket_number']}")
        else:
            print(f"❌ Error: {result['response']}")
    
    print("\n🎉 Multi-Agent System testing complete!")