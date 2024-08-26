# src/agents/contact_finding_agent.py

from pyhunter import PyHunter
import os
import requests
from typing import Dict, List

class ContactFinder:
    def __init__(self, config: Dict):
        self.config = config
        self.hunter = PyHunter(os.getenv('HUNTER_API_KEY'))
        self.apollo_api_key = config['apollo_io']['api_key']

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
            "per_page": 1,
            "person_titles": [job_title]
        }

        try:
            # First, search for the person
            search_response = requests.post(search_url, headers=headers, json=search_data)
            search_response.raise_for_status()
            search_result = search_response.json()

            if search_result and 'people' in search_result and len(search_result['people']) > 0:
                person = search_result['people'][0]
                
                # Now, use the enrich endpoint to get detailed information including email
                enrich_data = {
                    "id": person['id']
                }
                enrich_response = requests.post(enrich_url, headers=headers, json=enrich_data)
                enrich_response.raise_for_status()
                enrich_result = enrich_response.json()

                if 'person' in enrich_result:
                    enriched_person = enrich_result['person']
                    return {
                        'email': enriched_person.get('email', 'Not found'),
                        'position': enriched_person.get('title', job_title),
                        'confidence_score': 100,  # Apollo usually provides verified information
                        'domain': enriched_person.get('organization', {}).get('website_url', ''),
                        'first_name': enriched_person.get('first_name', ''),
                        'last_name': enriched_person.get('last_name', ''),
                        'source': 'Apollo.io'
                    }

            return self._empty_contact_info(job_title, 'Apollo.io')
        except Exception as e:
            print(f"Error finding contact with Apollo.io for {company_name}: {str(e)}")
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
        
        print(f"Finding contact for {company_name}...")
        hunter_info = self.find_contact_hunter(company_name, job_title)
        apollo_info = self.find_contact_apollo(company_name, job_title)
        
        # Determine the best contact
        contacts = [hunter_info, apollo_info]
        valid_contacts = [c for c in contacts if c['email'] is not None]
        
        if not valid_contacts:
            best_contact = self._empty_contact_info(job_title, "Multiple sources")
        else:
            best_contact = max(valid_contacts, key=lambda x: x['confidence_score'])
        
        print(f"Best contact found: {best_contact['email']} (Source: {best_contact['source']})")
        return {'company_name': company_name, 'contact_info': best_contact}

def contact_finding_agent(config: Dict):
    finder = ContactFinder(config)

    def run(state: Dict) -> Dict:
        print("Starting contact finding...")
        contacts = []
        for job in state.get('job_postings', []):
            contact_info = finder.find_contact(job)
            contacts.append(contact_info)
        print(f"Found contact information for {len(contacts)} companies")
        return {"job_postings": state['job_postings'], "contacts": contacts}

    return run