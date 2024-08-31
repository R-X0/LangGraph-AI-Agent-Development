import json
import yaml
import time
import pickle
import logging
from selenium import webdriver
from collections import defaultdict
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import os

logger = logging.getLogger(__name__)

def save_data_into_json(filename, data, merge=False):
    if merge:
        try:
            with open(f"{filename}.json", "r") as file:
                existing_data = json.load(file)
            existing_data.extend(data)
            data = existing_data
        except FileNotFoundError:
            pass
    
    with open(f"{filename}.json", "w") as file:
        json.dump(data, file, indent=4)

def analyze_job_posts(config, job_list):
    job_count_per_company = defaultdict(int)
    job_titles = defaultdict(list)
    source_count = defaultdict(lambda: defaultdict(int))
    job_titles_in_both_sources = defaultdict(list)

    for job in job_list:
        company = job["company_name"]
        title = job["job_title"]
        source = job.get("source", "Unknown")

        job_count_per_company[company] += 1

        if title not in job_titles[company]:
            job_titles[company].append(title)

        source_count[company][source] += 1

        if source == "Indeed":
            if source_count[company]["LinkedIn"] > 0 and title in job_titles[company]:
                job_titles_in_both_sources[company].append(title)
                job_count_per_company[company] -= 1
        elif source == "LinkedIn":
            if source_count[company]["Indeed"] > 0 and title in job_titles[company]:
                job_titles_in_both_sources[company].append(title)
                job_count_per_company[company] -= 1

    results = []
    minimum_job_posts = config.get("MinimumNumberOfJobPosts", 1)
    for company in job_count_per_company:
        if job_count_per_company[company] >= minimum_job_posts:
            results.append(
                {
                    "company_name": company,
                    "total_count": job_count_per_company[company],
                    "same_post_titles": job_titles_in_both_sources[company],
                }
            )

    results.sort(key=lambda x: x["total_count"], reverse=True)

    return results

def login(driver, wait, username, password):
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'iframe[title="Login screen"]')))
        
        login_frame = driver.find_element(By.CSS_SELECTOR, 'iframe[title="Login screen"]')
        driver.switch_to.frame(login_frame)
        
        username_field = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#username")))
        username_field.send_keys(username)
        
        password_field = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#password")))
        password_field.send_keys(password)
        
        sign_in_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Sign in"]')))
        sign_in_button.click()
        
        driver.switch_to.default_content()
        
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.search-global-typeahead__input')))
        
        logger.info("Successfully logged in to LinkedIn")
        return True
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        return False

def setup_driver(config, base_url):
    logger.info("Setting up Chrome driver")
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    if config.get("Headless", False):
        chrome_options.add_argument("--headless")
    
    chromedriver_path = r"C:\Users\Bona\Desktop\chromedriver-win64\chromedriver.exe"
    
    if not os.path.exists(chromedriver_path):
        raise FileNotFoundError(f"ChromeDriver not found at {chromedriver_path}. Please ensure it's in this location.")
    
    service = Service(chromedriver_path)
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("Successfully initialized Chrome driver")
        wait = WebDriverWait(driver, 20)
        
        logger.info("Logging into LinkedIn")
        driver.get(base_url)
        
        return driver, wait
    except Exception as e:
        logger.error(f"Failed to initialize Chrome driver: {str(e)}")
        raise

def set_filters(driver, wait, config):
    logger.info("Setting search filters")

    # Set Company Filters
    for company in config.get('companies', []):
        try:
            company_filter = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'fieldset [title="Current company"] li-icon[type="plus-icon"]')))
            company_filter.click()
            
            company_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'fieldset [title="Current company"] input')))
            company_input.clear()
            company_input.send_keys(company)
            time.sleep(2)
            
            options = driver.find_elements(By.CSS_SELECTOR, 'ul[role="listbox"] li')
            for option in options:
                if company.lower() in option.text.lower():
                    option.click()
                    break
            else:
                if config['UseFirstOption']:
                    options[0].click()
                elif config['UseSearchQuery']:
                    company_input.send_keys(Keys.RETURN)
        except Exception as e:
            logger.error(f"Error setting company filter for {company}: {str(e)}")

    # Set Job Title Filters
    for job_title in config.get('RequiredJobTitles', []):
        try:
            title_filter = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'fieldset [title="Current job title"] li-icon[type="plus-icon"]')))
            title_filter.click()
            
            title_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'fieldset [title="Current job title"] input')))
            title_input.send_keys(job_title)
            time.sleep(2)
            title_input.send_keys(Keys.RETURN)
        except Exception as e:
            logger.error(f"Error setting job title filter for {job_title}: {str(e)}")

    # Set Seniority Level Filters
    for level in config.get('RequiredSeniorityLevels', []):
        try:
            seniority_filter = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'fieldset [title="Seniority level"] li-icon[type="plus-icon"]')))
            seniority_filter.click()
            time.sleep(2)
            
            level_button = wait.until(EC.element_to_be_clickable((By.XPATH, f'//*[contains(@aria-label, "Include {level}")]')))
            level_button.click()
        except Exception as e:
            logger.error(f"Error setting seniority level filter for {level}: {str(e)}")

    # Set Location Filters
    if config.get('OnlyUSProspects', False):
        try:
            geography_filter = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'fieldset [title="Geography"] li-icon[type="plus-icon"]')))
            geography_filter.click()
            time.sleep(1)
            
            geography_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'fieldset [title="Geography"] input')))
            geography_input.send_keys("United States")
            time.sleep(1)
            
            us_option = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'ul[role="listbox"] li:nth-child(1)')))
            us_option.click()

            for state in config.get('StatesToExclude', []):
                geography_filter.click()
                time.sleep(1)
                geography_input.send_keys(state)
                time.sleep(1)
                exclude_option = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'ul[role="listbox"] li:nth-child(1) div div:nth-child(4)')))
                exclude_option.click()
        except Exception as e:
            logger.error(f"Error setting location filters: {str(e)}")

    logger.info("Search filters set successfully")

def search_contacts(driver, wait, config):
    logger.info("Searching for contacts")
    set_filters(driver, wait, config)
    
    prospects = []
    page = 1
    
    while True:
        try:
            all_entries = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".artdeco-list__item")))
            
            for entry in all_entries:
                try:
                    name = entry.find_element(By.CSS_SELECTOR, '[data-anonymize="person-name"]').text
                    title = entry.find_element(By.CSS_SELECTOR, '[data-anonymize="title"]').text
                    company = entry.find_element(By.CSS_SELECTOR, '[data-view-name="search-results-lead-company-name"]').text
                    location = entry.find_element(By.CSS_SELECTOR, '[data-anonymize="location"]').text
                    profile_link = entry.find_element(By.CSS_SELECTOR, 'a[data-view-name="search-results-lead-name"]').get_attribute("href")
                    
                    prospects.append({
                        "name": name,
                        "title": title,
                        "company": company,
                        "location": location,
                        "profile_link": profile_link,
                    })
                except Exception as e:
                    logger.warning(f"Error extracting prospect info: {str(e)}")

            logger.info(f"Processed page {page}, total prospects: {len(prospects)}")
            
            # Click on select all
            select_all_button = driver.find_element(By.CSS_SELECTOR, ".p4 .full-width label")
            select_all_button.click()

            time.sleep(2)
            try:
                save_to_list_button = driver.find_element(
                    By.CSS_SELECTOR,
                    'button[aria-label="Save to list. All selected leads are saved. Add to a custom list."]',
                )
                save_to_list_button.click()
            except:
                try:
                    save_to_list_button = driver.find_element(
                        By.CSS_SELECTOR,
                        'button[aria-label="Save to list. Save all selected leads and add to a custom list."]',
                    )
                    save_to_list_button.click()
                except:
                    save_to_list_button = driver.find_element(
                        By.CSS_SELECTOR,
                        '.p4 .full-width:nth-child(1) button[aria-expanded="false"]',
                    )
                    save_to_list_button.click()

            time.sleep(1)
            all_lists = driver.find_elements(By.CSS_SELECTOR, '[role="menuitem"] button')

            for list_item in all_lists:
                if config["SavelistName"].lower() in list_item.text.lower():
                    list_item.click()
                    time.sleep(1)
                    break

            next_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'button[aria-label="Next"]')))
            if "disabled" in next_button.get_attribute("class"):
                break
            next_button.click()
            time.sleep(2)
            page += 1
        
        except Exception as e:
            logger.error(f"Error occurred while searching on page {page}: {str(e)}")
            break
    
    return prospects

def add_contacts(config):
    full_start = time.time()

    with open(config["InputFileSRC"]) as file:
        job_posts = json.load(file)

    linkedin_config = config.get('linkedin_sales_navigator', {})
    analyzed_job_posts = analyze_job_posts(linkedin_config, job_posts)
    save_data_into_json("analyzied_job_posts", analyzed_job_posts, merge=False)

    logger.info("Starting LinkedIn Sales Automation")

    base_url = linkedin_config.get("BaseUrl", "https://www.linkedin.com/sales/search/people")
    
    try:
        driver, wait = setup_driver(config, base_url)
        prospects = search_contacts(driver, wait, linkedin_config)
        logger.info(f"Found {len(prospects)} prospects")
        
        save_data_into_json("prospects", prospects, merge=False)
        logger.info("Data saved into prospects.json")

        return prospects
    except Exception as e:
        logger.error(f"Error in add_contacts: {str(e)}")
        raise
    finally:
        if 'driver' in locals():
            driver.quit()

    logger.info("Ending LinkedIn Sales Automation")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with open("configs.yaml", "r") as file:
        config = yaml.safe_load(file)
    results = add_contacts(config)
    print(f"Found {len(results)} prospects")
    for prospect in results[:5]:
        print(f"Name: {prospect['name']}, Title: {prospect['title']}, Company: {prospect['company']}")