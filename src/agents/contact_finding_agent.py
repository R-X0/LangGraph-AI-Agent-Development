from anthropic import Anthropic

def contact_finding_agent(config):
    client = Anthropic(api_key=config['anthropic']['api_key'])

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
            model="claude-3-opus-20240229",
            max_tokens=1000,
            temperature=0,
            system="You are an AI assistant tasked with finding company contact information.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return {'company_name': company_name, 'contact_info': message.content}

    def run(state):
        contacts = []
        for job in state.get('job_postings', []):
            contact_info = find_contact(job['company_name'])
            contacts.append(contact_info)
        return {"contacts": contacts}

    return run