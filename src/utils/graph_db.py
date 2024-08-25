# src/utils/graph_db.py

from neo4j import GraphDatabase

class GraphDB:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def create_job_posting(self, job_data):
        with self.driver.session() as session:
            session.execute_write(self._create_job_posting, job_data)

    @staticmethod
    def _create_job_posting(tx, job_data):
        query = (
            "CREATE (j:JobPosting {title: $title, company: $company, location: $location, description: $description, postDate: $postDate})"
        )
        tx.run(query, title=job_data['job_title'], company=job_data['company_name'],
               location=job_data['job_location'], description=job_data['job_description'],
               postDate=job_data['job_post_date'])

    def create_company_contact(self, company_name, contact_info):
        with self.driver.session() as session:
            session.execute_write(self._create_company_contact, company_name, contact_info)

    @staticmethod
    def _create_company_contact(tx, company_name, contact_info):
        query = (
            "MERGE (c:Company {name: $company_name}) "
            "SET c.email = $email, "
            "c.position = $position, "
            "c.confidenceScore = $confidence_score, "
            "c.domain = $domain, "
            "c.firstName = $first_name, "
            "c.lastName = $last_name, "
            "c.source = $source"
        )
        tx.run(query, 
               company_name=company_name, 
               email=contact_info['email'],
               position=contact_info['position'],
               confidence_score=contact_info['confidence_score'],
               domain=contact_info['domain'],
               first_name=contact_info['first_name'],
               last_name=contact_info['last_name'],
               source=contact_info['source'])

    def get_job_postings(self):
        with self.driver.session() as session:
            result = session.run("MATCH (j:JobPosting) RETURN j")
            return [record["j"] for record in result]

    def get_company_contacts(self):
        with self.driver.session() as session:
            result = session.run("MATCH (c:Company) RETURN c")
            return [record["c"] for record in result]

    def display_stored_data(self):
        print("Job Postings:")
        for job in self.get_job_postings():
            print(f"Title: {job['title']}")
            print(f"Company: {job['company']}")
            print(f"Location: {job['location']}")
            print(f"Description: {job['description'][:100]}...")  # First 100 characters
            print(f"Post Date: {job['postDate']}")
            print("---")

        print("\nCompany Contacts:")
        for company in self.get_company_contacts():
            print(f"Company: {company['name']}")
            print(f"Email: {company['email']}")
            print(f"Position: {company['position']}")
            print(f"Confidence Score: {company['confidenceScore']}")
            print(f"Domain: {company['domain']}")
            print(f"First Name: {company['firstName']}")
            print(f"Last Name: {company['lastName']}")
            print(f"Source: {company['source']}")
            print("---")