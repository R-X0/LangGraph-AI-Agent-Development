# src/agents/job_scraping_agent.py

from src.utils.indeed_scraper import scrape_indeed
import json
import logging

logger = logging.getLogger(__name__)

def job_scraping_agent(configs):
    def run(state):
        logger.info("Starting job scraping...")
        job_postings = scrape_indeed(configs)
        logger.info(f"Scraped {len(job_postings)} job postings")
        
        # Save job postings to JSON file
        with open("job_posts.json", "w") as f:
            json.dump(job_postings, f, indent=4)
        logger.info("Job postings saved to job_posts.json")
        
        return {"job_postings": job_postings}
    return run