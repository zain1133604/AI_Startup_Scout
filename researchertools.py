from tavily import TavilyClient
from dotenv import load_dotenv
import os

load_dotenv()

def web_search_tool(query: str):
    """
    Searches the internet for startup info, competitors, and market size.
    Args:
        query: The search string to look up on Google.
    """
    TAVILY_KEY = os.environ.get("TAVILY_KEY")
    tavily = TavilyClient(api_key=TAVILY_KEY)
    
    print(f"🛰️  Researcher Tool -> Searching for: {query}")
    response = tavily.search(query=query, search_depth="advanced", max_results=5, include_answer=True)
    
    context = ""
    for result in response['results']:
        context += f"\nTitle: {result['title']}\nContent: {result['content']}\nURL: {result['url']}\n"
    
    return context




def hiring_pulse_tool(company_name: str):
    """
    Checks job boards (LinkedIn, Wellfound, Indeed) to see how many 
    open roles a company has. High role count = growth signal.
    """
    TAVILY_KEY = os.environ.get("TAVILY_KEY")
    tavily = TavilyClient(api_key=TAVILY_KEY)
    
    # We force the search to look at job boards only
    query = f"site:linkedin.com/jobs/ OR site:wellfound.com '{company_name}' open roles hiring"
    
    print(f"🕵️  Checking Hiring Pulse for: {company_name}")
    response = tavily.search(query=query, search_depth="advanced", max_results=3)
    
    context = f"Hiring Data for {company_name}:\n"
    for result in response['results']:
        context += f"- Source: {result['url']}\n  Snippet: {result['content']}\n"
    
    return context
