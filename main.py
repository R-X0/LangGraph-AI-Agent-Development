# main.py

import yaml
from langgraph.graph import StateGraph
from src.agents.job_scraping_agent import job_scraping_agent
from src.agents.contact_finding_agent import contact_finding_agent
from src.agents.email_outreach_agent import email_outreach_agent
from src.utils.graph_db import GraphDB
import os
from dotenv import load_dotenv

load_dotenv()

def main():
    with open("config.yaml", "r") as config_file:
        config = yaml.safe_load(config_file)

    os.environ['HUNTER_API_KEY'] = config['hunter_io']['api_key']
    os.environ['ANTHROPIC_API_KEY'] = config['anthropic']['api_key']
    os.environ['APOLLO_API_KEY'] = config['apollo_io']['api_key']

    class State(dict):
        job_postings: list
        contacts: list
        prepared_emails: list

    graph = StateGraph(State)

    graph.add_node("scrape_jobs", job_scraping_agent(config))
    graph.add_node("find_contacts", contact_finding_agent(config))
    graph.add_node("prepare_emails", email_outreach_agent(config))

    graph.add_edge("scrape_jobs", "find_contacts")
    graph.add_edge("find_contacts", "prepare_emails")

    graph.set_entry_point("scrape_jobs")
    graph.set_finish_point("prepare_emails")

    workflow = graph.compile()

    try:
        print("Starting workflow...")
        initial_state = {"job_postings": [], "contacts": [], "prepared_emails": []}
        result = workflow.invoke(initial_state)
        
        print("\nWorkflow completed.")
        print(f"Scraped {len(result['job_postings'])} job postings")
        
        if 'contacts' in result:
            print(f"Found contact information for {len(result['contacts'])} companies")
            valid_emails = sum(1 for contact in result['contacts'] if contact['contact_info']['email'] is not None)
            print(f"Valid email addresses found: {valid_emails}")
        else:
            print("No contact information found. Contact finding step may have failed.")
        
        if 'prepared_emails' in result:
            print(f"Prepared {len(result['prepared_emails'])} email templates")
        else:
            print("No email templates prepared. Email preparation step may have failed.")

        print("\nStoring results in Neo4j...")
        db = GraphDB(config['neo4j']['uri'], config['neo4j']['user'], config['neo4j']['password'])
        
        for job in result['job_postings']:
            db.create_job_posting(job)
        
        for contact in result.get('contacts', []):
            if contact['contact_info']['email'] is not None:
                db.create_company_contact(contact['company_name'], contact['contact_info'])
        
        print("Results stored in Neo4j")

        print("\nDisplaying stored data:")
        db.display_stored_data()

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()