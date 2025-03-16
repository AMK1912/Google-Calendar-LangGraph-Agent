# Google-Calendar-LangGraph-Agent

# AI Calendar Assistant 🤖 

An intelligent calendar management system that uses natural language processing to schedule events seamlessly with Google Calendar.

## 🌟 Features

- **Natural Language Processing**: Simply describe your event in plain English
- **Smart Time Parsing**: Automatically handles relative dates (tomorrow, next week, etc.)
- **Availability Checking**: Automatically checks for scheduling conflicts
- **Google Calendar Integration**: Directly creates and manages events in your calendar
- **Error Handling**: Robust validation and error management
- **Real-time Feedback**: Immediate confirmation and calendar links

## 🛠️ Tech Stack

- **Python**: Core programming language
- **LangGraph**: For workflow orchestration
- **LangChain**: For LLM interactions
- **OpenAI GPT-4**: Natural language processing
- **Google Calendar API**: Calendar integration
- **Pydantic**: Data validation and settings management
- **python-dotenv**: Environment variable management

## 📋 Prerequisites

- Python 3.8+
- Google Calendar API credentials
- OpenAI API key
- Google OAuth 2.0 credentials

## 🚀 Installation

1. Clone the repository:
   git clone https://github.com/yourusername/ai-calendar-assistant.git
   cd ai-calendar-assistant

2. Install dependencies:
   pip install -r requirements.txt


3. Set up environment variables:
   create a .env file in project folder
   .env
   OPENAI_API_KEY=your_openai_api_key
   GOOGLE_APPLICATION_CREDENTIALS=path_to_your_credentials.json


## 💻 Usage

1. Run the assistant:
   python calendar_agent.py

   
2. Enter your event details in natural language:
   Example inputs:

   "Schedule a team meeting tomorrow at 3 PM for 1 hour"
   "Book a dentist appointment next Tuesday at 2 PM"
   "Set up a project review on Friday morning for 2 hours"

   
