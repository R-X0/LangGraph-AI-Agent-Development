# src/utils/indeed_scraper.py

import bs4
import requests
import urllib.parse
import logging
import time
import warnings
from bs4 import MarkupResemblesLocatorWarning

# Suppress the specific BeautifulSoup warning
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

logger = logging.getLogger(__name__)

def is_location_valid(location, excluded_states):
    try:
        jl_subs = [x.strip() for x in location.split(",")]
        jl_subs = [sub_elem for elem in jl_subs for sub_elem in elem.split() if sub_elem]
    except:
        jl_subs = []
    return not any(state in jl_subs for state in excluded_states)

def scrape_indeed(configs):
    logger.info("Starting Indeed Scraper")
    
    search_query = configs['indeed']['search_query']
    INDEED_base_url = "https://www.indeed.com/jobs?sort=date&q="
    job_post = urllib.parse.quote_plus(search_query)

    logger.info(f"Searching: {search_query}")

    indeed_posts = []
    next_page_url = f"{INDEED_base_url}{job_post}"
    page_number = 1

    while next_page_url:
        payload = {
            "api_key": configs['indeed']['scraper_api_key'],
            "url": next_page_url,
            "premium": True,
            "ultra_premium": True,
        }
        
        try:
            r = requests.get("https://api.scraperapi.com/", params=payload)
            r.raise_for_status()
            soup = bs4.BeautifulSoup(r.text, "html.parser")
            
            job_cards = soup.select("ul.css-zu9cdh li.eu4oa1w0")

            if page_number % 4 == 0:
                logger.info(f"Scraped Up to Page #{page_number}")

            for job_card in job_cards:
                try:
                    company_name = job_card.select_one('[data-testid="company-name"]').text
                    job_title = job_card.select_one("h2.jobTitle").text
                    job_location = job_card.select_one('[data-testid="text-location"]').text
                    job_description = job_card.select_one(".heading6 li").text
                    job_post_date = job_card.select_one('[data-testid="myJobsStateDate"]').text
                except AttributeError:
                    # Silently skip this job posting if any required field is missing
                    continue

                if not all(keyword.lower() in job_title.lower() for keyword in configs['indeed']['required_keywords']):
                    continue

                if not is_location_valid(job_location, configs['indeed']['states_to_exclude']):
                    continue

                indeed_posts.append({
                    "company_name": company_name,
                    "job_title": job_title,
                    "job_location": job_location,
                    "job_description": job_description,
                    "job_post_date": job_post_date,
                    "source": "Indeed"  # Add this line to include the source
                })

            if len(indeed_posts) >= configs['indeed']['minimum_entries']:
                break

            try:
                next_page_element = soup.select_one('[aria-label="Next Page"]')
                next_page_url = f"https://www.indeed.com{next_page_element['href']}" if next_page_element else None
            except:
                next_page_url = None

            if next_page_url:
                page_number += 1

            time.sleep(1)  # Add a small delay between requests

        except requests.RequestException as e:
            logger.error(f"Error fetching page {page_number}: {str(e)}")
            break

    logger.info(f"Scraped {len(indeed_posts)} Indeed Posts")
    logger.info("Ending Indeed Scraper")

    return indeed_posts

if __name__ == "__main__":
    import yaml
    with open("configs.yaml", "r") as file:
        configs = yaml.safe_load(file)
    scrape_indeed(configs)