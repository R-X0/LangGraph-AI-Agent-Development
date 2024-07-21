from langgraph.graph import Graph
from .job_scraping_agent import JobScrapingAgent
from .contact_finding_agent import contact_finding_tool

class OrchestrationAgent:
    def __init__(self, config):
        self.config = config
        self.graph = self.create_graph()

    def create_graph(self):
        graph = Graph()
        
        job_scraper = JobScrapingAgent(self.config)
        
        graph.add_node("scrape_jobs", job_scraper.run)
        graph.add_node("find_contacts", contact_finding_tool)
        
        graph.add_edge("scrape_jobs", "find_contacts")
        
        return graph

    def run(self):
        return self.graph.run({})