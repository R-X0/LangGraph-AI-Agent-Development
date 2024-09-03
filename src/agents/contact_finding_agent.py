# src/agents/contact_finding_agent.py

from pyhunter import PyHunter
import os
import requests
from typing import Dict, List
import logging
import json

logger = logging.getLogger(__name__)

class ContactFinder:
    def __init__(self, configs: Dict):
        self.configs = configs
        self.hunter = PyHunter(configs.get('hunter_io', {}).get('api_key') or os.getenv('HUNTER_API_KEY'))
        self.apollo_api_key = configs.get('apollo_io', {}).get('api_key')
        self.contact_roles = configs.get('contact_roles', [])

    def find_contact_hunter(self, company_name: str, job_title: str) -> Dict:
        try:
            result = self.hunter.domain_search(company=company_name)
            
            if result is None or not result:
                logger.warning(f"Hunter.io returned no results for company: {company_name}")
                return self._empty_contact_info(job_title, 'Hunter.io')
            
            if 'emails' in result and result['emails']:
                for email in result['emails']:
                    position = email.get('position', '').lower()
                    if any(role.lower() in position for role in self.contact_roles):
                        return {
                            'email': email['value'],
                            'position': email.get('position', job_title),
                            'confidence_score': email.get('confidence', 0),
                            'domain': result.get('domain', ''),
                            'first_name': email.get('first_name', ''),
                            'last_name': email.get('last_name', ''),
                            'source': 'Hunter.io'
                        }
            return self._empty_contact_info(job_title, 'Hunter.io')
        except Exception as e:
            logger.error(f"Error finding contact with Hunter.io for {company_name}: {str(e)}")
            return self._empty_contact_info(job_title, 'Hunter.io')

    def find_contact_apollo(self, company_name: str, job_title: str) -> Dict:
        search_url = "https://api.apollo.io/v1/mixed_people/search"
        enrich_url = "https://api.apollo.io/v1/people/enrich"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.apollo_api_key
        }
        search_data = {
            "q_organization_domains": company_name,
            "page": 1,
            "per_page": 10,
            "person_titles": self.contact_roles
        }

        try:
            search_response = requests.post(search_url, headers=headers, json=search_data)
            search_response.raise_for_status()
            search_result = search_response.json()

            if search_result and 'people' in search_result and len(search_result['people']) > 0:
                for person in search_result['people']:
                    enrich_data = {"id": person['id']}
                    enrich_response = requests.post(enrich_url, headers=headers, json=enrich_data)
                    enrich_response.raise_for_status()
                    enrich_result = enrich_response.json()

                    if 'person' in enrich_result:
                        enriched_person = enrich_result['person']
                        return {
                            'email': enriched_person.get('email', 'Not found'),
                            'position': enriched_person.get('title', job_title),
                            'confidence_score': 100,
                            'domain': enriched_person.get('organization', {}).get('website_url', ''),
                            'first_name': enriched_person.get('first_name', ''),
                            'last_name': enriched_person.get('last_name', ''),
                            'source': 'Apollo.io'
                        }

            return self._empty_contact_info(job_title, 'Apollo.io')
        except Exception as e:
            logger.error(f"Error finding contact with Apollo.io for {company_name}: {str(e)}")
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
        hunter_info = self.find_contact_hunter(company_name, job_title)
        apollo_info = self.find_contact_apollo(company_name, job_title)
        
        contacts = [hunter_info, apollo_info]
        valid_contacts = [c for c in contacts if c['email'] is not None and c['email'] != 'N/A']
        
        if not valid_contacts:
            best_contact = self._empty_contact_info(job_title, "Multiple sources")
        else:
            best_contact = max(valid_contacts, key=lambda x: x['confidence_score'])
        
        logger.info(f"Best contact found: {best_contact['email']} (Source: {best_contact['source']})")
        return {'company_name': company_name, 'contact_info': best_contact}

def contact_finding_agent(configs: Dict):
    finder = ContactFinder(configs)

    def run(state: Dict) -> Dict:
        logger.info("Starting contact finding...")
        contacts = []
        
        # Read job postings from job_posts.json
        try:
            with open("job_posts.json", "r") as f:
                job_postings = json.load(f)
        except FileNotFoundError:
            logger.error("job_posts.json file not found. Make sure it exists in the current directory.")
            return {"error": "Job postings file not found"}
        except json.JSONDecodeError:
            logger.error("Error decoding job_posts.json. Make sure it's a valid JSON file.")
            return {"error": "Invalid job postings file"}
        
        for job in job_postings:
            contact_info = finder.find_contact(job)
            contacts.append(contact_info)
        logger.info(f"Found contact information for {len(contacts)} companies")
        return {"job_postings": job_postings, "contacts": contacts}

    return run