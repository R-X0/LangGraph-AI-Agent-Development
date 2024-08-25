# src/agents/contact_finding_agent.py

from pyhunter import PyHunter
import os
from typing import Dict, List

class ContactFinder:
    def __init__(self, config: Dict):
        self.config = config
        self.hunter = PyHunter(os.getenv('HUNTER_API_KEY'))
        # We'll initialize these later 
        self.linkedin_sales_navigator = None
        self.apollo = None

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
        # Placeholder for LinkedIn Sales Navigator integration
        print(f"Would search LinkedIn Sales Navigator for {company_name}")
        return self._empty_contact_info(job_title, 'LinkedIn Sales Navigator')

    def find_contact_apollo(self, company_name: str, job_title: str) -> Dict:
        # Placeholder for Apollo.io integration
        print(f"Would search Apollo.io for {company_name}")
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
        contact_info = self.find_contact_hunter(company_name, job_title)
        if contact_info['email'] == 'Not found':
            contact_info = self.find_contact_linkedin(company_name, job_title)
        if contact_info['email'] == 'Not found':
            contact_info = self.find_contact_apollo(company_name, job_title)
        
        return {'company_name': company_name, 'contact_info': contact_info}

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