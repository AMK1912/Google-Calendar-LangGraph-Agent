import googleapiclient.discovery
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from typing import TypedDict
from langgraph.graph import StateGraph
from auth import authenticate_google
from dotenv import load_dotenv
from typing import Optional
import os, json, re, pytz
from datetime import datetime, timedelta

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Authenticate and create Google Calendar service
creds = authenticate_google()
service = googleapiclient.discovery.build("calendar", "v3", credentials=creds)

llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=api_key)

class EventDetails(BaseModel):
    title: str
    start_time: str
    end_time: str


class CalendarState(BaseModel):
    user_input: str
    event_details:  Optional[EventDetails] = None
    availability_status: str = ""
    confirmation: str = ""
    status: str = ""
    final_message: str = "" 
    event_link: str = ""     
    error_message: str = ""


    class Config:
        arbitrary_types_allowed = True
                                                                                                          
def extract_event_details(state: CalendarState):
    user_input= state.user_input
    prompt = f """
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
        
        event_details = EventDetails(**details)
        state.event_details = event_details


    except (ValueError, KeyError) as e:
        raise ValueError(f"DateTime validation failed: {str(e)}")


    print(f"Extracted details: {state.event_details}")  
    return state

# Function to check availability
def check_availability(state: CalendarState):
    if not state.event_details:
        raise ValueError("No event details available")
        
    details = state.event_details
    print(f"Checking availability with details: {details}")

    try:
        time_min = f"{details.start_time}Z"
        time_max = f"{details.end_time}Z"
        
        print(f"Checking calendar from {time_min} to {time_max}")
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get("items", [])
        
        new_state = state.model_copy()
        if events:
            new_state.availability_status = f"⚠️ Slot unavailable! You have {len(events)} conflicting event(s)."
        else:
            new_state.availability_status = "✅ Slot available."
            
    except Exception as e:
        print(f"Error checking availability: {str(e)}")
        new_state = state.model_copy()
        new_state.availability_status = f"Error checking availability: {str(e)}"
    
    return new_state



def end_task(state: CalendarState):

    new_state = state.model_copy()

    if new_state.status == "completed":
        if not new_state.final_message:
            new_state.final_message = "✅ Event successfully booked and added to your calendar!"
    elif new_state.status == "cancelled":
        new_state.final_message = "❌ Booking cancelled by user."
    elif new_state.status == "error":
        if not new_state.final_message:
            new_state.final_message = f"⚠️ Error occurred: {new_state.get('error_message', 'Unknown error')}"
    
    return new_state

def confirm_booking(state: CalendarState):
    if not state.event_details:
        raise ValueError("No event details available")
        
    details = state.event_details
    print(f"Confirming booking with details: {details}")
    
    # Add this line to force confirmation for testing
    new_state = state.model_copy()
    new_state.confirmation = "confirm"


    if new_state.confirmation == "confirm":
        try:
            event = {
                "summary": details.title,
                "start": {"dateTime": details.start_time, "timeZone": "UTC"},  
                "end": {"dateTime": details.end_time, "timeZone": "UTC"},      
            }
            
            print(f"Attempting to book event: {event}")  
            
            event_result = service.events().insert(calendarId="primary", body=event).execute()
            
            print(f"Booking result: {event_result}") 
            
            new_state.event_link = event_result.get('htmlLink', '')
            new_state.status = "completed"
            new_state.final_message = f"✅ Event successfully booked and added to your calendar!\nView event: {new_state.event_link}"
            
        except Exception as e:
            print(f"Booking error: {str(e)}")  # Debug print
            new_state.status = "error"
            new_state.error_message = str(e)
            new_state.final_message = f"⚠️ Error booking event: {str(e)}"
    else:
        new_state.status = "pending_confirmation"
    
    return new_state

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
            initial_state = CalendarState(
                user_input= user_input,
                event_details= None,
                availability_status= "",
                confirmation= "",
                status= "",
                final_message= "",
                event_link= "",
                error_message= ""
            )

            result = agent.invoke(initial_state.model_dump())
            

            final_state = CalendarState(**result)
            
            print(final_state.final_message)
            if final_state.event_link:
                print(f"View event: {final_state.event_link}")
            
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
