import anthropic
from typing import Dict, List

class EmailOutreachAgent:
    def __init__(self, config: Dict):
        self.config = config
        self.client = anthropic.Anthropic(api_key=config['anthropic']['api_key'])

    def generate_email_template(self, job_posting: Dict, contact_info: Dict) -> str:
        prompt = f"""
        Generate a personalized email template for a job prospecting outreach based on the following information:

        Job Title: {job_posting['job_title']}
        Company: {job_posting['company_name']}
        Job Description: {job_posting['job_description']}
        Contact Name: {contact_info['first_name']} {contact_info['last_name']}
        Contact Position: {contact_info['position']}

        The email should be professional, concise, and highlight how our staffing services can help fill this position.
        """

        message = self.client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=500,
            temperature=0.7,
            system="You are an AI assistant tasked with creating personalized email templates for job prospecting.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content

    def prepare_emails(self, job_postings: List[Dict], contacts: List[Dict]) -> List[Dict]:
        prepared_emails = []
        for job, contact in zip(job_postings, contacts):
            email_content = self.generate_email_template(job, contact['contact_info'])
            prepared_emails.append({
                'to_email': contact['contact_info']['email'],
                'subject': f"Staffing Solutions for {job['job_title']} at {job['company_name']}",
                'content': email_content
            })
        return prepared_emails

    def send_emails(self, prepared_emails: List[Dict]) -> None:
        # This method will be implemented later when we connect to an email service
        print(f"Would send {len(prepared_emails)} emails if connected to an email service.")
        for email in prepared_emails:
            print(f"To: {email['to_email']}")
            print(f"Subject: {email['subject']}")
            print(f"Content: {email['content'][:100]}...")  # Print first 100 characters
            print("---")

def email_outreach_agent(config: Dict):
    agent = EmailOutreachAgent(config)

    def run(state: Dict) -> Dict:
        print("Starting email outreach preparation...")
        prepared_emails = agent.prepare_emails(state['job_postings'], state['contacts'])
        agent.send_emails(prepared_emails)
        state['prepared_emails'] = prepared_emails
        return state

    return run