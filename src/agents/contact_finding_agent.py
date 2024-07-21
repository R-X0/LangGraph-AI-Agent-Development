from anthropic import Anthropic
import os

def contact_finding_agent(config):
    client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    def find_contact(company_name):
        prompt = f"""
        Find potential contact information for the company: {company_name}. 
        Use your knowledge to provide:
        1. A likely email format (e.g., firstname.lastname@company.com)
        2. The company's main website
        3. Any social media profiles
        
        Present the information in a structured format.
        """

        message = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1000,
            temperature=0,
            system="You are an AI assistant tasked with finding company contact information.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract the text content from the ContentBlock
        contact_info = message.content[0].text if message.content else "No information found"
        
        return {'company_name': company_name, 'contact_info': contact_info}

    def run(state):
        print("Starting contact finding...")
        contacts = []
        for job in state.get('job_postings', []):
            print(f"Finding contact for {job['company_name']}...")
            contact_info = find_contact(job['company_name'])
            contacts.append(contact_info)
        print(f"Found contact information for {len(contacts)} companies")
        return {"job_postings": state['job_postings'], "contacts": contacts}

    return run