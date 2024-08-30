# src/agents/email_outreach_agent.py

import os
from typing import Dict, List, Optional
import anthropic
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, SendAt
import logging
from email_validator import validate_email, EmailNotValidError
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailOutreachAgent:
    def __init__(self, config: Dict):
        self.config = config
        self.client = anthropic.Anthropic(api_key=config['anthropic']['api_key'])
        self.sg = SendGridAPIClient(api_key=config['sendgrid']['api_key'])
        self.from_email = config['sendgrid']['from_email']
        self.email_sequences = config['email_sequences']
        self.template_cache = {}

    async def generate_email_content(self, job_posting: Dict, contact_info: Dict, sequence: str) -> str:
        cache_key = f"{job_posting['job_title']}_{job_posting['company_name']}_{sequence}"
        if cache_key in self.template_cache:
            return self.template_cache[cache_key]

        prompt = f"""
        Generate a personalized email for a {sequence} outreach based on the following:
        Job Title: {job_posting['job_title']}
        Company: {job_posting['company_name']}
        Job Description: {job_posting['job_description']}
        Contact Name: {contact_info['first_name']} {contact_info['last_name']}
        Contact Position: {contact_info['position']}
        Sequence: {sequence}

        Use the following template structure:
        [Personalized greeting]
        [Brief introduction referencing the job posting]
        [Candidate summary - generate this based on the job description]
        [Call to action]
        [Closing]

        Ensure the email is tailored to the specific job description and company.
        """
        message = await self.client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4096,
            temperature=0.1,
            system="You are an AI assistant tasked with creating personalized email templates for job prospecting.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        content = message.content
        self.template_cache[cache_key] = content
        return content

    def validate_email(self, email: str) -> Optional[str]:
        try:
            valid = validate_email(email)
            return valid.email
        except EmailNotValidError as e:
            logger.warning(f"Invalid email: {email}. Error: {str(e)}")
            return None

    def get_unsubscribe_link(self) -> str:
        return f"<br><br><small>To unsubscribe, <a href='{self.config['unsubscribe_url']}'>click here</a>.<br>Our address: {self.config['company_address']}</small>"

    async def schedule_email(self, to_email: str, subject: str, content: str, send_at: datetime) -> None:
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

    async def prepare_and_schedule_emails(self, job_postings: List[Dict], contacts: List[Dict]) -> List[Dict]:
        prepared_emails = []
        for job, contact in zip(job_postings, contacts):
            for sequence, details in self.email_sequences.items():
                email_content = await self.generate_email_content(job, contact['contact_info'], sequence)
                send_date = datetime.now() + timedelta(days=details['delay_days'])
                
                await self.schedule_email(
                    to_email=contact['contact_info']['email'],
                    subject=details['subject'],
                    content=email_content,
                    send_at=send_date
                )
                
                prepared_emails.append({
                    'to_email': contact['contact_info']['email'],
                    'subject': details['subject'],
                    'content': email_content,
                    'sequence': sequence,
                    'scheduled_send_date': send_date
                })
        return prepared_emails

def email_outreach_agent(config: Dict):
    agent = EmailOutreachAgent(config)

    async def run(state: Dict) -> Dict:
        logger.info("Starting email outreach preparation and scheduling...")
        prepared_emails = await agent.prepare_and_schedule_emails(state['job_postings'], state['contacts'])
        
        state['prepared_emails'] = prepared_emails
        logger.info(f"Prepared and scheduled {len(prepared_emails)} emails for sending")
        return state

    return run