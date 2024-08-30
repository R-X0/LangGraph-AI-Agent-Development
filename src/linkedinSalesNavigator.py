# src/linkedinSalesNavigator.py

import yaml
import time
import pickle
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

logger = logging.getLogger(__name__)

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
        
        # Wait for successful login
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
    
    # Use the existing Chrome installation
    chrome_options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"  # Adjust this path if necessary
    
    # Uncomment the next line if you want to run in headless mode
    # chrome_options.add_argument("--headless")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 10)
    
    logger.info("Logging into LinkedIn")
    driver.get(base_url)
    
    try:
        cookies = pickle.load(open("cookies/LinkedIn.pkl", "rb"))
        for cookie in cookies:
            driver.add_cookie(cookie)
        driver.get(base_url)
        time.sleep(3)
        
        if "Login screen" not in driver.page_source:
            logger.info("Successfully logged in using cookies")
            return driver, wait
    except Exception as e:
        logger.warning(f"Could not load cookies: {str(e)}")
    
    if login(driver, wait, config['username'], config['password']):
        pickle.dump(driver.get_cookies(), open("cookies/LinkedIn.pkl", "wb"))
        return driver, wait
    else:
        raise Exception("Failed to log in to LinkedIn")

def set_filters(driver, wait, config):
    logger.info("Setting search filters")

    # Set Company Filters
    for company in config.get('companies', []):
        try:
            company_filter = driver.find_element(By.CSS_SELECTOR, 'fieldset [title="Current company"] li-icon[type="plus-icon"]')
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
            title_filter = driver.find_element(By.CSS_SELECTOR, 'fieldset [title="Current job title"] li-icon[type="plus-icon"]')
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
            seniority_filter = driver.find_element(By.CSS_SELECTOR, 'fieldset [title="Seniority level"] li-icon[type="plus-icon"]')
            seniority_filter.click()
            time.sleep(2)
            
            level_button = driver.find_element(By.XPATH, f'//*[contains(@aria-label, "Include {level}")]')
            level_button.click()
        except Exception as e:
            logger.error(f"Error setting seniority level filter for {level}: {str(e)}")

    # Set Location Filters
    if config.get('OnlyUSProspects', False):
        try:
            geography_filter = driver.find_element(By.CSS_SELECTOR, 'fieldset [title="Geography"] li-icon[type="plus-icon"]')
            geography_filter.click()
            time.sleep(1)
            
            geography_input = driver.find_element(By.CSS_SELECTOR, 'fieldset [title="Geography"] input')
            geography_input.send_keys("United States")
            time.sleep(1)
            
            us_option = driver.find_element(By.CSS_SELECTOR, 'ul[role="listbox"] li:nth-child(1)')
            us_option.click()

            for state in config.get('StatesToExclude', []):
                geography_filter.click()
                time.sleep(1)
                geography_input.send_keys(state)
                time.sleep(1)
                exclude_option = driver.find_element(By.CSS_SELECTOR, 'ul[role="listbox"] li:nth-child(1) div div:nth-child(4)')
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
            
            if len(prospects) >= config['MinimumNumberOfJobPosts']:
                break
            
            next_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Next"]')
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
    linkedin_config = config.get('linkedin_sales_navigator', {})
    if not linkedin_config:
        logger.error("LinkedIn Sales Navigator configuration not found")
        return []
    
    base_url = linkedin_config['BaseUrl']
    driver, wait = setup_driver(linkedin_config, base_url)
    
    try:
        prospects = search_contacts(driver, wait, linkedin_config)
        logger.info(f"Found {len(prospects)} prospects")
        
        # TODO: Implement saving to list functionality using linkedin_config['SavelistName']
        
        return prospects
    finally:
        driver.quit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)
    results = add_contacts(config)
    print(f"Found {len(results)} prospects")
    for prospect in results[:5]:  # Print first 5 prospects as an example
        print(f"Name: {prospect['name']}, Title: {prospect['title']}, Company: {prospect['company']}")