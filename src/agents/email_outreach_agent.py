# src/agents/email_outreach_agent.py

from typing import Dict, List
import anthropic
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailOutreachAgent:
    def __init__(self, configs: Dict):
        self.configs = configs
        self.client = anthropic.Anthropic(api_key=configs['anthropic']['api_key'])
        self.email_sequences = configs['email_sequences']
        self.template_cache = {}

    def generate_email_content(self, job_posting: Dict, contact_info: Dict, sequence: str) -> str:
        cache_key = f"{job_posting['job_title']}_{job_posting['company_name']}_{sequence}"
        if cache_key in self.template_cache:
            return self.template_cache[cache_key]

        prompt = f"""
        Generate a personalized email for a {sequence} outreach based on the following:
        Job Title: {job_posting['job_title']}
        Company: {job_posting['company_name']}
        Job Description: {job_posting['job_description']}
        Contact Name: {contact_info.get('first_name', '')} {contact_info.get('last_name', '')}
        Contact Position: {contact_info.get('position', '')}
        Contact Email: {contact_info.get('email', '')}
        Contact LinkedIn: {contact_info.get('linkedin_url', '')}
        Contact Location: {contact_info.get('city', '')}, {contact_info.get('state', '')}, {contact_info.get('country', '')}
        Company Industry: {contact_info.get('organization', {}).get('industry', '')}

        Create an email with the following structure:
        Subject: [Compelling subject line related to the job posting]

        [Brief, personalized introduction mentioning the contact's name and position]
        [Statement about working with an exceptional candidate for the specific job posting]
        [Offer to discuss other hiring needs if this candidate isn't the right fit]
        [Concise, bullet-point candidate summary tailored to the job requirements]
        [Call to action asking if they'd like to review the resume]
        [Closing with a way to reach you]

        Ensure the email is concise, tailored to the specific job and contact, and presents a compelling case for the candidate.
        The candidate summary should be believable and match the job requirements closely.
        """
        message = self.client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4096,
            temperature=0.7,
            system="You are an AI assistant tasked with creating personalized email templates for job prospecting. Your emails should be concise, tailored, and focused on presenting a strong candidate for the specific job opportunity.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        content = message.content[0].text
        self.template_cache[cache_key] = content
        return content

def email_outreach_agent(configs: Dict):
    agent = EmailOutreachAgent(configs)

    def run(state: Dict) -> Dict:
        logger.info("Starting email outreach preparation...")
        job_postings = state.get('job_postings', [])
        contacts = state.get('contacts', [])
        prepared_emails = []

        for job in job_postings:
            company_name = job['company_name']
            contact_info = next((contact['contact_info'] for contact in contacts if contact['company_name'] == company_name), {})
            
            if contact_info and contact_info.get('email'):
                email_content = agent.generate_email_content(job, contact_info, 'initial_outreach')
                
                prepared_emails.append({
                    'to_email': contact_info['email'],
                    'subject': email_content.split('\n')[0].replace('Subject: ', ''),
                    'content': '\n'.join(email_content.split('\n')[1:]),
                    'sequence': 'initial_outreach',
                    'job': job,
                    'contact_info': contact_info
                })
            else:
                logger.warning(f"No email found for job at {company_name}")

        logger.info(f"Prepared {len(prepared_emails)} personalized emails")
        
        # Print prepared emails
        for i, email in enumerate(prepared_emails, 1):
            logger.info(f"\nEmail {i}:")
            logger.info(f"To: {email['to_email']}")
            logger.info(f"Subject: {email['subject']}")
            logger.info(f"Content:\n{email['content']}")
            logger.info("-" * 50)

        return {"job_postings": state['job_postings'], "contacts": state['contacts'], "prepared_emails": prepared_emails}

    return run