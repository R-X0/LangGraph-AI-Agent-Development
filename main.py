# main.py

import yaml
import os
from langgraph.graph import StateGraph
from src.agents.job_scraping_agent import job_scraping_agent
from src.agents.contact_finding_agent import contact_finding_agent
from src.agents.email_outreach_agent import email_outreach_agent
from dotenv import load_dotenv
import logging
import asyncio

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    try:
        with open("configs.yaml", "r") as config_file:
            configs = yaml.safe_load(config_file)

        os.environ['HUNTER_API_KEY'] = configs['hunter_io']['api_key']
        os.environ['ANTHROPIC_API_KEY'] = configs['anthropic']['api_key']
        os.environ['APOLLO_API_KEY'] = configs['apollo_io']['api_key']

        class State(dict):
            job_postings: list
            contacts: list
            prepared_emails: list

        graph = StateGraph(State)

        graph.add_node("scrape_jobs", job_scraping_agent(configs))
        graph.add_node("find_contacts", contact_finding_agent(configs))
        graph.add_node("prepare_emails", email_outreach_agent(configs))

        graph.add_edge("scrape_jobs", "find_contacts")
        graph.add_edge("find_contacts", "prepare_emails")

        graph.set_entry_point("scrape_jobs")
        graph.set_finish_point("prepare_emails")

        workflow = graph.compile()

        logger.info("Starting workflow...")
        initial_state = {"job_postings": [], "contacts": [], "prepared_emails": []}
        result = await workflow.ainvoke(initial_state)
        
        logger.info("Workflow completed.")
        logger.info(f"Scraped {len(result['job_postings'])} job postings")
        logger.info(f"Found contact information for {len(result['contacts'])} companies")
        logger.info(f"Prepared {len(result['prepared_emails'])} personalized emails")

        logger.info("\n" + "="*50 + "\nPrepared Emails:\n" + "="*50)
        for i, email in enumerate(result['prepared_emails'], 1):
            logger.info(f"\nEmail {i}:")
            logger.info(f"To: {email['to_email']}")
            logger.info(f"Subject: {email['subject']}")
            logger.info(f"Content:\n{email['content']}")
            logger.info("-" * 50)

        logger.info("Workflow completed successfully.")

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())