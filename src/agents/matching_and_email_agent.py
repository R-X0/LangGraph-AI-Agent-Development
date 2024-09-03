# src/agents/matching_and_email_agent.py

import json
import logging
from typing import Dict, List
import anthropic

logger = logging.getLogger(__name__)

class MatchingAgent:
    def __init__(self, configs: Dict):
        self.configs = configs
        self.claude_client = anthropic.Anthropic(api_key=configs['anthropic']['api_key'])

    def load_job_posts(self) -> List[Dict]:
        with open("job_posts.json", "r") as f:
            return json.load(f)

    def load_prospects(self) -> List[Dict]:
        with open("prospects.json", "r") as f:
            return json.load(f)

    def match_job_to_prospect(self, job: Dict, prospects: List[Dict]) -> Dict:
        prompt = f"""
        Evaluate how well the following job posting matches with each prospect's profile.
        Provide a match score between 0 and 100 for each prospect, where 100 is a perfect match.
        Only respond with a JSON object containing the prospect's name as the key and the score as the value.

        Job Posting:
        Title: {job['job_title']}
        Company: {job['company_name']}
        Description: {job['job_description']}

        Prospects:
        {json.dumps([{
            'name': p.get('name', 'N/A'),
            'title': p.get('title', 'N/A'),
            'company': p.get('company', 'N/A')
        } for p in prospects], indent=2)}
        """

        response = self.claude_client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=2000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            scores = json.loads(response.content[0].text)
            best_match = max(scores.items(), key=lambda x: x[1])
            best_prospect = next(p for p in prospects if p.get('name') == best_match[0])
            return {'job': job, 'prospect': best_prospect, 'score': best_match[1]}
        except (json.JSONDecodeError, ValueError, AttributeError, IndexError) as e:
            logger.error(f"Error processing Claude's response for job {job['job_title']}: {str(e)}")
            return {'job': job, 'prospect': None, 'score': 0}

    def run(self) -> List[Dict]:
        logger.info("Starting matching process...")
        job_posts = self.load_job_posts()
        prospects = self.load_prospects()
        
        logger.info(f"Loaded {len(job_posts)} job posts and {len(prospects)} prospects")
        logger.info(f"Sample job post: {job_posts[0] if job_posts else 'No job posts'}")
        logger.info(f"Sample prospect: {prospects[0] if prospects else 'No prospects'}")

        matched_data = []

        for job in job_posts:
            match = self.match_job_to_prospect(job, prospects)
            matched_data.append(match)
            logger.info(f"Matched job {job['job_title']} with prospect {match['prospect'].get('name', 'N/A') if match['prospect'] else 'No match'} (Score: {match['score']})")

        logger.info(f"Matched {len(matched_data)} job-prospect pairs")
        return matched_data

def matching_and_email_agent(configs: Dict):
    matching_agent = MatchingAgent(configs)
    
    def run(state: Dict) -> Dict:
        matched_data = matching_agent.run()
        return {"matched_data": matched_data}

    return run