from src.utils.indeed_scraper import scrape_indeed

def job_scraping_agent(config):
    def run(state):
        job_postings = scrape_indeed(config)  # Pass the entire config
        return {"job_postings": job_postings}
    return run