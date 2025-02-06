import googleapiclient.discovery
from langchain_openai import ChatOpenAI
from typing import TypedDict
from langgraph.graph import StateGraph
from auth import authenticate_google
from dotenv import load_dotenv
import os
import json
import re
from datetime import datetime, timedelta
import pytz

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Authenticate and create Google Calendar service
creds = authenticate_google()
service = googleapiclient.discovery.build("calendar", "v3", credentials=creds)

llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=api_key)

class CalendarState(TypedDict):
    user_input: str
    event_details: dict
    availability_status: str
    confirmation: str
    status: str
    final_message: str  # New field for final status message
    event_link: str     # New field for calendar event link
    error_message: str


def extract_event_details(state: CalendarState):
    user_input= state["user_input"]
    prompt = f"""
    Extract the event title, start time, and end time from the following text: "{user_input}"
    Current time is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.
    
    Rules:
    1. For relative times (like 'tomorrow', 'next week'), convert to actual dates
    2. If no specific date is mentioned, assume tomorrow
    3. If no duration is specified, assume 1 hour
    4. Use 24-hour format
    
    Format dates exactly like this: YYYY-MM-DDTHH:mm:ss
    Example: 2024-03-22T15:00:00
    
    Respond in this exact JSON format:
    {{"title": "string", "start_time": "YYYY-MM-DDTHH:mm:ss", "end_time": "YYYY-MM-DDTHH:mm:ss"}}
    
    Example:
    Input: "Meeting tomorrow at 3pm for 1 hour"
    Output: {{"title": "Meeting", "start_time": "2024-03-22T15:00:00", "end_time": "2024-03-22T16:00:00"}}
    """
    response = llm.invoke(prompt)
    response_content = response.content  # Extract the content from the response

    # Use a regular expression to extract the JSON content
    match = re.search(r'\{.*\}', response_content, re.DOTALL)
    if not match:
        raise ValueError("Failed to extract JSON from response")

    details = json.loads(match.group(0))

    try:
        start = datetime.fromisoformat(details["start_time"])
        end = datetime.fromisoformat(details["end_time"])
        
        # Ensure the dates are in the future
        now = datetime.now()
        if start < now:
            raise ValueError("Start time must be in the future")
        if end <= start:
            raise ValueError("End time must be after start time")
            
        # Format the times in the exact format Google Calendar API expects
        details["start_time"] = start.strftime("%Y-%m-%dT%H:%M:%S")
        details["end_time"] = end.strftime("%Y-%m-%dT%H:%M:%S")
        
    except (ValueError, KeyError) as e:
        raise ValueError(f"DateTime validation failed: {str(e)}")


    print(f"Extracted details: {details}")  # Debugging statement
    state["event_details"] = details
    return state

# Function to check availability
def check_availability(state: CalendarState):
    details = state["event_details"]
    print(f"Checking availability with details: {details}")  # Debugging statement

    try:
        # Add timezone suffix for Google Calendar API
        time_min = f"{details['start_time']}Z"
        time_max = f"{details['end_time']}Z"
        
        print(f"Checking calendar from {time_min} to {time_max}")
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get("items", [])
        
        if events:
            state["availability_status"] = f"⚠️ Slot unavailable! You have {len(events)} conflicting event(s)."
        else:
            state["availability_status"] = "✅ Slot available."
            
    except Exception as e:
        print(f"Error checking availability: {str(e)}")
        state["availability_status"] = f"Error checking availability: {str(e)}"
    
    return state



def end_task(state: CalendarState):
    """Final node to clean up and return the final state"""
    if state["status"] == "completed":
        if not state.get("final_message"):
            state["final_message"] = "✅ Event successfully booked and added to your calendar!"
    elif state["status"] == "cancelled":
        state["final_message"] = "❌ Booking cancelled by user."
    elif state["status"] == "error":
        if not state.get("final_message"):
            state["final_message"] = f"⚠️ Error occurred: {state.get('error_message', 'Unknown error')}"
    
    return state

def confirm_booking(state: CalendarState):
    details = state["event_details"]
    print(f"Confirming booking with details: {details}")
    
    # Add this line to force confirmation for testing
    state["confirmation"] = "confirm"  # Temporary fix for testing
    
    if state.get("confirmation") == "confirm":
        try:
            event = {
                "summary": details["title"],
                "start": {"dateTime": f"{details['start_time']}", "timeZone": "UTC"},  # Remove Z suffix
                "end": {"dateTime": f"{details['end_time']}", "timeZone": "UTC"},      # Remove Z suffix
            }
            
            print(f"Attempting to book event: {event}")  # Debug print
            
            event_result = service.events().insert(calendarId="primary", body=event).execute()
            
            print(f"Booking result: {event_result}")  # Debug print
            
            state["event_link"] = event_result.get('htmlLink')
            state["status"] = "completed"
            state["final_message"] = f"✅ Event successfully booked and added to your calendar!\nView event: {state['event_link']}"
            
        except Exception as e:
            print(f"Booking error: {str(e)}")  # Debug print
            state["status"] = "error"
            state["error_message"] = str(e)
            state["final_message"] = f"⚠️ Error booking event: {str(e)}"
    else:
        state["status"] = "pending_confirmation"
    
    return state

# Define LangGraph nodes
graph = StateGraph(state_schema=CalendarState)

graph.add_node("extract_event_details", extract_event_details)
graph.add_node("check_availability", check_availability)
graph.add_node("confirm_booking", confirm_booking)
graph.add_node('end_task', end_task)

""" graph.add_node("book_event", book_event)
graph.add_node("end_success", end_success)
graph.add_node("end_cancelled", end_cancelled) """

# Define flow
graph.add_edge("extract_event_details", "check_availability")
graph.add_edge("check_availability", "confirm_booking")
graph.add_edge("confirm_booking", "end_task")

# Set entry and terminal points
graph.set_entry_point("extract_event_details")

def handle_booking_condition():
    current_state = input("Enter the current state: ")
    if current_state == "confirm":
        # Manually handle the transition
        graph.current_state = "book_event"
        print("Transitioned to 'book_event'")
    else:
        print("Condition not met. No transition.")

# Example usage
handle_booking_condition()

agent = graph.compile()

# For terminal testing
if __name__ == "__main__":
    print("🗓️ Welcome to the Calendar Booking Assistant! 🤖")
    print("You can book events using natural language, for example:")
    print("- Book a meeting with Alex tomorrow at 3 PM for 1 hour")
    print("- Schedule a team sync next Monday at 10 AM for 30 minutes")
    print("Type 'quit' to exit\n")
    
    while True:
        user_input = input("\nDescribe your event: ")
        if user_input.lower() == 'quit':
            print("Goodbye! 👋")
            break
            
        try:
            result = agent.invoke({
                "user_input": user_input,
                "event_details": {},
                "availability_status": "",
                "confirmation": "",
                "status": "",
                "final_message": "",
                "event_link": "",
                "error_message": ""
            })
            
            # Print final message and event link if available
            print(result["final_message"])
            if result.get("event_link"):
                print(f"View event: {result['event_link']}")
            
            continue_booking = input("\nWould you like to book another event? (yes/no): ")
            if continue_booking.lower() != 'yes':
                print("Goodbye! 👋")
                break
                
        except Exception as e:
            print(f"Error: {str(e)}")
            continue_booking = input("Would you like to try again? (yes/no): ")
            if continue_booking.lower() != 'yes':
                print("Goodbye! 👋")
                break