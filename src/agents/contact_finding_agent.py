# src/agents/contact_finding_agent.py

from pyhunter import PyHunter
import os
import requests
from typing import Dict, List
import logging
import time
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class ContactFinder:
    def __init__(self, configs: Dict):
        self.configs = configs
        self.hunter = PyHunter(os.getenv('HUNTER_API_KEY'))
        self.apollo_api_key = configs['apollo_io']['api_key']

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
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
                logger.warning(f"Hunter.io couldn't find emails for company: {company_name}")
                return self._empty_contact_info(job_title, 'Hunter.io')
        except Exception as e:
            logger.error(f"Error finding contact with Hunter.io for {company_name}: {str(e)}", exc_info=True)
            return self._empty_contact_info(job_title, 'Hunter.io')

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def find_contact_apollo(self, company_name: str, job_title: str) -> Dict:
        search_url = "https://api.apollo.io/v1/mixed_people/search"
        enrich_url = "https://api.apollo.io/v1/people/enrich"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.apollo_api_key
        }
        search_data = {
            "q_organization_name": company_name,
            "page": 1,
            "per_page": 20,
            "person_titles": [job_title, "HR", "Recruiter", "Hiring Manager"]
        }

        try:
            search_response = requests.post(search_url, headers=headers, json=search_data)
            search_response.raise_for_status()
            search_result = search_response.json()

            if 'error' in search_result:
                logger.error(f"Apollo.io API error for {company_name}: {search_result['error']}")
                return self._empty_contact_info(job_title, 'Apollo.io')

            if search_result and 'people' in search_result and search_result['people']:
                for person in search_result['people']:
                    if person.get('organization', {}).get('name', '').lower() == company_name.lower():
                        enrich_data = {"id": person['id']}
                        enrich_response = requests.post(enrich_url, headers=headers, json=enrich_data)
                        enrich_response.raise_for_status()
                        enrich_result = enrich_response.json()

                        if 'person' in enrich_result:
                            enriched_person = enrich_result['person']
                            if enriched_person.get('email'):
                                return {
                                    'email': enriched_person['email'],
                                    'position': enriched_person.get('title', job_title),
                                    'confidence_score': 100,
                                    'domain': enriched_person.get('organization', {}).get('website_url', ''),
                                    'first_name': enriched_person.get('first_name', ''),
                                    'last_name': enriched_person.get('last_name', ''),
                                    'source': 'Apollo.io'
                                }

            logger.warning(f"No matching contact found in Apollo.io for {company_name}")
            return self._empty_contact_info(job_title, 'Apollo.io')
        except Exception as e:
            logger.error(f"Error finding contact with Apollo.io for {company_name}: {str(e)}", exc_info=True)
            return self._empty_contact_info(job_title, 'Apollo.io')

    def _empty_contact_info(self, job_title: str, source: str) -> Dict:
        return {
            'email': None,
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
        
        logger.info(f"Finding contact for {company_name}...")
        
        company_variations = [company_name, company_name.replace(" ", ""), company_name.split()[0]]
        
        for variation in company_variations:
            hunter_info = self.find_contact_hunter(variation, job_title)
            if hunter_info.get('email'):
                logger.info(f"Hunter.io result for {company_name}: {hunter_info.get('email')} (Score: {hunter_info.get('confidence_score')})")
                return {'company_name': company_name, 'contact_info': hunter_info}
            
            apollo_info = self.find_contact_apollo(variation, job_title)
            if apollo_info.get('email'):
                logger.info(f"Apollo.io result for {company_name}: {apollo_info.get('email')} (Score: {apollo_info.get('confidence_score')})")
                return {'company_name': company_name, 'contact_info': apollo_info}
            
            time.sleep(1)  # Add a 1-second delay between API calls
        
        logger.warning(f"No valid contacts found for {company_name}")
        return {'company_name': company_name, 'contact_info': self._empty_contact_info(job_title, "Multiple sources")}

def contact_finding_agent(configs: Dict):
    finder = ContactFinder(configs)

    def run(state: Dict) -> Dict:
        logger.info("Starting contact finding...")
        contacts = []
        for job in state.get('job_postings', []):
            contact_info = finder.find_contact(job)
            contacts.append(contact_info)
        logger.info(f"Found contact information for {len(contacts)} companies")
        return {"job_postings": state['job_postings'], "contacts": contacts}

    return run