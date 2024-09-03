# main.py

import yaml
from langgraph.graph import StateGraph
from src.agents.job_scraping_agent import job_scraping_agent
from src.agents.contact_finding_agent import contact_finding_agent
from src.agents.matching_and_email_agent import matching_and_email_agent
from src.agents.email_outreach_agent import email_outreach_agent
from src.linkedinSalesNavigator import LinkedInSalesNavigator
from src.utils.utils import save_data_into_json
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
import logging
import json
import asyncio

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_cookies(cookies):
    for cookie in cookies:
        if 'expiry' in cookie:
            cookie['expires'] = cookie.pop('expiry')
        
        if 'sameSite' not in cookie or cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
            cookie['sameSite'] = 'Lax'
        
        allowed_fields = ['name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure', 'sameSite']
        for key in list(cookie.keys()):
            if key not in allowed_fields:
                del cookie[key]
    
    return cookies

async def run_linkedin_sales_navigator(configs, processed_cookies):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        # Add the processed cookies to the context
        await context.add_cookies(processed_cookies)
        
        page = await context.new_page()

        # Create LinkedInSalesNavigator instance
        linkedin_sales = LinkedInSalesNavigator(configs, page)

        # Login and perform actions
        await linkedin_sales.login()
        await linkedin_sales.set_filters()
        prospects = await linkedin_sales.search_whole_pages()

        # Save prospects data
        save_data_into_json("prospects", prospects)
        logger.info(f"LinkedIn prospects saved into prospects.json. Total prospects: {len(prospects)}")

        logger.info("Ending LinkedIn Sales Automation")

        # Keep the browser open until user input
        input("Press Enter to close the browser...")

        await browser.close()

    return prospects

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
            prospects: list
            matched_data: list
            prepared_emails: list

        graph = StateGraph(State)

        graph.add_node("scrape_jobs", job_scraping_agent(configs))
        graph.add_node("find_contacts", contact_finding_agent(configs))

        graph.add_edge("scrape_jobs", "find_contacts")

        graph.set_entry_point("scrape_jobs")
        graph.set_finish_point("find_contacts")

        workflow = graph.compile()

        logger.info("Starting workflow...")
        initial_state = {"job_postings": [], "contacts": [], "prospects": [], "matched_data": [], "prepared_emails": []}
        result = await workflow.ainvoke(initial_state)
        
        logger.info("Workflow completed.")
        logger.info(f"Scraped {len(result['job_postings'])} job postings")
        logger.info(f"Found contact information for {len(result['contacts'])} companies")

        # LinkedIn Sales Navigator process
        logger.info("Starting LinkedIn Sales Navigator process...")

        # Load cookies
        with open('cookies.json', 'r') as f:
            cookies = json.load(f)
        
        # Process the cookies
        processed_cookies = process_cookies(cookies)

        prospects = await run_linkedin_sales_navigator(configs, processed_cookies)

        # Update the state with the prospects
        result['prospects'] = prospects

        # Run matching and email preparation
        match_result = await matching_and_email_agent(configs)(result)
        result['matched_data'] = match_result['matched_data']
        
        email_result = await email_outreach_agent(configs)(result)
        result['prepared_emails'] = email_result['prepared_emails']

        logger.info(f"Matched {len(result['matched_data'])} job-prospect pairs")
        logger.info(f"Prepared {len(result['prepared_emails'])} emails for sending")

        logger.info("Workflow completed successfully.")

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())