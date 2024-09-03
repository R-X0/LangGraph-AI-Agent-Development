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
        best_match = None
        best_score = 0

        for prospect in prospects:
            # Add a check to ensure prospect is a dictionary
            if not isinstance(prospect, dict):
                logger.warning(f"Skipping invalid prospect data: {prospect}")
                continue

            prompt = f"""
            Evaluate how well the following job posting matches with the prospect's profile:

            Job Posting:
            Title: {job['job_title']}
            Company: {job['company_name']}
            Description: {job['job_description']}

            Prospect:
            Name: {prospect.get('name', 'N/A')}
            Title: {prospect.get('title', 'N/A')}
            Company: {prospect.get('company', 'N/A')}

            Provide a match score between 0 and 100, where 100 is a perfect match.
            Only respond with the numeric score.
            """

            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=100,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            try:
                # Extract the content from the response
                content = response.content[0].text if isinstance(response.content, list) else response.content
                # Convert the content to a string and then to an integer
                score = int(str(content).strip())
                if score > best_score:
                    best_score = score
                    best_match = prospect
            except (ValueError, AttributeError, IndexError) as e:
                logger.warning(f"Invalid score returned by Claude for job {job['job_title']} and prospect {prospect.get('name', 'N/A')}: {str(e)}")

        return {'job': job, 'prospect': best_match, 'score': best_score}

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