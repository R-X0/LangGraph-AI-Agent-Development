# src/agents/contact_finding_agent.py

from pyhunter import PyHunter
import os
import requests
from typing import Dict, List
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

class ContactFinder:
    def __init__(self, config: Dict):
        self.config = config
        self.hunter = PyHunter(os.getenv('HUNTER_API_KEY'))
        self.apollo_api_key = config['apollo_io']['api_key']
        self.linkedin_username = os.getenv('LINKEDIN_USERNAME')
        self.linkedin_password = os.getenv('LINKEDIN_PASSWORD')
        self.linkedin_driver = None

    def initialize_linkedin(self):
        if not self.linkedin_driver:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            service = Service(ChromeDriverManager().install())
            self.linkedin_driver = webdriver.Chrome(service=service, options=chrome_options)
            self.login_to_linkedin()

    def login_to_linkedin(self):
        self.linkedin_driver.get("https://www.linkedin.com/sales/login")
        try:
            username_field = WebDriverWait(self.linkedin_driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            username_field.send_keys(self.linkedin_username)
            
            password_field = self.linkedin_driver.find_element(By.ID, "password")
            password_field.send_keys(self.linkedin_password)
            
            login_button = self.linkedin_driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            WebDriverWait(self.linkedin_driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "search-global-typeahead__input"))
            )
            print("Successfully logged in to LinkedIn Sales Navigator")
        except TimeoutException:
            print("Failed to log in to LinkedIn Sales Navigator")

    def find_contact_hunter(self, company_name: str, job_title: str) -> Dict:
        try:
            result = self.hunter.domain_search(company=company_name)
            
            if result and 'emails' in result and len(result['emails']) > 0:
                email = result['emails'][0]
                return {
                    'email': email['value'],
                    'position': email.get('position', job_title),
                    'confidence_score': email.get('confidence', 0),
                    'domain': result.get('domain', ''),
                    'first_name': email.get('first_name', ''),
                    'last_name': email.get('last_name', ''),
                    'source': 'Hunter.io'
                }
            else:
                return self._empty_contact_info(job_title, 'Hunter.io')
        except Exception as e:
            print(f"Error finding contact with Hunter.io for {company_name}: {str(e)}")
            return self._empty_contact_info(job_title, 'Hunter.io')

    def find_contact_linkedin(self, company_name: str, job_title: str) -> Dict:
        self.initialize_linkedin()
        search_url = f"https://www.linkedin.com/sales/search/people?companyName={company_name}&title={job_title}"
        self.linkedin_driver.get(search_url)
        
        try:
            result = WebDriverWait(self.linkedin_driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "artdeco-entity-lockup__title"))
            )
            name = result.text.strip()
            position_element = self.linkedin_driver.find_element(By.CLASS_NAME, "artdeco-entity-lockup__subtitle")
            position = position_element.text.strip()
            
            return {
                'email': 'Not found',  
                'position': position,
                'confidence_score': 80,  
                'domain': '',
                'first_name': name.split()[0],
                'last_name': name.split()[-1],
                'source': 'LinkedIn Sales Navigator'
            }
        except (TimeoutException, NoSuchElementException):
            return self._empty_contact_info(job_title, 'LinkedIn Sales Navigator')

    def find_contact_apollo(self, company_name: str, job_title: str) -> Dict:
        url = "https://api.apollo.io/v1/mixed_people/search"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.apollo_api_key
        }
        data = {
            "q_organization_domains": company_name,
            "page": 1,
            "per_page": 1,
            "person_titles": [job_title]
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()

            if result and 'people' in result and len(result['people']) > 0:
                person = result['people'][0]
                return {
                    'email': person.get('email', 'Not found'),
                    'position': person.get('title', job_title),
                    'confidence_score': 100,  
                    'domain': person.get('organization', {}).get('website_url', ''),
                    'first_name': person.get('first_name', ''),
                    'last_name': person.get('last_name', ''),
                    'source': 'Apollo.io'
                }
            else:
                return self._empty_contact_info(job_title, 'Apollo.io')
        except Exception as e:
            print(f"Error finding contact with Apollo.io for {company_name}: {str(e)}")
            return self._empty_contact_info(job_title, 'Apollo.io')

    def _empty_contact_info(self, job_title: str, source: str) -> Dict:
        return {
            'email': 'Not found',
            'position': job_title,
            'confidence_score': 0,
            'domain': '',
            'first_name': '',
            'last_name': '',
            'source': source
        }

    def find_contact(self, job: Dict) -> Dict:
        company_name = job['company_name']
        job_title = job['job_title']
        
        # Try each source in order
        contact_info = self.find_contact_apollo(company_name, job_title)
        if contact_info['email'] == 'Not found':
            contact_info = self.find_contact_hunter(company_name, job_title)
        if contact_info['email'] == 'Not found':
            contact_info = self.find_contact_linkedin(company_name, job_title)
        
        return {'company_name': company_name, 'contact_info': contact_info}

    def __del__(self):
        if self.linkedin_driver:
            self.linkedin_driver.quit()

def contact_finding_agent(config: Dict):
    finder = ContactFinder(config)

    def run(state: Dict) -> Dict:
        print("Starting contact finding...")
        contacts = []
        for job in state.get('job_postings', []):
            print(f"Finding contact for {job['company_name']}...")
            contact_info = finder.find_contact(job)
            contacts.append(contact_info)
        print(f"Found contact information for {len(contacts)} companies")
        return {"job_postings": state['job_postings'], "contacts": contacts}

    return run