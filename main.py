import yaml
from langgraph.graph import StateGraph
from src.agents.job_scraping_agent import job_scraping_agent
from src.agents.contact_finding_agent import contact_finding_agent
from src.utils.graph_db import GraphDB
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    # Load configuration
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
    try:
        print("Starting workflow...")
        initial_state = {"job_postings": [], "contacts": []}
        result = workflow.invoke(initial_state)
        
        print(f"Workflow completed.")
        print(f"Scraped {len(result['job_postings'])} job postings")
        print(f"Found contact information for {len(result['contacts'])} companies")

        # Store results in Neo4j
        print("Storing results in Neo4j...")
        db = GraphDB(config['neo4j']['uri'], config['neo4j']['user'], config['neo4j']['password'])
        
        for job in result['job_postings']:
            db.create_job_posting(job)
        
        for contact in result['contacts']:
            db.create_company_contact(contact['company_name'], contact['contact_info'])
        
        print("Results stored in Neo4j")

        # Display stored data
        print("\nDisplaying stored data:")
        db.display_stored_data()

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()