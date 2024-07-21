import bs4
import requests
import urllib.parse

def is_location_valid(location, excluded_states):
    try:
        jl_subs = [x.strip() for x in location.split(",")]
        jl_subs = [sub_elem for elem in jl_subs for sub_elem in elem.split() if sub_elem]
    except:
        jl_subs = []
    return not any(state in jl_subs for state in excluded_states)

def scrape_indeed(config):
    print("-> Starting Indeed Scraper")
    
    search_query = config['indeed']['search_query']
    INDEED_base_url = "https://www.indeed.com/jobs?sort=date&q="
    job_post = urllib.parse.quote_plus(search_query)

    print(f"-> Searching: {search_query}")

    indeed_posts = []
    next_page_url = f"{INDEED_base_url}{job_post}"
    page_number = 1

    while next_page_url:
        payload = {
            "api_key": config['indeed']['scraper_api_key'],
            "url": next_page_url,
            "premium": True,
            "ultra_premium": True,
        }
        
        r = requests.get("https://api.scraperapi.com/", params=payload)
        soup = bs4.BeautifulSoup(r.text, "html.parser")
        
        job_cards = soup.select("ul.css-zu9cdh li.eu4oa1w0")

        if page_number % 4 == 0:
            print(f"-> Scraped Up to Page #{page_number}")

        for job_card in job_cards:
            try:
                company_name = job_card.select_one('[data-testid="company-name"]').text
                job_title = job_card.select_one("h2.jobTitle").text
                job_location = job_card.select_one('[data-testid="text-location"]').text
                job_description = job_card.select_one(".heading6 li").text
                job_post_date = job_card.select_one('[data-testid="myJobsStateDate"]').text
            except:
                continue

            if not all(keyword.lower() in job_title.lower() for keyword in config['indeed']['required_keywords']):
                continue

            if not is_location_valid(job_location, config['indeed']['states_to_exclude']):
                continue

            indeed_posts.append({
                "company_name": company_name,
                "job_title": job_title,
                "job_location": job_location,
                "job_description": job_description,
                "job_post_date": job_post_date,
            })

        if len(indeed_posts) >= config['indeed']['minimum_entries']:
            break

        try:
            next_page_element = soup.select_one('[aria-label="Next Page"]')
            next_page_url = f"https://www.indeed.com{next_page_element['href']}" if next_page_element else None
        except:
            next_page_url = None

        if next_page_url:
            page_number += 1

    print(f"-> Scraped {len(indeed_posts)} Indeed Posts")
    print("-> Ending Indeed Scraper")

    return indeed_posts