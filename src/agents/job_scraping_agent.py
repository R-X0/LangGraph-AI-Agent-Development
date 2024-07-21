from src.utils.indeed_scraper import scrape_indeed

def job_scraping_agent(config):
    def run(state):
        print("Starting job scraping...")
        job_postings = scrape_indeed(config)
        print(f"Scraped {len(job_postings)} job postings")
        return {"job_postings": job_postings}
    return run