from src.graphs.marketing.marketing_graph import marketing_graph

# For backward compatibility, expose a factory that now just returns the single marketing graph.
def create_main_graph(checkpointer):
    # marketing_graph already compiled with its own checkpointer inside; if strict reuse needed,
    # could add recompile logic here. Return as-is.
    return marketing_graph

# Legacy helper retained (no-op) to avoid import errors elsewhere
def create_travel_only_graph(checkpointer):
    return marketing_graph

