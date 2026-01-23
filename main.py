import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from state import MarketeerState
from nodes import scout_node, analyst_node, outreach_node

# Load environment variables
load_dotenv()


def should_proceed(state: MarketeerState) -> str:
    """Conditional edge function: routes to Outreach if PROCEED, otherwise END."""
    decision = state.get("decision")
    if decision == "PROCEED":
        return "outreach"
    return "end"


def main():
    """Initialize and run the Marketeer graph."""
    # Initialize the StateGraph
    workflow = StateGraph(MarketeerState)
    
    # Add nodes
    workflow.add_node("scout", scout_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("outreach", outreach_node)
    
    # Set entry point
    workflow.set_entry_point("scout")
    
    # Add edges
    workflow.add_edge("scout", "analyst")
    
    # Add conditional edge after analyst
    workflow.add_conditional_edges(
        "analyst",
        should_proceed,
        {
            "outreach": "outreach",
            "end": END
        }
    )
    
    # Add edge from outreach to end
    workflow.add_edge("outreach", END)
    
    # Compile the graph
    app = workflow.compile()
    
    return app


if __name__ == "__main__":
    # Example usage
    graph = main()
    
    # Example: Run the graph with a URL
    initial_state = {
        "url": "https://herdwatch.ie/",
        "raw_markdown": None,
        "company_name": None,
        "is_irish_sme": None,
        "tech_stack": [],
        "has_angular_debt": None,
        "grant_eligible": None,
        "decision": None,
        "outreach_draft": None
    }
    
    # Uncomment to run:
    result = graph.invoke(initial_state)
    print(result)
