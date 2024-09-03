# src/agents/email_outreach_agent.py

import os
from typing import Dict, List
import anthropic
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, SendAt
import logging
from email_validator import validate_email, EmailNotValidError
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailOutreachAgent:
    def __init__(self, configs: Dict):
        self.configs = configs
        self.client = anthropic.Anthropic(api_key=configs['anthropic']['api_key'])
        self.sg = SendGridAPIClient(api_key=configs['sendgrid']['api_key'])
        self.from_email = configs['sendgrid']['from_email']
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
        Sequence: {sequence}

        Use the following template structure:
        [Personalized greeting]
        [Brief introduction referencing the job posting]
        [Candidate summary - generate this based on the job description]
        [Call to action]
        [Closing]

        Ensure the email is tailored to the specific job description and company.
        """
        message = self.client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4096,
            temperature=0.1,
            system="You are an AI assistant tasked with creating personalized email templates for job prospecting.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        content = message.content[0].text
        self.template_cache[cache_key] = content
        return content

    def validate_email(self, email: str) -> str:
        try:
            valid = validate_email(email)
            return valid.email
        except EmailNotValidError as e:
            logger.warning(f"Invalid email: {email}. Error: {str(e)}")
            return None

    def get_unsubscribe_link(self) -> str:
        return f"<br><br><small>To unsubscribe, <a href='{self.configs['unsubscribe_url']}'>click here</a>.<br>Our address: {self.configs['company_address']}</small>"

    def schedule_email(self, to_email: str, subject: str, content: str, send_at: datetime) -> None:
        valid_email = self.validate_email(to_email)
        if not valid_email:
            logger.error(f"Skipping invalid email: {to_email}")
            return

        message = Mail(
            from_email=Email(self.from_email),
            to_emails=To(valid_email),
            subject=subject,
            html_content=Content("text/html", content + self.get_unsubscribe_link())
        )

        # Convert send_at to a Unix timestamp
        send_at_timestamp = int(send_at.timestamp())
        message.send_at = SendAt(send_at_timestamp)

        try:
            response = self.sg.client.mail.send.post(request_body=message.get())
            logger.info(f"Email scheduled for {valid_email} at {send_at}. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error scheduling email to {valid_email}: {str(e)}")

def email_outreach_agent(configs: Dict):
    agent = EmailOutreachAgent(configs)

    def run(state: Dict) -> Dict:
        logger.info("Starting email outreach preparation and scheduling...")
        matched_data = state.get('matched_data', [])
        contacts = state.get('contacts', [])
        prepared_emails = []

        for match in matched_data:
            job = match['job']
            prospect = match['prospect']
            
            # Find the corresponding contact info
            contact_info = next((contact['contact_info'] for contact in contacts if contact['company_name'] == job['company_name']), None)
            
            if contact_info and contact_info.get('email'):
                email_content = agent.generate_email_content(job, contact_info, 'initial_outreach')
                send_date = datetime.now() + timedelta(days=agent.email_sequences['initial']['delay_days'])
                
                agent.schedule_email(
                    to_email=contact_info['email'],
                    subject=agent.email_sequences['initial']['subject'],
                    content=email_content,
                    send_at=send_date
                )
                
                prepared_emails.append({
                    'to_email': contact_info['email'],
                    'subject': agent.email_sequences['initial']['subject'],
                    'content': email_content,
                    'sequence': 'initial_outreach',
                    'scheduled_send_date': send_date,
                    'job': job,
                    'prospect': prospect
                })
            else:
                logger.warning(f"No email found for job at {job['company_name']}")

        logger.info(f"Prepared and scheduled {len(prepared_emails)} emails for sending")
        return {"prepared_emails": prepared_emails}

    return run