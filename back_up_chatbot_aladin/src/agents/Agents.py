from langchain_anthropic import ChatAnthropic
from langchain_tavily import TavilySearch
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from datetime import datetime
from src.tools import car_tools, hotel_tools, excursion_tools, flight_tools
from src.tools.memory_tools import save_user_preference, get_user_profile
from src.database.qdrant_store import search_company_policies, search_user_preferences
from langchain_openai import ChatOpenAI
from src.graphs.state.state  import State

from langchain.chat_models import init_chat_model
from langgraph.store.base import BaseStore
import uuid
import logging
from langchain_anthropic import ChatAnthropic

from langchain_tavily import TavilySearch
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig

from pydantic import BaseModel, Field

from langchain_groq import ChatGroq
model_deep_seek = ChatGroq(model="deepseek-r1-distill-llama-70b", temperature=0.5)
qwen = ChatGroq(model="qwen-qwq-32b", temperature=0.5)

gpt = ChatOpenAI(model="gpt-4o-mini", streaming=True, temperature=0.1)

gemini = init_chat_model("google_genai:gemini-2.0-flash-lite")
llm = gpt

# --- Utility Functions for Stream Writer (shared) ---
def emit_reasoning_step(node_name: str, summary: str, status: str = "processing", details: dict = None, context_question: str = ""):
    """
    Utility function to emit reasoning steps using LangGraph's custom stream writer.
    Shared across all assistant functions for consistent reasoning step emission.
    
    Args:
        node_name: Name of the node/assistant (e.g., 'primary_assistant', etc.)
        summary: Human-readable summary of what the assistant is doing
        status: 'processing' or 'completed' 
        details: Optional dictionary with additional details
        context_question: User question for context (will be truncated if too long)
    
    Returns:
        bool: True if successfully emitted, False otherwise
    """
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
        if writer:
            # Truncate context question for better UX
            truncated_question = context_question[:50] + '...' if len(context_question) > 50 else context_question
            
            writer({
                "reasoning_step": {
                    "node": node_name,
                    "summary": summary,
                    "status": status,
                    "details": details or {},
                    "context_question": truncated_question
                }
            })
            return True
        else:
            logging.warning(f"Stream writer not available for node: {node_name}")
            return False
    except Exception as e:
        # Log error but don't break the flow
        logging.error(f"Stream writer error in {node_name}: {e}")
        return False


def create_reasoning_step_legacy(node_name: str, summary: str, details: dict = None):
    """
    Create reasoning step in legacy format for backward compatibility.
    This is used in the return statements to maintain existing functionality.
    
    Args:
        node_name: Name of the node
        summary: Summary description  
        details: Optional details dictionary
        
    Returns:
        dict: Reasoning step in legacy format
    """
    return {
        "node": node_name,
        "summary": summary,
        "details": details or {}
    }


class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def binding_prompt(self, state: State):
        prompt = {
            **state,
            "user_info": state["user"]["user_info"],
            "user_profile": state["user"]["user_profile"],
        }
        return prompt

    def __call__(self, state: State, config: RunnableConfig):
        # Check if this is a cancel action first
        if "cancel_action" in state:
            cancel_signal = state["cancel_action"]
            print(f"🔧 Assistant received cancel signal: {cancel_signal}")
            
            # Create a cancellation response message
            cancelled_tools = cancel_signal.get("cancelled_tools", [])
            tools_text = ", ".join(cancelled_tools) if cancelled_tools else "operation"
            
            cancel_response = f"I understand you've cancelled the {tools_text}. No action has been taken. Is there anything else I can help you with?"
            
            # Emit reasoning step for cancellation
            emit_reasoning_step(
                node_name="primary_assistant",
                summary="🚫 User cancelled operation - providing cancellation confirmation",
                status="completed",
                details={
                    "action": "cancellation_response",
                    "cancelled_tools": cancelled_tools,
                    "reason": cancel_signal.get("reason", "User cancelled")
                }
            )
            
            # Return cancellation message
            from langchain_core.messages import AIMessage
            return AIMessage(content=cancel_response)
        
        # Determine assistant type from dialog_state or config
        assistant_name = "primary_assistant"  # default
        dialog_state = state.get("dialog_state", [])
        if dialog_state:
            current_skill = dialog_state[-1]
            assistant_mapping = {
                "flight_assistant": "flight_assistant",
                "book_car_rental": "car_rental_assistant", 
                "book_hotel": "hotel_assistant",
                "book_excursion": "excursion_assistant"
            }
            assistant_name = assistant_mapping.get(current_skill, current_skill)
        
        # Get current question for context
        question = ""
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content'):
                if isinstance(last_message.content, str):
                    question = last_message.content
                elif isinstance(last_message.content, list):
                    question = " ".join([
                        item.get("text", "") for item in last_message.content
                        if isinstance(item, dict) and "text" in item
                    ])
        
        # Assistant name to emoji mapping
        emoji_mapping = {
            "primary_assistant": "🤖",
            "flight_assistant": "✈️",
            "car_rental_assistant": "🚗",
            "hotel_assistant": "🏨", 
            "excursion_assistant": "🗺️"
        }
        emoji = emoji_mapping.get(assistant_name, "🤖")
        
        # Emit processing step
        emit_reasoning_step(
            node_name=assistant_name,
            summary=f"{emoji} {assistant_name.replace('_', ' ').title()} processing user request",
            status="processing",
            details={"action": "llm_generation", "assistant_type": assistant_name},
            context_question=question
        )
        
        while True:
            config["configurable"]["user_id"] = state["user"]["user_info"]["user_id"]
            print(f"config:{config}")
            result = self.runnable.invoke(self.binding_prompt(state), config)

            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        
        # Determine response type for reasoning step
        if result.tool_calls:
            tool_names = [tc.get("name", "unknown") for tc in result.tool_calls]
            summary = f"{emoji} {assistant_name.replace('_', ' ').title()} calling tools: {', '.join(tool_names)}"
            details = {"action": "tool_calls", "tools": tool_names, "assistant_type": assistant_name}
        else:
            summary = f"{emoji} {assistant_name.replace('_', ' ').title()} providing direct response"
            details = {"action": "direct_response", "assistant_type": assistant_name}
        
        # Emit completion step
        emit_reasoning_step(
            node_name=assistant_name,
            summary=summary,
            status="completed",
            details=details,
            context_question=question
        )
        
        # Create reasoning step for state update (EXACTLY like adaptive_rag_graph)
        reasoning_step = create_reasoning_step_legacy(
            node_name=assistant_name,
            summary=summary,
            details=details
        )
        
        # Return with reasoning_steps like adaptive_rag_graph does
        return {"messages": result, "reasoning_steps": [reasoning_step]}


class CompleteOrEscalate(BaseModel):
    """A tool to mark the current task as completed and/or to escalate control of the dialog to the main assistant,
    who can re-route the dialog based on the user's needs."""

    cancel: bool = True
    reason: str

    class Config:
        json_schema_extra = {
            "example": {
                "cancel": True,
                "reason": "User changed their mind about the current task.",
            },
            "example 2": {
                "cancel": True,
                "reason": "I have fully completed the task.",
            },
            "example 3": {
                "cancel": False,
                "reason": "I need to search the user's emails or calendar for more information.",
            },
        }


# Flight booking assistant

flight_booking_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Always answer in the same language as the user's question. If the user asks in Vietnamese, answer in Vietnamese. If the user asks in English, answer in English.\n"
            "You are a specialized assistant for handling flight searches, bookings, and updates. "
            "The primary assistant delegates work to you whenever the user needs help with flights. "
            "Your primary job is to use the provided tools to find and book flights, or update existing bookings. "
            "When a user requests to book a flight, always use the information provided by the user to fetch the detailed flight information first. Present these flight details to the user before proceeding. When calling the booking tool, always include the full flight details in the confirmation message so the user can review all information before confirming the booking. After a booking is successfully completed, always present the ticket information to the user as a data table with clear columns for each field (for example: ticket number, passenger name, flight number, departure, arrival, seat, price, etc). "
            "When using a search tool, if the result is a list of results, always present the results as a data table with clear columns for each field (for example: flight number, departure, arrival, price, etc). "
            "When searching, be persistent. Expand your query bounds if the first search returns no results. "
            "If you need more information or the customer changes their mind, escalate the task back to the main assistant."
            " Remember that a booking isn't completed until after the relevant tool has successfully been used."
            "\n\nCurrent user flight information:\n<Flights>\n{user_info}\n</Flights>"
            "\n\nUser personalized profile:\n<UserProfile>\n{user_profile}\n</UserProfile>"
            "\nCurrent time: {time}."
            "\n\nIf the user needs help, and none of your tools are appropriate for it, then"
            ' "CompleteOrEscalate" the dialog to the host assistant. Do not waste the user\'s time. Do not make up invalid tools or functions.',
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

flight_assistant_safe_tools = [
    flight_tools.search_flights,
    flight_tools.list_available_flights,
]
flight_assistant_sensitive_tools = [
    flight_tools.update_ticket_to_new_flight,
    flight_tools.book_ticket,
    flight_tools.cancel_ticket,
]
flight_assistant_tools = flight_assistant_safe_tools + flight_assistant_sensitive_tools
flight_assistant_runnable = flight_booking_prompt | llm.bind_tools(
    flight_assistant_tools + [CompleteOrEscalate]
)

book_hotel_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Always answer in the same language as the user's question. If the user asks in Vietnamese, answer in Vietnamese. If the user asks in English, answer in English.\n"
            "You are a specialized assistant for handling hotel bookings. "
            "When you receive a hotel booking request, your first action must be to call the search_hotels tool to find available hotels that match the user's criteria. "
            "After retrieving the list, present the available hotels to the user and ask them to select one. "
            "If the result of a search tool is a list of hotels, always present the results as a data table with clear columns for each field (for example: hotel name, location, price, rating, etc). "
            "Once the user has selected a hotel, proceed to book the hotel using the book_hotel tool. "
            "If no suitable hotel is found, inform the user. "
            "If any required information is missing, ask the user for clarification. "
            "When searching, be persistent. Expand your query bounds if the first search returns no results. "
            "If you need more information or the customer changes their mind, escalate the task back to the main assistant. "
            "Remember, a booking is only complete after you have successfully invoked the book_hotel tool. "
            "\n\nUser personalized profile:\n<UserProfile>\n{user_profile}\n</UserProfile>"
            "\nCurrent time: {time}."
            '\n\nIf the user needs help, and none of your tools are appropriate for it, then "CompleteOrEscalate" the dialog to the host assistant. '
            "Do not waste the user's time. Do not make up invalid tools or functions."
            "\n\nSome examples for which you should CompleteOrEscalate:\n"
            " - 'what's the weather like this time of year?'\n"
            " - 'nevermind i think I'll book separately'\n"
            " - 'i need to figure out transportation while i'm there'\n"
            " - 'Oh wait i haven't booked my flight yet i'll do that first'\n"
            " - 'Hotel booking confirmed'",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

book_hotel_safe_tools = [hotel_tools.search_hotels]
book_hotel_sensitive_tools = [
    hotel_tools.book_hotel,
    hotel_tools.update_hotel,
    hotel_tools.cancel_hotel,
]
book_hotel_tools = book_hotel_safe_tools + book_hotel_sensitive_tools
book_hotel_runnable = book_hotel_prompt | llm.bind_tools(
    book_hotel_tools + [CompleteOrEscalate]
)

# Car Rental Assistant
book_car_rental_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Always answer in the same language as the user's question. If the user asks in Vietnamese, answer in Vietnamese. If the user asks in English, answer in English.\n"
            "You are a specialized assistant for handling car rental bookings. "
            "The primary assistant delegates work to you whenever the user needs help booking a car rental. "
            "Search for available car rentals based on the user's preferences and confirm the booking details with the customer. "
            "If the result of a search tool is a list of car rentals, always present the results as a data table with clear columns for each field (for example: car type, company, price, location, etc). "
            " When searching, be persistent. Expand your query bounds if the first search returns no results. "
            "If you need more information or the customer changes their mind, escalate the task back to the main assistant."
            " Remember that a booking isn't completed until after the relevant tool has successfully been used."
            "\n\nUser personalized profile:\n<UserProfile>\n{user_profile}\n</UserProfile>"
            "\nCurrent time: {time}."
            "\n\nIf the user needs help, and none of your tools are appropriate for it, then "
            '"CompleteOrEscalate" the dialog to the host assistant. Do not waste the user\'s time. Do not make up invalid tools or functions.'
            "\n\nSome examples for which you should CompleteOrEscalate:\n"
            " - 'what's the weather like this time of year?'\n"
            " - 'What flights are available?'\n"
            " - 'nevermind i think I'll book separately'\n"
            " - 'Oh wait i haven't booked my flight yet i'll do that first'\n"
            " - 'Car rental booking confirmed'",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

book_car_rental_safe_tools = [car_tools.search_car_rentals]
book_car_rental_sensitive_tools = [
    car_tools.book_car_rental,
    car_tools.update_car_rental,
    car_tools.cancel_car_rental,
]
book_car_rental_tools = book_car_rental_safe_tools + book_car_rental_sensitive_tools
book_car_rental_runnable = book_car_rental_prompt | llm.bind_tools(
    book_car_rental_tools + [CompleteOrEscalate]
)

# Excursion Assistant

book_excursion_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Always answer in the same language as the user's question. If the user asks in Vietnamese, answer in Vietnamese. If the user asks in English, answer in English.\n"
            "You are a specialized assistant for handling trip recommendations. "
            "The primary assistant delegates work to you whenever the user needs help booking a recommended trip. "
            "Search for available trip recommendations based on the user's preferences and confirm the booking details with the customer. "
            "If the result of a search tool is a list of trip recommendations, always present the results as a data table with clear columns for each field (for example: trip name, location, price, highlights, etc). "
            "If you need more information or the customer changes their mind, escalate the task back to the main assistant."
            " When searching, be persistent. Expand your query bounds if the first search returns no results. "
            " Remember that a booking isn't completed until after the relevant tool has successfully been used."
            "\n\nUser personalized profile:\n<UserProfile>\n{user_profile}\n</UserProfile>"
            "\nCurrent time: {time}."
            '\n\nIf the user needs help, and none of your tools are appropriate for it, then "CompleteOrEscalate" the dialog to the host assistant. Do not waste the user\'s time. Do not make up invalid tools or functions.'
            "\n\nSome examples for which you should CompleteOrEscalate:\n"
            " - 'nevermind i think I'll book separately'\n"
            " - 'i need to figure out transportation while i'm there'\n"
            " - 'Oh wait i haven't booked my flight yet i'll do that first'\n"
            " - 'Excursion booking confirmed!'",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

book_excursion_safe_tools = [excursion_tools.search_trip_recommendations]
book_excursion_sensitive_tools = [
    excursion_tools.book_excursion,
    excursion_tools.update_excursion,
    excursion_tools.cancel_excursion,
]
book_excursion_tools = book_excursion_safe_tools + book_excursion_sensitive_tools
book_excursion_runnable = book_excursion_prompt | llm.bind_tools(
    book_excursion_tools + [CompleteOrEscalate]
)


# Primary Assistant
class ToFlightBookingAssistant(BaseModel):
    """Transfers work to a specialized assistant to handle flight searches, bookings, updates, and cancellations."""

    request: str = Field(
        description="The user's request, which will be forwarded to the flight assistant."
    )


class ToBookCarRental(BaseModel):
    """Transfers work to a specialized assistant to handle car rental bookings."""

    location: str = Field(
        description="The location where the user wants to rent a car."
    )
    start_date: str = Field(description="The start date of the car rental.")
    end_date: str = Field(description="The end date of the car rental.")
    request: str = Field(
        description="Any additional information or requests from the user regarding the car rental."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "location": "Basel",
                "start_date": "2023-07-01",
                "end_date": "2023-07-05",
                "request": "I need a compact car with automatic transmission.",
            }
        }


class ToHotelBookingAssistant(BaseModel):
    """Transfer work to a specialized assistant to handle hotel bookings."""

    location: str = Field(
        description="The location where the user wants to book a hotel."
    )
    checkin_date: str = Field(description="The check-in date for the hotel.")
    checkout_date: str = Field(description="The check-out date for the hotel.")
    request: str = Field(
        description="Any additional information or requests from the user regarding the hotel booking."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "location": "Zurich",
                "checkin_date": "2023-08-15",
                "checkout_date": "2023-08-20",
                "request": "I prefer a hotel near the city center with a room that has a view.",
            }
        }


class ToBookExcursion(BaseModel):
    """Transfers work to a specialized assistant to handle trip recommendation and other excursion bookings."""

    location: str = Field(
        description="The location where the user wants to book a recommended trip."
    )
    request: str = Field(
        description="Any additional information or requests from the user regarding the trip recommendation."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "location": "Lucerne",
                "request": "The user is interested in outdoor activities and scenic views.",
            }
        }


# The top-level assistant performs general Q&A and delegates specialized tasks to other assistants.
# The task delegation is a simple form of semantic routing / does simple intent detection
# llm = ChatAnthropic(model="claude-3-haiku-20240307")
# llm = ChatAnthropic(model="claude-3-sonnet-20240229", temperature=1)

primary_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Always answer in the same language as the user's question. If the user asks in Vietnamese, answer in Vietnamese. If the user asks in English, answer in English.\n"
            "You are a smart travel assistant.\n"
            "Your primary role is to search for flight information and company policies to answer customer queries.\n"
            "If you use a search tool and the result is a list of results, always present the results as a data table with clear columns for each field (for example: flight number, departure, arrival, price, etc).\n"
            "If a customer requests to search, book, update, or cancel a hotel, car rental, flight ticket, or excursion/trip recommendation, "
            "or asks for a list of available flights, "
            "always delegate the task to the appropriate specialized assistant by invoking the corresponding tool: \n"
            "- For hotel-related requests, call ToHotelBookingAssistant.\n"
            "- For car rental-related requests, call ToBookCarRental.\n"
            "- For flight ticket-related requests, including listing available flights, call ToFlightBookingAssistant.\n"
            "- For excursion/trip recommendation-related requests, call ToBookExcursion.\n"
            "You are not able to make these types of changes yourself. Only the specialized assistants are given permission to do this for the user. "
            "The user is not aware of the different specialized assistants, so do not mention them; just quietly delegate through function calls.\n"
            "Provide detailed information to the customer, and always double-check the database before concluding that information is unavailable.\n"
            "When searching, be persistent. Expand your query bounds if the first search returns no results. If a search comes up empty, expand your search before giving up.\n"
            "\nIMPORTANT: Use the save_user_preference tool whenever you learn new information about the user's preferences, habits, or personal details that could help personalize future interactions. "
            "Examples: dietary restrictions, preferred seat types, travel companions, budget preferences, favorite destinations, etc.\n"
            "If the user asks about their preferences, habits, or personal profile (e.g., 'What do I like?', 'What is my profile?', 'What are my preferences?'), "
            "you MUST call the get_user_profile tool to retrieve the latest information from the vector database. Do not guess or answer from short-term memory.\n"
            "If you have just saved new preference information, confirm that it has been saved and instruct the user to ask again if they want to see their personalized profile.\n"
            "Only answer about user preferences or profile after you have called get_user_profile and received the result.\n"
            "\nCurrent user flight information:\n<Flights>\n{user_info}\n</Flights>"
            "\nUser personalized profile:\n<UserProfile>\n{user_profile}\n</UserProfile>"
            "\nCurrent time: {time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

primary_assistant_tools = [
    TavilySearch(max_results=1),
    search_company_policies,
    search_user_preferences,
    save_user_preference,  # Thêm tool lưu thông tin người dùng
    get_user_profile,
]
assistant_runnable = primary_assistant_prompt | llm.bind_tools(
    primary_assistant_tools
    + [
        ToFlightBookingAssistant,
        ToBookCarRental,
        ToHotelBookingAssistant,
        ToBookExcursion,
    ]
)
