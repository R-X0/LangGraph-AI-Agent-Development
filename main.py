import yaml
from langgraph.graph import StateGraph
from src.agents.job_scraping_agent import job_scraping_agent
from src.agents.contact_finding_agent import contact_finding_agent

def main():
    with open("config.yaml", "r") as config_file:
        config = yaml.safe_load(config_file)

    # Define the state schema
    class State(dict):
        job_postings: list
        contacts: list

    # Create the graph
    graph = StateGraph(State)

    # Add nodes
    graph.add_node("scrape_jobs", job_scraping_agent(config))
    graph.add_node("find_contacts", contact_finding_agent(config))

    # Add edges
    graph.add_edge("scrape_jobs", "find_contacts")

    # Set entry and exit points
    graph.set_entry_point("scrape_jobs")
    graph.set_finish_point("find_contacts")

    # Compile the graph
    workflow = graph.compile()

    # Run the graph
    result = workflow.invoke({"job_postings": [], "contacts": []})

    print(f"Scraped {len(result['job_postings'])} job postings")
    print(f"Found contact information for {len(result['contacts'])} companies")

if __name__ == "__main__":
    main()