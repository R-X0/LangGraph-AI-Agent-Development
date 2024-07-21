import anthropic

def find_contact(company_name, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    
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
    
    return message.content