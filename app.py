import streamlit as st
from calendar_agent import agent, CalendarState
from datetime import datetime

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "booking_complete" not in st.session_state:
        st.session_state.booking_complete = False

def reset_booking():
    st.session_state.booking_complete = False
    st.session_state.messages = []

def main():
    st.title("🗓️ Calendar Booking Assistant")
    
    initialize_session_state()
    
    # Add sidebar with examples
    with st.sidebar:
        st.header("Example Inputs")
        st.write("Try these example formats:")
        st.write("- Book a meeting with Alex tomorrow at 3 PM for 1 hour")
        st.write("- Schedule a team sync next Monday at 10 AM for 30 minutes")
        
        if st.button("Start New Booking", type="primary"):
            reset_booking()

    # Main booking interface
    if not st.session_state.booking_complete:
        user_input = st.text_input(
            "Describe your event",
            placeholder="e.g., Book a meeting with Alex tomorrow at 3 PM for 1 hour",
            key="user_input"
        )
        
        if st.button("Book Event", type="primary"):
            if user_input:
                with st.spinner("Processing your request..."):
                    try:
                        initial_state = {
                            "user_input": user_input,
                            "event_details": {},
                            "availability_status": "",
                            "confirmation": "",
                            "status": "",
                            "final_message": "",
                            "event_link": "",
                            "error_message": ""
                        }
                        
                        # Get event details and availability
                        result = agent.invoke(initial_state)

                        # Display availability status
                        st.info(result["availability_status"])
                        
                        # If slot is available, show confirmation
                        if "unavailable" not in result["availability_status"].lower():
                            event_details = result["event_details"]
                            st.write("### Event Details")
                            st.write(f"**Title:** {event_details['title']}")
                            st.write(f"**Start:** {event_details['start_time']}")
                            st.write(f"**End:** {event_details['end_time']}")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("Confirm Booking", type="primary", key="confirm"):
                                    with st.spinner("Booking your event..."):
                                        # Create new state for confirmation
                                        confirm_state = result.copy()
                                        confirm_state["confirmation"] = "confirm"
                                        
                                        # Process the booking
                                        final_result = agent.invoke(confirm_state)
                                        
                                        if final_result["status"] == "completed":
                                            st.success(final_result["final_message"])
                                            if final_result.get("event_link"):
                                                st.markdown(f"[View in Calendar]({final_result['event_link']})")
                                                st.session_state.messages.append(
                                                    f"Event booked: {event_details['title']} at {event_details['start_time']}"
                                                )
                                        else:
                                            st.error(final_result.get("error_message", "Failed to book event"))
                                        
                                        st.session_state.booking_complete = True
                            
                            with col2:
                                if st.button("Cancel", type="secondary", key="cancel"):
                                    st.warning("Booking cancelled")
                                    st.session_state.booking_complete = True
                        
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
            else:
                st.warning("Please enter event details")

    
    # Show booking history
    if st.session_state.messages:
        st.write("### Booking History")
        for message in st.session_state.messages:
            st.write(message)

if __name__ == "__main__":
    main()