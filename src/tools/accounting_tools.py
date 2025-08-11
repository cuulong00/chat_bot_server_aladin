from langchain_core.tools import tool

@tool
def get_accounting_document(query: str) -> str:
    """
    Retrieves an accounting document based on a query.
    """
    # In a real implementation, this would query a database or a document store.
    return f"Accounting document for query: {query}"

accounting_tools = [get_accounting_document]
