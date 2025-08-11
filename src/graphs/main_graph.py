from src.graphs.accounting.accounting_graphs import acounting_graph
from src.graphs.insurance.insurance_graphs import insurance_graph
from src.graphs.travel.travel_graph import travel_graph
from src.graphs.wolt_food.wolt_food_graph import wolt_food_graph
from langgraph.graph import StateGraph, MessagesState, END
from typing import Literal
from src.graphs.state.state import RagState

# State cho main graph
class MainState(RagState):
    domain: str  # "accounting" hoặc "insurance"
    context: dict


# Node router logic
def domain_router_node(
    state: MainState, config=None
) -> Literal["accounting", "insurance", "travel"]:

    return state


# Tạo main graph
def create_main_graph(checkpointer):
    builder = StateGraph(MainState)
    builder.add_node("router", domain_router_node)
    builder.add_node("accounting", acounting_graph)
    builder.add_node("insurance", insurance_graph)
    builder.add_node("travel", travel_graph)
    builder.add_node("wolt_food_graph", wolt_food_graph)
    builder.set_entry_point("router")

    def get_domain_from_state(state):
        print(f"get_domain_from_state->state:{state}")
        context = state.get("context")
        print(f"get_domain_from_state->context:{context}")
        
        if context is None:
            print("Context is None, defaulting to 'travel'")
            return "travel"
        
        domain_selected = context.get("domain")
        print(f"get_domain_from_state->context->domain:{domain_selected}")
        
        if domain_selected is None:
            print("Domain is None, defaulting to 'travel'")
            return "travel"
        
        print(f"domain_selected: {domain_selected}")
        return domain_selected

    builder.add_conditional_edges(
        "router",
        get_domain_from_state,
        {
            "accounting": "accounting",
            "travel": "travel",
            "insurance": "insurance",
            "wolt_food_graph": "wolt_food_graph",
        },
    )
    builder.add_edge("accounting", END)
    builder.add_edge("travel", END)
    builder.add_edge("insurance", END)
    builder.add_edge("wolt_food_graph", END)
    _graph_instance = builder.compile(
        name="_agent_",
        checkpointer=checkpointer
        
    )
    return _graph_instance


# Hàm test với chỉ travel_graph
def create_travel_only_graph(checkpointer):
    """
    Tạo main graph với chỉ travel_graph để test streaming
    """
    builder = StateGraph(MainState)
    
    # Router node đơn giản, luôn route tới travel
    def travel_router_node(state: MainState, config=None):
        # Đảm bảo state có context với domain = "travel"
        if not state.get("context"):
            state["context"] = {"domain": "travel"}
        else:
            state["context"]["domain"] = "travel"
        return state
    
    # Add nodes
    builder.add_node("router", travel_router_node)
    builder.add_node("travel", travel_graph)
    
    # Set entry point
    builder.set_entry_point("router")
    
    # Router luôn đi tới travel
    builder.add_edge("router", "travel")
    builder.add_edge("travel", END)
    
    # Compile graph
    _graph_instance = builder.compile(
        name="_travel_only_agent_",
        checkpointer=checkpointer
    )
    return _graph_instance

