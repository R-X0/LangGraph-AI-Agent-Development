from pyhunter import PyHunter
import os

def contact_finding_agent(config):
    hunter = PyHunter(os.getenv('HUNTER_API_KEY'))

    def find_contact(job):
        company_name = job['company_name']
        job_title = job['job_title']
        
        try:
            # Try to find email addresses for the company domain
            result = hunter.domain_search(company=company_name)
            
            if result and 'emails' in result and len(result['emails']) > 0:
                # Get the first email in the list
                email = result['emails'][0]
                contact_info = {
                    'email': email['value'],
                    'position': email.get('position', job_title),
                    'confidence_score': email.get('confidence', 0),
                    'domain': result.get('domain', ''),
                    'first_name': email.get('first_name', ''),
                    'last_name': email.get('last_name', '')
                }
            else:
                # If no email found, return empty info
                contact_info = {
                    'email': 'Not found',
                    'position': job_title,
                    'confidence_score': 0,
                    'domain': '',
                    'first_name': '',
                    'last_name': ''
                }
            
        except Exception as e:
            print(f"Error finding contact for {company_name}: {str(e)}")
            contact_info = {
                'email': 'Error occurred',
                'position': job_title,
                'confidence_score': 0,
                'domain': '',
                'first_name': '',
                'last_name': ''
            }
        
        return {'company_name': company_name, 'contact_info': contact_info}

    def run(state):
        print("Starting contact finding...")
        contacts = []
        for job in state.get('job_postings', []):
            print(f"Finding contact for {job['company_name']}...")
            contact_info = find_contact(job)
            contacts.append(contact_info)
        print(f"Found contact information for {len(contacts)} companies")
        return {"job_postings": state['job_postings'], "contacts": contacts}

    return run