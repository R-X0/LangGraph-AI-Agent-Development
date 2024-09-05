import os
import requests
from typing import Dict, List
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
import re
from urllib.parse import urlparse
import time

logger = logging.getLogger(__name__)

class ContactFinder:
    def __init__(self, configs: Dict):
        self.configs = configs
        self.apollo_api_key = configs['apollo_io']['api_key']
        self.proxycurl_api_key = configs['proxycurl']['api_key']
        self.target_roles = [
            "HR",
            "Human Resources",
            "Recruiter",
            "Talent Acquisition",
            "People Operations"
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _make_proxycurl_request(self, url: str, params: Dict) -> Dict:
        headers = {"Authorization": f"Bearer {self.proxycurl_api_key}"}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def find_contact_apollo(self, company_name: str) -> Dict:
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
            "per_page": 10,
            "person_titles": self.target_roles
        }

        print(f"Apollo.io search data: {search_data}")

        try:
            search_response = requests.post(search_url, headers=headers, json=search_data)
            search_response.raise_for_status()
            search_result = search_response.json()
            print(f"Apollo.io search result: {search_result}")

            if search_result and 'people' in search_result and search_result['people']:
                person = search_result['people'][0]
                
                # Use the enrich endpoint to get the email
                enrich_data = {"id": person['id']}
                enrich_response = requests.post(enrich_url, headers=headers, json=enrich_data)
                enrich_response.raise_for_status()
                enrich_result = enrich_response.json()
                print(f"Apollo.io enrich result: {enrich_result}")
                
                if 'person' in enrich_result:
                    enriched_person = enrich_result['person']
                    return {
                        'first_name': enriched_person.get('first_name', ''),
                        'last_name': enriched_person.get('last_name', ''),
                        'full_name': f"{enriched_person.get('first_name', '')} {enriched_person.get('last_name', '')}".strip(),
                        'position': enriched_person.get('title', ''),
                        'company_name': company_name,
                        'email': enriched_person.get('email', ''),
                        'linkedin_url': enriched_person.get('linkedin_url', ''),
                        'source': 'Apollo.io'
                    }

            print(f"No matching contact found in Apollo.io for {company_name}")
        except Exception as e:
            print(f"Error in Apollo.io request for {company_name}: {str(e)}")
        
        return {}

    def enrich_with_proxycurl(self, contact_info: Dict) -> Dict:
        if not contact_info.get('linkedin_url'):
            print(f"No LinkedIn URL available for {contact_info.get('full_name')}")
            return contact_info

        print(f"Attempting Proxycurl enrichment for {contact_info['full_name']}...")
        
        enrich_url = "https://nubela.co/proxycurl/api/v2/linkedin"
        enrich_params = {'url': contact_info['linkedin_url']}
        
        try:
            enrich_response = self._make_proxycurl_request(enrich_url, enrich_params)
            
            if enrich_response:
                contact_info.update({
                    'country': enrich_response.get('country'),
                    'city': enrich_response.get('city'),
                    'state': enrich_response.get('state'),
                    'industry': enrich_response.get('industry'),
                    'company_domain': enrich_response.get('company_domain'),
                    'source': 'Apollo.io + Proxycurl'
                })
                print(f"Proxycurl enrichment successful for {contact_info['full_name']}")
            else:
                print(f"Proxycurl couldn't enrich data for {contact_info['full_name']}")
        except Exception as e:
            print(f"Error in Proxycurl enrichment for {contact_info['full_name']}: {str(e)}")
        
        return contact_info

    def find_contact(self, job: Dict) -> Dict:
        company_name = job['company_name']
        
        print(f"Finding contact for {company_name}...")
        
        contact_info = self.find_contact_apollo(company_name)
        if contact_info:
            if contact_info.get('email'):
                print(f"Apollo.io found email for {company_name}: {contact_info['email']}")
            enriched_info = self.enrich_with_proxycurl(contact_info)
            return {'company_name': company_name, 'contact_info': enriched_info}
        
        print(f"No valid contact found for {company_name}")
        return {'company_name': company_name, 'contact_info': {}}

def contact_finding_agent(configs: Dict):
    finder = ContactFinder(configs)

    def run(state: Dict) -> Dict:
        print("Starting contact finding...")
        contacts = []
        for job in state.get('job_postings', []):
            contact_info = finder.find_contact(job)
            contacts.append(contact_info)
        print(f"Found contact information for {len(contacts)} companies")
        return {"job_postings": state['job_postings'], "contacts": contacts}

    return run