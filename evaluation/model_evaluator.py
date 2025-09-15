# evaluation/model_evaluator.py
import sqlite3
import json
from typing import Dict, List, Any
from datetime import datetime, timedelta

class ModelEvaluator:
    """Implements requirement 7: Model Evaluation"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
        # Test cases for classification evaluation
        self.test_cases = [
            {"message": "Thank you for solving my issue!", "expected": "positive_feedback", "category": "gratitude"},
            {"message": "Great service from your team!", "expected": "positive_feedback", "category": "praise"},
            {"message": "My card is still not working", "expected": "negative_feedback", "category": "complaint"},
            {"message": "Very disappointed with the delay", "expected": "negative_feedback", "category": "dissatisfaction"},
            {"message": "What's the status of INC1234567890?", "expected": "query", "category": "status_inquiry"},
            {"message": "Can you check ticket REQ0987654321?", "expected": "query", "category": "ticket_lookup"},
            {"message": "Please help me with my account", "expected": "query", "category": "help_request"},
            {"message": "Thanks for the quick resolution!", "expected": "positive_feedback", "category": "appreciation"},
            {"message": "This is taking too long", "expected": "negative_feedback", "category": "frustration"},
            {"message": "Status of PBI5555555555?", "expected": "query", "category": "problem_inquiry"}
        ]
    
    def evaluate_classification_accuracy(self, orchestrator) -> Dict[str, Any]:
        """Evaluate classifier accuracy against test cases"""
        results = {
            "total_tests": len(self.test_cases),
            "correct_classifications": 0,
            "accuracy_percentage": 0.0,
            "detailed_results": [],
            "category_performance": {}
        }
        
        category_stats = {}
        
        for test_case in self.test_cases:
            # Get classification from orchestrator
            classification_result = orchestrator.classifier.process(test_case["message"])
            actual = classification_result.get('classification', 'unknown')
            expected = test_case["expected"]
            category = test_case["category"]
            
            is_correct = actual == expected
            if is_correct:
                results["correct_classifications"] += 1
            
            # Track category performance
            if category not in category_stats:
                category_stats[category] = {"total": 0, "correct": 0}
            category_stats[category]["total"] += 1
            if is_correct:
                category_stats[category]["correct"] += 1
            
            results["detailed_results"].append({
                "message": test_case["message"],
                "expected": expected,
                "actual": actual,
                "correct": is_correct,
                "category": category,
                "confidence": classification_result.get('confidence', 0)
            })
        
        # Calculate overall accuracy
        results["accuracy_percentage"] = (results["correct_classifications"] / results["total_tests"]) * 100
        
        # Calculate category performance
        for category, stats in category_stats.items():
            accuracy = (stats["correct"] / stats["total"]) * 100
            results["category_performance"][category] = {
                "accuracy": accuracy,
                "correct": stats["correct"],
                "total": stats["total"]
            }
        
        return results
    
    def evaluate_response_quality(self) -> Dict[str, Any]:
        """Evaluate response quality from database logs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get recent AI interactions
        cursor.execute("""
            SELECT user_message, classification, response_generated, success, agent_used
            FROM ai_logs
            ORDER BY timestamp DESC
            LIMIT 50
        """)
        
        interactions = cursor.fetchall()
        conn.close()
        
        if not interactions:
            return {"message": "No interactions found for evaluation"}
        
        results = {
            "total_interactions": len(interactions),
            "success_rate": 0.0,
            "response_quality_scores": {
                "empathy_score": 0.0,
                "clarity_score": 0.0,
                "completeness_score": 0.0
            },
            "agent_performance": {},
            "classification_distribution": {}
        }
        
        successful_interactions = sum(1 for interaction in interactions if interaction[3])
        results["success_rate"] = (successful_interactions / len(interactions)) * 100
        
        # Analyze by agent
        agent_stats = {}
        classification_stats = {}
        
        for interaction in interactions:
            user_msg, classification, response, success, agent = interaction
            
            # Agent performance
            if agent not in agent_stats:
                agent_stats[agent] = {"total": 0, "successful": 0}
            agent_stats[agent]["total"] += 1
            if success:
                agent_stats[agent]["successful"] += 1
            
            # Classification distribution
            if classification not in classification_stats:
                classification_stats[classification] = 0
            classification_stats[classification] += 1
            
            # Simple response quality scoring
            if success and response:
                response_length = len(response.split())
                empathy_keywords = ['apologize', 'sorry', 'thank', 'appreciate', 'understand', 'delighted']
                clarity_indicators = ['ticket', 'status', 'resolved', 'created', 'team']
                
                empathy_score = sum(1 for word in empathy_keywords if word in response.lower())
                clarity_score = min(response_length / 20, 1.0)  # Normalize by expected length
                completeness_score = 1.0 if any(indicator in response.lower() for indicator in clarity_indicators) else 0.5
                
                results["response_quality_scores"]["empathy_score"] += empathy_score
                results["response_quality_scores"]["clarity_score"] += clarity_score
                results["response_quality_scores"]["completeness_score"] += completeness_score
        
        # Average the scores
        if successful_interactions > 0:
            for score_type in results["response_quality_scores"]:
                results["response_quality_scores"][score_type] /= successful_interactions
        
        # Agent performance percentages
        for agent, stats in agent_stats.items():
            success_rate = (stats["successful"] / stats["total"]) * 100
            results["agent_performance"][agent] = {
                "success_rate": success_rate,
                "total_interactions": stats["total"]
            }
        
        results["classification_distribution"] = classification_stats
        
        return results
    
    def evaluate_agent_routing_success(self) -> Dict[str, Any]:
        """Evaluate agent routing effectiveness"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get routing data
        cursor.execute("""
            SELECT classification, agent_used, success
            FROM ai_logs
            WHERE classification IS NOT NULL AND agent_used IS NOT NULL
        """)
        
        routing_data = cursor.fetchall()
        conn.close()
        
        if not routing_data:
            return {"message": "No routing data available"}
        
        results = {
            "total_routings": len(routing_data),
            "correct_routings": 0,
            "routing_accuracy": 0.0,
            "routing_matrix": {}
        }
        
        # Expected routing patterns
        expected_routing = {
            "positive_feedback": "FeedbackHandler",
            "negative_feedback": "FeedbackHandler", 
            "query": "QueryHandler"
        }
        
        routing_matrix = {}
        
        for classification, agent, success in routing_data:
            # Track routing patterns
            if classification not in routing_matrix:
                routing_matrix[classification] = {}
            if agent not in routing_matrix[classification]:
                routing_matrix[classification][agent] = {"count": 0, "successful": 0}
            
            routing_matrix[classification][agent]["count"] += 1
            if success:
                routing_matrix[classification][agent]["successful"] += 1
            
            # Check if routing was correct
            expected_agent = expected_routing.get(classification)
            if expected_agent and expected_agent in agent:
                results["correct_routings"] += 1
        
        results["routing_accuracy"] = (results["correct_routings"] / results["total_routings"]) * 100
        results["routing_matrix"] = routing_matrix
        
        return results
    
    def generate_comprehensive_report(self, orchestrator) -> Dict[str, Any]:
        """Generate complete evaluation report as per requirement 7"""
        report = {
            "evaluation_timestamp": datetime.now().isoformat(),
            "classification_evaluation": self.evaluate_classification_accuracy(orchestrator),
            "response_quality_evaluation": self.evaluate_response_quality(),
            "agent_routing_evaluation": self.evaluate_agent_routing_success()
        }
        
        # Overall system health score
        classification_score = report["classification_evaluation"]["accuracy_percentage"]
        response_success_rate = report["response_quality_evaluation"].get("success_rate", 0)
        routing_accuracy = report["agent_routing_evaluation"].get("routing_accuracy", 0)
        
        overall_score = (classification_score + response_success_rate + routing_accuracy) / 3
        
        report["overall_system_health"] = {
            "score": overall_score,
            "grade": self._get_grade(overall_score),
            "recommendations": self._get_recommendations(report)
        }
        
        return report
    
    def _get_grade(self, score: float) -> str:
        """Convert numeric score to grade"""
        if score >= 90:
            return "A - Excellent"
        elif score >= 80:
            return "B - Good"
        elif score >= 70:
            return "C - Satisfactory"
        elif score >= 60:
            return "D - Needs Improvement"
        else:
            return "F - Poor"
    
    def _get_recommendations(self, report: Dict) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        
        classification_accuracy = report["classification_evaluation"]["accuracy_percentage"]
        if classification_accuracy < 85:
            recommendations.append("Improve classification model with more training examples")
        
        response_quality = report["response_quality_evaluation"]
        empathy_score = response_quality["response_quality_scores"]["empathy_score"]
        if empathy_score < 0.5:
            recommendations.append("Enhance response templates with more empathetic language")
        
        routing_accuracy = report["agent_routing_evaluation"].get("routing_accuracy", 0)
        if routing_accuracy < 90:
            recommendations.append("Review agent routing logic for edge cases")
        
        if not recommendations:
            recommendations.append("System performing well - continue monitoring")
        
        return recommendations

# Test function to demonstrate evaluation
def run_evaluation_demo():
    """Demo function showing evaluation in action"""
    from database.bmc_database import BMCDatabase
    from agents.multi_agent_system import MultiAgentOrchestrator
    
    # Initialize system
    db = BMCDatabase()
    orchestrator = MultiAgentOrchestrator(db)
    evaluator = ModelEvaluator(db.db_path)
    
    # Run some test interactions first
    test_messages = [
        ("Thanks for your help!", "Test User"),
        ("My card doesn't work", "Test User"),
        ("Status of INC1234567890?", "Test User")
    ]
    
    for message, customer in test_messages:
        orchestrator.process_message(message, customer)
    
    # Generate evaluation report
    report = evaluator.generate_comprehensive_report(orchestrator)
    
    print("=== MODEL EVALUATION REPORT ===")
    print(f"Overall System Health: {report['overall_system_health']['grade']}")
    print(f"Classification Accuracy: {report['classification_evaluation']['accuracy_percentage']:.1f}%")
    print(f"Response Success Rate: {report['response_quality_evaluation'].get('success_rate', 0):.1f}%")
    print(f"Agent Routing Accuracy: {report['agent_routing_evaluation'].get('routing_accuracy', 0):.1f}%")
    print("\nRecommendations:")
    for rec in report['overall_system_health']['recommendations']:
        print(f"- {rec}")

if __name__ == "__main__":
    run_evaluation_demo()