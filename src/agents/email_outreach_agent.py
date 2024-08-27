# src/agents/email_outreach_agent.py

import os
import asyncio
from typing import Dict, List, Optional
import anthropic
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import logging
from email_validator import validate_email, EmailNotValidError
from ratelimit import limits, sleep_and_retry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailOutreachAgent:
    def __init__(self, config: Dict):
        self.config = config
        self.client = anthropic.Anthropic(api_key=config['anthropic']['api_key'])
        self.sg = SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))
        self.from_email = config['sendgrid']['from_email']
        self.rate_limit = config['sendgrid'].get('rate_limit', 100)  # emails per minute
        self.template_cache = {}

    async def generate_email_template(self, job_posting: Dict, contact_info: Dict) -> str:
        cache_key = f"{job_posting['job_title']}_{job_posting['company_name']}"
        if cache_key in self.template_cache:
            return self.template_cache[cache_key]

        prompt = f"""
        Generate a personalized email template for a job prospecting outreach based on the following information:

        Job Title: {job_posting['job_title']}
        Company: {job_posting['company_name']}
        Job Description: {job_posting['job_description']}
        Contact Name: {contact_info['first_name']} {contact_info['last_name']}
        Contact Position: {contact_info['position']}

        The email should be professional, concise, and highlight how our staffing services can help fill this position.
        Include a clear call-to-action and an unsubscribe link at the bottom.
        """

        message = await self.client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=500,
            temperature=0.7,
            system="You are an AI assistant tasked with creating personalized email templates for job prospecting.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        template = message.content
        self.template_cache[cache_key] = template
        return template

    async def prepare_emails(self, job_postings: List[Dict], contacts: List[Dict]) -> List[Dict]:
        prepared_emails = []
        for job, contact in zip(job_postings, contacts):
            email_content = await self.generate_email_template(job, contact['contact_info'])
            prepared_emails.append({
                'to_email': contact['contact_info']['email'],
                'subject': f"Staffing Solutions for {job['job_title']} at {job['company_name']}",
                'content': email_content
            })
        return prepared_emails

    def validate_email(self, email: str) -> Optional[str]:
        try:
            valid = validate_email(email)
            return valid.email
        except EmailNotValidError as e:
            logger.warning(f"Invalid email: {email}. Error: {str(e)}")
            return None

    @sleep_and_retry
    @limits(calls=100, period=60)
    async def send_single_email(self, email: Dict) -> None:
        valid_email = self.validate_email(email['to_email'])
        if not valid_email:
            logger.error(f"Skipping invalid email: {email['to_email']}")
            return

        message = Mail(
            from_email=Email(self.from_email),
            to_emails=To(valid_email),
            subject=email['subject'],
            content=Content("text/html", email['content'] + self.get_unsubscribe_link())
        )
        try:
            response = await self.sg.send(message)
            logger.info(f"Email sent to {valid_email}. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending email to {valid_email}: {str(e)}")

    async def send_emails(self, prepared_emails: List[Dict]) -> None:
        tasks = [self.send_single_email(email) for email in prepared_emails]
        await asyncio.gather(*tasks)

    def get_unsubscribe_link(self) -> str:
        return f"<br><br><small>To unsubscribe, <a href='{self.config['unsubscribe_url']}'>click here</a>.<br>Our address: {self.config['company_address']}</small>"

def email_outreach_agent(config: Dict):
    agent = EmailOutreachAgent(config)

    def run(state: Dict) -> Dict:
        async def async_run():
            logger.info("Starting email outreach preparation...")
            prepared_emails = await agent.prepare_emails(state['job_postings'], state['contacts'])
            await agent.send_emails(prepared_emails)
            state['prepared_emails'] = prepared_emails
            return state

        return asyncio.run(async_run())

    return run